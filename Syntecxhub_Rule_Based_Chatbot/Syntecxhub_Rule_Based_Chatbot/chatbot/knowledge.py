"""Small domain knowledge base (Artificial Intelligence) with weighted keyword search."""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

from .text_utils import tokenize

EXACT_MATCH_BONUS = 2.0  # > any partial score, so exact topic/alias matches always win


class KnowledgeBase:
    """Scores every entry against the user's tokens using IDF-weighted overlap.

    Token weights per entry: topic/alias words = 3, keywords = 2, example questions = 1.
    A query that equals a topic/alias exactly gets a bonus so that "AI" returns the
    Artificial Intelligence entry rather than "Generative AI".
    """

    def __init__(self, entries: List[dict]):
        self.entries = entries
        self.by_id: Dict[str, dict] = {e["id"]: e for e in entries}
        self._weights: List[Dict[str, int]] = []
        self._exact: List[set] = []
        doc_freq: Counter = Counter()
        for entry in entries:
            weights: Dict[str, int] = {}
            for tok in tokenize(entry["topic"]):
                weights[tok] = 3
            for alias in entry.get("aliases", []):
                for tok in tokenize(alias):
                    weights[tok] = 3
            for kw in entry.get("keywords", []):
                for tok in tokenize(kw):
                    weights[tok] = max(weights.get(tok, 0), 2)
            for q in entry.get("questions", []):
                for tok in tokenize(q):
                    weights[tok] = max(weights.get(tok, 0), 1)
            self._weights.append(weights)
            doc_freq.update(weights.keys())
            names = [entry["topic"]] + entry.get("aliases", [])
            self._exact.append({" ".join(tokenize(n)) for n in names})
        total = len(entries)
        self._idf = {t: math.log(1 + total / c) for t, c in doc_freq.items()}
        self._unknown_idf = math.log(1 + total)

    @classmethod
    def from_file(cls, path: Path) -> "KnowledgeBase":
        with open(path, encoding="utf-8") as fh:
            return cls(json.load(fh)["entries"])

    def topics(self) -> List[str]:
        return sorted(e["topic"] for e in self.entries)

    def get(self, entry_id: str) -> dict:
        return self.by_id[entry_id]

    def search(self, tokens: List[str], limit: int = 3) -> List[Tuple[float, dict]]:
        """Return up to `limit` (score, entry) pairs, best first. Score ~0..1 (+bonus)."""
        if not tokens:
            return []
        total = sum(self._idf.get(t, self._unknown_idf) for t in tokens)
        query_key = " ".join(tokens)
        scored: List[Tuple[float, dict]] = []
        for entry, weights, exact in zip(self.entries, self._weights, self._exact):
            score = sum(self._idf.get(t, 0.0) * weights.get(t, 0) / 3 for t in tokens) / total
            if query_key in exact:
                score += EXACT_MATCH_BONUS
            if score > 0:
                scored.append((round(score, 3), entry))
        scored.sort(key=lambda pair: -pair[0])
        return scored[:limit]
