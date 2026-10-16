"""Core chatbot engine: intent pattern matching + knowledge-base lookup + fallback."""
from __future__ import annotations

import json
import random
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .knowledge import KnowledgeBase
from .text_utils import normalize, tokenize

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

MAX_INPUT_CHARS = 500
KB_ANSWER_THRESHOLD = 0.55   # answer directly
KB_RELAXED_THRESHOLD = 0.40  # accepted when clearly ahead of the runner-up
KB_SUGGEST_THRESHOLD = 0.30  # "did you mean ...?"
KB_STRONG_THRESHOLD = 0.60   # strong enough to beat a weak intent such as "greeting"
_NAME_STOP_WORDS = {"and", "but", "so", "i", "please", "you", "how", "what"}


@dataclass
class Reply:
    text: str
    intent: str
    confidence: float
    exit: bool = False


@dataclass
class Intent:
    tag: str
    patterns: List["re.Pattern[str]"]
    responses: List[str]
    priority: int = 5
    max_words: Optional[int] = None
    yield_to_kb: bool = False
    action: Optional[str] = None
    exit: bool = False
    responses_alt: List[str] = field(default_factory=list)


def load_intents(path: Path) -> Tuple[Dict[str, str], List[Intent], List[str]]:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    intents = [
        Intent(
            tag=item["tag"],
            patterns=[re.compile(p) for p in item["patterns"]],
            responses=item["responses"],
            priority=item.get("priority", 5),
            max_words=item.get("max_words"),
            yield_to_kb=item.get("yield_to_kb", False),
            action=item.get("action"),
            exit=item.get("exit", False),
            responses_alt=item.get("responses_alt", []),
        )
        for item in raw["intents"]
    ]
    return raw.get("bot", {}), intents, raw.get("fallback", ["Sorry, I didn't understand that."])


