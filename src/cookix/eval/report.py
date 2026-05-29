"""Render a :class:`BenchmarkReport` as Markdown or JSON."""

from __future__ import annotations

import json

from .harness import BenchmarkReport


def to_json(report: BenchmarkReport) -> str:
    payload = {
        "corpus": report.corpus_name,
        "n_docs": report.n_docs,
        "n_queries": report.n_queries,
        "k": report.k,
        "query_kinds": report.query_kinds,
        "scores": [
            {"retriever": s.name, "overall": s.overall, "by_kind": s.by_kind}
            for s in report.scores
        ],
    }
    return json.dumps(payload, indent=2)


def _fmt(v: float) -> str:
    return f"{v:.3f}"


def to_markdown(report: BenchmarkReport) -> str:
    metrics = report.metric_names()
    lines = [
        f"### Benchmark: `{report.corpus_name}`",
        "",
        f"{report.n_docs} documents · {report.n_queries} queries "
        f"({', '.join(f'{k}={v}' for k, v in sorted(report.query_kinds.items()))}) · k={report.k}",
        "",
        "| retriever | " + " | ".join(metrics) + " |",
        "|" + "---|" * (len(metrics) + 1),
    ]
    for s in report.scores:
        row = [s.name] + [_fmt(s.overall.get(m, float("nan"))) for m in metrics]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    lines.append("Higher is better for every metric. `path_acc` is only defined "
                 "for multi-hop queries and only a path-returning retriever can "
                 "score above zero.")
    return "\n".join(lines)
