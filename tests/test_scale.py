from __future__ import annotations

from cookix.eval import ScaleReport, run_scale_benchmark, to_markdown_scale
from cookix.eval.perf import _scale_graph


def test_scale_graph_is_deterministic_and_well_formed():
    a = _scale_graph(50, avg_degree=3, seed=0)
    b = _scale_graph(50, avg_degree=3, seed=0)
    assert a == b  # deterministic from seed
    assert len(a) == 50
    assert all(doc["_id"] == f"n{i}" for i, doc in enumerate(a))
    # No self-loops were emitted.
    assert all(t != doc["_id"] for doc in a for _, t in doc["edges"])


def test_report_has_a_row_per_size():
    report = run_scale_benchmark(sizes=(200, 500), n_queries=20, seed=0)
    assert isinstance(report, ScaleReport)
    assert [r.n_objects for r in report.rows] == [200, 500]


def test_metrics_are_well_formed():
    report = run_scale_benchmark(sizes=(200,), n_queries=20, seed=0)
    row = report.rows[0]
    assert row.ingest_ms >= 0.0
    assert row.peak_mb > 0.0
    assert row.query_p95_ms >= row.query_median_ms
    assert row.qps > 0.0


def test_markdown_renders():
    report = run_scale_benchmark(sizes=(200,), n_queries=20, seed=0)
    md = to_markdown_scale(report)
    assert "Scaling" in md
    assert "objects" in md
    assert "200" in md
