"""Text helpers shared by the intent matcher and the knowledge base."""
from __future__ import annotations

import re
from typing import List

_CONTRACTIONS = {
    "what's": "what is", "who's": "who is", "how's": "how is",
    "that's": "that is", "where's": "where is", "there's": "there is",
    "i'm": "i am", "you're": "you are", "it's": "it is", "let's": "let us",
    "don't": "do not", "doesn't": "does not", "can't": "can not",
    "won't": "will not", "isn't": "is not", "i've": "i have",
    "i'll": "i will", "what're": "what are",
}
_CONTRACTION_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _CONTRACTIONS) + r")\b"
)

# Words that carry no topic information when searching the knowledge base.
STOPWORDS = frozenset(
    """a an the is are am was were be been being what whats who whom whose how why
    when where which do does did you your yours me my mine i we us our it its
    tell about explain define definition mean means meaning of in on to for and
    or can could would should will please give show know with by at as that this
    there any some help understand want need like teach there also just more
    let us difference differences between versus vs compare comparison type types kind kinds
    example examples work works working""".split()
)


def normalize(text: str) -> str:
    """Lower-case, expand contractions, protect special tokens, strip punctuation."""
    text = text.replace("\u2019", "'").lower().strip()
    text = _CONTRACTION_RE.sub(lambda m: _CONTRACTIONS[m.group(1)], text)
    # Keep technical tokens that contain punctuation intact.
    text = re.sub(r"\ba\s*\*|\ba[\s-]+star\b", "astar", text)
    text = re.sub(r"\btf[\s-]*idf\b", "tfidf", text)
    text = re.sub(r"\bk[\s-]*means\b", "kmeans", text)
    text = re.sub(r"'s\b", "s", text)  # today's -> todays
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def stem(token: str) -> str:
    """Very small suffix stripper so 'networks' ~ 'network', 'learning' ~ 'learn'."""
    if len(token) > 5 and token.endswith("ing"):
        token = token[:-3]
    elif len(token) > 4 and token.endswith("ed"):
        token = token[:-2]
    if len(token) > 3 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        token = token[:-1]
    return token


def tokenize(text: str) -> List[str]:
    """Normalised, stop-word-free, stemmed tokens (duplicates removed, order kept)."""
    tokens = [stem(t) for t in normalize(text).split() if t not in STOPWORDS]
    return list(dict.fromkeys(tokens))
