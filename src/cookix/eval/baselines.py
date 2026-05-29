"""Retrievers compared in the benchmark.

All retrievers share one interface — given a query string, return a ranked list
of object ids — so the harness can score them identically. CookiX additionally
exposes the reasoning *path*, which content-similarity retrievers structurally
cannot.

* :class:`LexicalRetriever` — TF-IDF cosine over document content. This is the
  content-similarity baseline (the family a vector database belongs to): it has
  no notion of typed, directed edges. A dense neural embedder would plug into
  the same interface and behave the same way with respect to *relations* — it
  retrieves by topical proximity, not by traversal.
* :class:`RandomRetriever` — a seeded random ranking; the no-skill floor.
* :class:`CookixRetriever` — the CookiX pipeline at a chosen ablation ``mode``.
"""

from __future__ import annotations

import math
import random
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..database import Database
    from .corpus import EvalQuery

_TOKEN = re.compile(r"[a-z0-9]+")


@dataclass
class Retrieved:
    """One ranked result. ``path`` is the relation chain when the retriever has one."""

    object_id: str
    score: float
    path: tuple[str, ...] | None = None


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class LexicalRetriever:
    """TF-IDF cosine retriever over document content (the vector-family baseline)."""

    name = "lexical-tfidf"

    def __init__(self, documents: list[dict]) -> None:
        self._ids: list[str] = []
        raw: list[Counter[str]] = []
        df: Counter[str] = Counter()
        for doc in documents:
            toks = _tokenize(doc.get("content", ""))
            tf = Counter(toks)
            self._ids.append(doc["_id"])
            raw.append(tf)
            for term in tf:
                df[term] += 1
        n = max(len(documents), 1)
        self._idf = {t: math.log((1 + n) / (1 + d)) + 1.0 for t, d in df.items()}
        self._vecs = [self._weight(tf) for tf in raw]
        self._norms = [math.sqrt(sum(v * v for v in vec.values())) for vec in self._vecs]

    def _weight(self, tf: Counter[str]) -> dict[str, float]:
        return {t: c * self._idf.get(t, 0.0) for t, c in tf.items()}

    def retrieve(self, query: EvalQuery, k: int) -> list[Retrieved]:
        q = self._weight(Counter(_tokenize(query.text)))
        qnorm = math.sqrt(sum(v * v for v in q.values())) or 1.0
        scored: list[Retrieved] = []
        for i, vec in enumerate(self._vecs):
            dot = sum(w * vec.get(t, 0.0) for t, w in q.items())
            denom = qnorm * (self._norms[i] or 1.0)
            scored.append(Retrieved(self._ids[i], dot / denom))
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:k]


class RandomRetriever:
    """Seeded random ranking — the no-skill baseline."""

    name = "random"

    def __init__(self, documents: list[dict], seed: int = 0) -> None:
        self._ids = [d["_id"] for d in documents]
        self._rng = random.Random(seed)

    def retrieve(self, query: EvalQuery, k: int) -> list[Retrieved]:
        ids = list(self._ids)
        self._rng.shuffle(ids)
        return [Retrieved(i, 1.0 - rank / len(ids)) for rank, i in enumerate(ids[:k])]


@dataclass
class CookixRetriever:
    """The CookiX pipeline at a given ablation ``mode``.

    Receives the same natural-language query string as every other retriever and
    parses it with the database's own extractor — so this measures the whole
    end-to-end product, parsing included, not an oracle.
    """

    db: Database
    mode: str = "graph"
    name: str = field(default="")

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"cookix-{self.mode}"

    def retrieve(self, query: EvalQuery, k: int) -> list[Retrieved]:
        results = self.db.query(query.text, k=k, mode=self.mode)
        out: list[Retrieved] = []
        for r in results:
            # CookiX scores are distances (lower better); invert so the harness's
            # rank order (descending score) matches.
            out.append(
                Retrieved(
                    object_id=r.object_id,
                    score=-r.score,
                    path=tuple(s.relation for s in r.path),
                )
            )
        return out
