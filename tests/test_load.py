from __future__ import annotations

import pytest

from cookix.eval.load import _rss_mb

pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")

from cookix.eval import LoadReport, run_load_test, to_markdown_load  # noqa: E402


def test_rss_is_positive_or_none():
    m = _rss_mb()
    assert m is None or m > 0.0


def test_load_test_runs_with_no_errors():
    # A short real load test: starts the server on a socket and hammers it.
    report = run_load_test(objects=500, workers=4, duration_s=2.0, port=8931)
    assert isinstance(report, LoadReport)
    assert report.requests > 0
    assert report.errors == 0  # the server must not drop requests under load
    assert report.rps > 0.0
    assert report.p99_ms >= report.median_ms


def test_load_markdown_renders():
    report = run_load_test(objects=300, workers=2, duration_s=1.5, port=8932)
    md = to_markdown_load(report)
    assert "Load / soak" in md
    assert "Throughput" in md
    assert "Errors" in md
