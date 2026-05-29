"""Benchmark harness: builds the corpus, runs every retriever, scores them.

Deterministic end to end: a fixed ``seed`` fully determines the corpus, the
random baseline, and therefore every reported number.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .. import connect
from .baselines import CookixRetriever, LexicalRetriever, RandomRetriever
from .corpus import Corpus, synthetic_corpus
from .metrics import MetricAccumulator

# CookiX ablation modes to evaluate, mapped to friendly run names.
DEFAULT_MODES = ("graph", "topo", "sheaf", "reasoning")


@dataclass
class RetrieverScore:
    name: str
    overall: dict[str, float]
    by_kind: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class BenchmarkReport:
    corpus_name: str
    n_docs: int
    n_queries: int
    k: int
    query_kinds: dict[str, int]
    scores: list[RetrieverScore]

    def metric_names(self) -> list[str]:
        names: list[str] = []
        for s in self.scores:
            for m in s.overall:
                if m not in names:
                    names.append(m)
        return names


def _build_db(corpus: Corpus):
    db = connect(corpus.name)
    db.insert_many(corpus.documents)
    return db


def _score_retriever(retriever, corpus: Corpus, k: int) -> RetrieverScore:
    overall = MetricAccumulator(k=k)
    buckets: dict[str, MetricAccumulator] = {}
    for q in corpus.queries:
        ranked = retriever.retrieve(q, k)
        overall.update(ranked, q)
        buckets.setdefault(q.kind, MetricAccumulator(k=k)).update(ranked, q)
    return RetrieverScore(
        name=retriever.name,
        overall=overall.means(),
        by_kind={kind: acc.means() for kind, acc in buckets.items()},
    )


def run_benchmark(
    seed: int = 0,
    n_worlds: int = 40,
    k: int = 5,
    modes: tuple[str, ...] = DEFAULT_MODES,
) -> BenchmarkReport:
    """Run the full benchmark and return a structured report.

    Retrievers: a random floor, a TF-IDF (vector-family) baseline, and CookiX at
    each requested ablation ``mode``. Every retriever sees the same
    natural-language queries.
    """
    corpus = synthetic_corpus(seed=seed, n_worlds=n_worlds)
    db = _build_db(corpus)

    retrievers = [
        RandomRetriever(corpus.documents, seed=seed),
        LexicalRetriever(corpus.documents),
    ]
    retrievers += [CookixRetriever(db, mode=m) for m in modes]

    scores = [_score_retriever(r, corpus, k) for r in retrievers]
    return BenchmarkReport(
        corpus_name=corpus.name,
        n_docs=corpus.n_docs,
        n_queries=len(corpus.queries),
        k=k,
        query_kinds=corpus.query_kinds(),
        scores=scores,
    )