class ChatBot:
    """Rule-based chatbot.

    Pipeline for every message:
      1. normalise the text (lower-case, expand contractions, strip punctuation)
      2. match it against the intent regex patterns (greeting, help, small talk, ...)
      3. otherwise search the knowledge base and answer if the match is good enough
      4. otherwise return a helpful fallback (with "did you mean" suggestions)
    """

    def __init__(self, data_dir: Optional[Path] = None, seed: Optional[int] = None,
                 clock: Callable[[], datetime] = datetime.now):
        data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.bot_info, self.intents, self.fallbacks = load_intents(data_dir / "intents.json")
        self.kb = KnowledgeBase.from_file(data_dir / "knowledge_base.json")
        self.bot_name = self.bot_info.get("name", "SyntecBot")
        self._rng = random.Random(seed)
        self._clock = clock
        self._last_choice: Dict[str, str] = {}
        self.user_name: Optional[str] = None
        self.last_topic: Optional[str] = None
        self.fallback_streak = 0

    # ------------------------------------------------------------------ public
    def respond(self, message: str) -> Reply:
        raw = (message or "").strip()[:MAX_INPUT_CHARS]
        if not raw:
            return Reply("I didn't catch that - please type something.", "empty", 1.0)
        text = normalize(raw)
        if not text:
            return self._fallback([])
        n_words = len(text.split())
        hits = self.kb.search(tokenize(text))
        match = self._match_intent(text, n_words)

        if match:
            intent, m = match
            rest_hits = hits
            if intent.yield_to_kb and n_words > 2:
                # "hi, what is NLP?" -> search the knowledge base without the greeting words
                rest_hits = self.kb.search(tokenize(text[:m.start()] + " " + text[m.end():]))
            kb_strong = (bool(rest_hits) and rest_hits[0][0] >= KB_STRONG_THRESHOLD
                         and not self._ambiguous(rest_hits))
            if intent.yield_to_kb and n_words > 2 and kb_strong:
                reply = self._kb_reply(rest_hits)
                if intent.tag == "greeting":
                    prefix = self._fmt(self._pick("greeting_prefix", ["Hello{nc}!", "Hi{nc}!"]))
                    reply.text = f"{prefix} {reply.text}"
                self.fallback_streak = 0
                return reply
            self.fallback_streak = 0
            return self._intent_reply(intent, m, text)

        if self._confident(hits):
            self.fallback_streak = 0
            return self._kb_reply(hits)
        return self._fallback(hits)

    def reset(self) -> None:
        self.user_name = None
        self.last_topic = None
        self.fallback_streak = 0

    # --------------------------------------------------------------- internals
    def _match_intent(self, text: str, n_words: int) -> Optional[Tuple[Intent, "re.Match[str]"]]:
        best: Optional[Tuple[Intent, "re.Match[str]"]] = None
        for intent in self.intents:
            if intent.max_words and n_words > intent.max_words:
                continue
            for pattern in intent.patterns:
                m = pattern.search(text)
                if m:
                    if best is None or intent.priority > best[0].priority:
                        best = (intent, m)
                    break
        return best

    @staticmethod
    def _confident(hits: List[Tuple[float, dict]]) -> bool:
        """Good score, or a fair score that is clearly ahead of the runner-up."""
        if not hits:
            return False
        top = hits[0][0]
        second = hits[1][0] if len(hits) > 1 else 0.0
        return top >= KB_ANSWER_THRESHOLD or (top >= KB_RELAXED_THRESHOLD and top - second >= 0.25)

    @staticmethod
    def _ambiguous(hits: List[Tuple[float, dict]]) -> bool:
        return (len(hits) > 1 and hits[0][0] < 1.5
                and hits[0][0] >= KB_ANSWER_THRESHOLD
                and hits[0][0] - hits[1][0] < 0.02)

    def _pick(self, key: str, options: List[str]) -> str:
        """Random choice that avoids repeating the previous answer for the same key."""
        choices = [o for o in options if o != self._last_choice.get(key)] or options
        choice = self._rng.choice(choices)
        self._last_choice[key] = choice
        return choice

    def _fmt(self, template: str, **extra: str) -> str:
        now = self._clock()
        values = defaultdict(str, {
            "nc": f", {self.user_name}" if self.user_name else "",
            "name": self.user_name or "",
            "bot": self.bot_name,
            "time": now.strftime("%I:%M %p").lstrip("0"),
            "date": now.strftime("%A, %d %B %Y"),
        })
        values.update(extra)
        return template.format_map(values)

    def _intent_reply(self, intent: Intent, m: "re.Match[str]", text: str) -> Reply:
        confidence = 1.0 if len(m.group(0)) >= 0.6 * len(text) else 0.8
        action = intent.action
        options = intent.responses

        if action == "remember_name":
            words: List[str] = []
            for w in m.group("name").split():
                if w in _NAME_STOP_WORDS:
                    break
                words.append(w)
            if not words:
                return self._fallback([])
            self.user_name = " ".join(words).title()
        elif action == "ask_name" and not self.user_name:
            options = intent.responses_alt
        elif action == "list_topics":
            topics = self._wrap_items(self.kb.topics())
            body = self._pick(intent.tag, options)
            return Reply(self._fmt(body, topics=topics, count=str(len(self.kb.entries))),
                         intent.tag, confidence)
        elif action == "more":
            return self._more_reply(intent, confidence)

        text_out = self._fmt(self._pick(intent.tag, options))
        return Reply(text_out, intent.tag, confidence, exit=intent.exit)

    @staticmethod
    def _wrap_items(items: List[str], width: int = 78) -> str:
        """Join items with ', ' and wrap between items so a topic never splits over two lines."""
        lines, current = [], ""
        for item in items:
            piece = item + ","
            if current and len(current) + 1 + len(piece) > width:
                lines.append(current)
                current = piece
            else:
                current = f"{current} {piece}".strip()
        lines.append(current)
        return "\n".join(lines).rstrip(",")

    def _more_reply(self, intent: Intent, confidence: float) -> Reply:
        if self.last_topic:
            related = self.kb.get(self.last_topic).get("related", [])
            names = [self.kb.get(r)["topic"] for r in related if r in self.kb.by_id]
            if names:
                return Reply("Related topics you can ask me about: " + ", ".join(names) + ".",
                             intent.tag, confidence)
        return Reply(self._fmt(self._pick("more_none", intent.responses)), intent.tag, confidence)

    def _kb_reply(self, hits: List[Tuple[float, dict]]) -> Reply:
        if self._ambiguous(hits):
            names = [e["topic"] for s, e in hits if hits[0][0] - s < 0.02]
            text = ("That could mean a few things: " + ", ".join(names)
                    + ". Which one would you like to know about?")
            return Reply(text, "kb_ambiguous", round(min(hits[0][0], 1.0), 2))
        score, entry = hits[0]
        self.last_topic = entry["id"]
        return Reply(entry["answer"], f"kb:{entry['id']}", round(min(score, 1.0), 2))

    def _fallback(self, hits: List[Tuple[float, dict]]) -> Reply:
        self.fallback_streak += 1
        suggestions = [e["topic"] for s, e in hits if s >= KB_SUGGEST_THRESHOLD][:3]
        if suggestions:
            text = "I'm not sure I understood. Did you mean: " + ", ".join(suggestions) + "?"
        else:
            text = self._fmt(self._pick("fallback", self.fallbacks))
        if self.fallback_streak >= 2:
            text += " (Tip: type 'help' to see what I can do, or 'topics' for my subjects.)"
        return Reply(text, "fallback", 0.0)
