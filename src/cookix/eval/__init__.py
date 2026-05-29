"""Reproducible benchmark suite for CookiX.

Everything here is deterministic: a single ``seed`` fixes the synthetic corpus,
the random baseline, and therefore every reported number. The suite exists to
back the central NoVectDB claim with evidence — that typed, directed edges carry
relational information flat content similarity cannot recover — by comparing
CookiX against fair content-similarity and no-skill baselines on the same
natural-language queries.

Quickstart::

    from cookix.eval import run_benchmark, to_markdown

    print(to_markdown(run_benchmark(seed=0, n_worlds=40)))
"""

from __future__ import annotations

from .baselines import (
    CookixRetriever,
    LexicalRetriever,
    RandomRetriever,
    Retrieved,
)
from .corpus import Corpus, EvalQuery, synthetic_corpus
from .extraction import (
    Annotated,
    ExtractionReport,
    ExtractionScore,
    gold_extraction_corpus,
    projected_multihop_accuracy,
    run_extraction_study,
    score_extractor,
    to_markdown_extraction,
)
from .harness import (
    BenchmarkReport,
    RetrieverScore,
    run_benchmark,
)
from .report import to_json, to_markdown
from .sheaf_study import SheafAblation, run_sheaf_ablation, to_markdown_sheaf

__all__ = [
    "synthetic_corpus",
    "Corpus",
    "EvalQuery",
    "Retrieved",
    "LexicalRetriever",
    "RandomRetriever",
    "CookixRetriever",
    "run_benchmark",
    "BenchmarkReport",
    "RetrieverScore",
    "to_markdown",
    "to_json",
    "Annotated",
    "ExtractionScore",
    "ExtractionReport",
    "gold_extraction_corpus",
    "score_extractor",
    "run_extraction_study",
    "projected_multihop_accuracy",
    "to_markdown_extraction",
    "SheafAblation",
    "run_sheaf_ablation",
    "to_markdown_sheaf",
]
