from __future__ import annotations

from cookix.eval import PerfReport, run_perf_benchmark, to_markdown_perf
from cookix.eval.perf import _percentile


def test_report_has_a_row_per_mode():
    report = run_perf_benchmark(seed=0, n_worlds=4, k=5, repeats=1,
                                modes=("graph", "reasoning"))
    assert isinstance(report, PerfReport)
    labels = [r.label for r in report.rows]
    assert labels == ["cookix-graph", "cookix-reasoning"]


def test_call_count_matches_workload():
    # n_calls must equal n_queries * repeats — every query is timed each repeat.
    report = run_perf_benchmark(seed=1, n_worlds=4, k=5, repeats=2,
                                modes=("graph",))
    row = report.rows[0]
    assert row.n_calls == report.n_queries * report.repeats


def test_timings_are_well_formed():
    report = run_perf_benchmark(seed=0, n_worlds=4, k=3, repeats=1,
                                modes=("graph",))
    row = report.rows[0]
    assert row.median_ms >= 0.0
    assert row.mean_ms >= 0.0
    assert row.p95_ms >= row.median_ms  # p95 cannot sit below the median
    assert row.qps > 0.0
    assert report.ingest_ms >= 0.0


def test_workload_is_deterministic_in_shape():
    a = run_perf_benchmark(seed=3, n_worlds=5, k=5, repeats=1, modes=("graph",))
    b = run_perf_benchmark(seed=3, n_worlds=5, k=5, repeats=1, modes=("graph",))
    assert a.corpus_name == b.corpus_name
    assert a.n_docs == b.n_docs
    assert a.n_queries == b.n_queries


def test_percentile_nearest_rank():
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert _percentile(values, 100.0) == 50.0
    assert _percentile(values, 0.0) == 10.0  # clamps to the first element
    assert _percentile([], 95.0) == 0.0


def test_markdown_renders_every_mode():
    report = run_perf_benchmark(seed=0, n_worlds=4, k=5, repeats=1,
                                modes=("graph", "reasoning"))
    md = to_markdown_perf(report)
    assert "Performance" in md
    assert "cookix-graph" in md
    assert "cookix-reasoning" in md
    assert "queries/s" in md
