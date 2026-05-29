"""Retrieval metrics for the benchmark.

Standard ranked-retrieval metrics plus a relational one (path accuracy) that
only a path-returning retriever can score above zero.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .baselines import Retrieved
from .corpus import EvalQuery


def hits_at_k(ranked: Sequence[Retrieved], answers: set[str], k: int) -> float:
    return 1.0 if any(r.object_id in answers for r in ranked[:k]) else 0.0


def precision_at_k(ranked: Sequence[Retrieved], answers: set[str], k: int) -> float:
    if k == 0:
        return 0.0
    hit = sum(1 for r in ranked[:k] if r.object_id in answers)
    return hit / k


def recall_at_k(ranked: Sequence[Retrieved], answers: set[str], k: int) -> float:
    if not answers:
        return 0.0
    found = {r.object_id for r in ranked[:k]} & answers
    return len(found) / len(answers)


def reciprocal_rank(ranked: Sequence[Retrieved], answers: set[str]) -> float:
    for i, r in enumerate(ranked, start=1):
        if r.object_id in answers:
            return 1.0 / i
    return 0.0


def path_correct(ranked: Sequence[Retrieved], query: EvalQuery) -> float:
    """1.0 if the top correct answer was reached via the gold relation chain.

    Only meaningful when a gold path is defined (multi-hop). Retrievers that do
    not return paths score 0.0 here by construction — that asymmetry is the
    point: a reasoning path is something content similarity cannot produce.
    """
    if not query.gold_path:
        return float("nan")
    answers = set(query.answers)
    for r in ranked:
        if r.object_id in answers:
            return 1.0 if r.path == query.gold_path else 0.0
    return 0.0


@dataclass
class MetricAccumulator:
    """Running means of every metric, optionally bucketed by query kind."""

    k: int = 5
    _sums: dict[str, float] = None  # type: ignore[assignment]
    _counts: dict[str, int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._sums = {}
        self._counts = {}

    def _add(self, key: str, value: float) -> None:
        if value != value:  # NaN -> not applicable, skip
            return
        self._sums[key] = self._sums.get(key, 0.0) + value
        self._counts[key] = self._counts.get(key, 0) + 1

    def update(self, ranked: Sequence[Retrieved], query: EvalQuery) -> None:
        ans = set(query.answers)
        self._add("hits@1", hits_at_k(ranked, ans, 1))
        self._add(f"hits@{self.k}", hits_at_k(ranked, ans, self.k))
        self._add(f"precision@{self.k}", precision_at_k(ranked, ans, self.k))
        self._add(f"recall@{self.k}", recall_at_k(ranked, ans, self.k))
        self._add("mrr", reciprocal_rank(ranked, ans))
        self._add("path_acc", path_correct(ranked, query))

    def means(self) -> dict[str, float]:
        return {k: self._sums[k] / self._counts[k] for k in self._sums}
