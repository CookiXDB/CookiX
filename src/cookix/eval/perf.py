"""Reproducible performance benchmark for the CookiX query engine.

The retrieval benchmark (see :mod:`cookix.eval.harness`) answers *is CookiX
correct?*; this answers *is it fast enough to use?*. It builds the same
deterministic synthetic corpus, then times the end-to-end query path — natural
language in, ranked reasoning paths out — at each ablation ``mode``.

The **workload** is deterministic (a fixed seed fixes the corpus and the query
set), so the numbers are comparable run to run on the same machine. The
**timings** are not: wall-clock latency depends on the CPU, the Python build,
and system load, so absolute milliseconds are only meaningful relative to each
other within one run. We report median and p95 latency (robust to GC pauses)
alongside throughput, and we warm up — building the index and running each mode
once — before measuring, so JIT-free Python import/first-call costs do not leak
into the numbers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from statistics import median

from .. import connect
from .corpus import synthetic_corpus

DEFAULT_MODES = ("graph", "topo", "sheaf", "reasoning")


@dataclass
class PerfRow:
    """Timing summary for one ablation mode over the full query set."""

    label: str
    n_calls: int
    median_ms: float
    mean_ms: float
    p95_ms: float
    qps: float


@dataclass
class PerfReport:
    corpus_name: str
    n_docs: int
    n_queries: int
    repeats: int
    ingest_ms: float
    rows: list[PerfRow]


def _percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile (no interpolation) — robust for small samples."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, min(len(ordered), round(pct / 100.0 * len(ordered))))
    return ordered[rank - 1]


def _time_mode(db, queries, mode: str, k: int, repeats: int) -> PerfRow:
    samples: list[float] = []
    for _ in range(repeats):
        for q in queries:
            start = time.perf_counter()
            db.query(q.text, k=k, mode=mode)
            samples.append((time.perf_counter() - start) * 1000.0)
    total_s = sum(samples) / 1000.0
    return PerfRow(
        label=f"cookix-{mode}",
        n_calls=len(samples),
        median_ms=median(samples),
        mean_ms=sum(samples) / len(samples),
        p95_ms=_percentile(samples, 95.0),
        qps=(len(samples) / total_s) if total_s > 0 else float("inf"),
    )


def run_perf_benchmark(
    seed: int = 0,
    n_worlds: int = 40,
    k: int = 5,
    repeats: int = 3,
    modes: tuple[str, ...] = DEFAULT_MODES,
) -> PerfReport:
    """Time the end-to-end query path at each ablation ``mode``.

    Args:
        seed: RNG seed fixing the corpus and query set (workload determinism).
        n_worlds: number of synthetic worlds (<=80); scales corpus size.
        k: retrieval cutoff passed to every query.
        repeats: how many times to replay the full query set per mode; more
            repeats give a steadier median.
        modes: ablation modes to time, friendly names (``graph``/``topo``/
            ``sheaf``/``reasoning``).
    """
    corpus = synthetic_corpus(seed=seed, n_worlds=n_worlds)

    start = time.perf_counter()
    db = connect(corpus.name)
    db.insert_many(corpus.documents)
    ingest_ms = (time.perf_counter() - start) * 1000.0

    # Warm up: trigger lazy topology indexing and first-call paths for every
    # mode so one-off setup cost does not contaminate the timed loop.
    for mode in modes:
        for q in corpus.queries[: min(len(corpus.queries), 8)]:
            db.query(q.text, k=k, mode=mode)

    rows = [_time_mode(db, corpus.queries, m, k, repeats) for m in modes]
    return PerfReport(
        corpus_name=corpus.name,
        n_docs=corpus.n_docs,
        n_queries=len(corpus.queries),
        repeats=repeats,
        ingest_ms=ingest_ms,
        rows=rows,
    )


def to_markdown_perf(report: PerfReport) -> str:
    lines = [
        f"### Performance: `{report.corpus_name}`",
        "",
        f"{report.n_docs} documents · {report.n_queries} queries × "
        f"{report.repeats} repeats · ingest {report.ingest_ms:.1f} ms",
        "",
        "| mode | calls | median ms | mean ms | p95 ms | queries/s |",
        "|---|---|---|---|---|---|",
    ]
    for r in report.rows:
        lines.append(
            f"| {r.label} | {r.n_calls} | {r.median_ms:.3f} | {r.mean_ms:.3f} "
            f"| {r.p95_ms:.3f} | {r.qps:.0f} |"
        )
    lines.append("")
    lines.append(
        "Timings are wall-clock on the measuring machine and vary with hardware "
        "and load; only the relative cost of each mode is portable. The workload "
        "(corpus + queries) is fixed by `seed`."
    )
    return "\n".join(lines)
