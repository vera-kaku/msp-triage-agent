"""A small BM25 keyword index. No embeddings or vector database."""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "for", "from", "has",
    "have", "i", "if", "in", "is", "it", "its", "me", "my", "no", "not", "of", "on", "or", "our",
    "so", "that", "the", "their", "them", "there", "this", "to", "up", "us", "was", "we", "what",
    "when", "with", "you", "your", "just", "some", "any", "all", "been", "get", "got", "please",
}
# A deliberately light stemmer: "printers", "printing" and "printer" all become "print".
_SUFFIXES = ("ations", "ation", "ings", "ing", "ers", "er", "ed", "es", "s")


def stem(token: str) -> str:
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> list[str]:
    return [stem(t) for t in _TOKEN.findall(text.lower()) if t not in _STOP]


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.ids: list[str] = []
        self.docs: list[Counter] = []
        self.lengths: list[int] = []
        self.df: Counter = Counter()

    def add(self, doc_id: str, text: str) -> None:
        tokens = tokenize(text)
        counts = Counter(tokens)
        self.ids.append(doc_id)
        self.docs.append(counts)
        self.lengths.append(len(tokens))
        self.df.update(counts.keys())

    def search(self, query: str, k: int = 3) -> list[tuple[str, float]]:
        if not self.docs:
            return []
        n = len(self.docs)
        avg_len = sum(self.lengths) / n
        terms = set(tokenize(query))
        scored = []
        for doc_id, counts, length in zip(self.ids, self.docs, self.lengths, strict=True):
            score = 0.0
            for term in terms:
                tf = counts.get(term, 0)
                if not tf:
                    continue
                idf = math.log(1 + (n - self.df[term] + 0.5) / (self.df[term] + 0.5))
                norm = tf + self.k1 * (1 - self.b + self.b * length / avg_len)
                score += idf * tf * (self.k1 + 1) / norm
            if score > 0:
                scored.append((doc_id, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:k]
