"""Knowledge base articles and resolved ticket history."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from .search import BM25Index


@dataclass
class Article:
    id: str
    title: str
    queue: str
    tags: list[str]
    body: str


def _parse_article(path: Path) -> Article:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path} has no front matter")
    _, front, body = text.split("---", 2)
    meta = yaml.safe_load(front)
    return Article(meta["id"], meta["title"], meta["queue"], meta.get("tags", []), body.strip())


class KnowledgeBase:
    def __init__(self, kb_dir: Path) -> None:
        self.articles = {a.id: a for a in map(_parse_article, sorted(kb_dir.glob("*.md")))}
        self.index = BM25Index()
        for article in self.articles.values():
            # Title and tags are repeated so that they weigh more than body text.
            boost = f"{article.title} {' '.join(article.tags)}"
            self.index.add(article.id, f"{boost} {boost} {article.body}")

    def search(self, query: str, k: int = 3) -> list[dict]:
        hits = []
        for doc_id, score in self.index.search(query, k):
            article = self.articles[doc_id]
            hits.append({
                "id": article.id,
                "title": article.title,
                "queue": article.queue,
                "score": round(score, 2),
                "text": article.body[:900],
            })
        return hits


class TicketHistory:
    def __init__(self, path: Path) -> None:
        self.tickets: dict[str, dict] = {}
        self.index = BM25Index()
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self.tickets[row["id"]] = row
                    self.index.add(row["id"], f"{row['subject']} {row['body']}")

    def search(self, query: str, k: int = 3) -> list[dict]:
        fields = ("id", "subject", "type", "queue", "priority", "resolution")
        return [
            {f: self.tickets[doc_id][f] for f in fields}
            for doc_id, _ in self.index.search(query, k)
        ]
