from __future__ import annotations

import math

from cookix.eval import (
    LexicalRetriever,
    Retrieved,
    run_benchmark,
    synthetic_corpus,
    to_json,
    to_markdown,
)
from cookix.eval.metrics import (
    hits_at_k,
    path_correct,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_corpus_is_deterministic():
    a = synthetic_corpus(seed=0, n_worlds=20)
    b = synthetic_corpus(seed=0, n_worlds=20)
    assert [d["_id"] for d in a.documents] == [d["_id"] for d in b.documents]
    assert [q.qid for q in a.queries] == [q.qid for q in b.queries]


def test_corpus_shape():
    corpus = synthetic_corpus(seed=1, n_worlds=10)
    assert corpus.n_docs == 60  # 6 entities per world
    assert len(corpus.queries) == 40  # 4 queries per world
    assert corpus.query_kinds() == {
        "single_hop": 10,
        "single_hop_inverse": 10,
        "multi_hop": 10,
        "contradiction": 10,
    }


def test_metric_definitions():
    answers = {"x"}
    ranked = [Retrieved("a", 0.9), Retrieved("x", 0.8), Retrieved("b", 0.7)]
    assert hits_at_k(ranked, answers, 1) == 0.0
    assert hits_at_k(ranked, answers, 5) == 1.0
    assert precision_at_k(ranked, answers, 5) == 1 / 5
    assert recall_at_k(ranked, answers, 5) == 1.0
    assert reciprocal_rank(ranked, answers) == 0.5


def test_path_acc_is_nan_without_gold_path():
    corpus = synthetic_corpus(seed=0, n_worlds=1)
    single = next(q for q in corpus.queries if q.kind == "single_hop")
    assert math.isnan(path_correct([], single))


def test_lexical_retrieves_topical_neighbourhood():
    # The lexical baseline shares the per-world adjective, so it should at least
    # surface entities from the right world — a fair (steelman) baseline.
    corpus = synthetic_corpus(seed=0, n_worlds=5)
    lex = LexicalRetriever(corpus.documents)
    q = corpus.queries[0]
    adj = q.anchor.split("_")[0]
    ranked = lex.retrieve(q, k=5)
    assert any(r.object_id.startswith(adj) for r in ranked)


def test_cookix_beats_lexical_on_relations():
    report = run_benchmark(seed=0, n_worlds=20, k=5)
    by_name = {s.name: s for s in report.scores}
    lexical = by_name["lexical-tfidf"]
    cookix = by_name["cookix-graph"]
    random_floor = by_name["random"]

    # The whole point: traversal recovers the relationally-correct entity that
    # content similarity cannot, and only CookiX produces a correct path.
    assert cookix.overall["hits@1"] > lexical.overall["hits@1"]
    assert cookix.overall["mrr"] > lexical.overall["mrr"]
    assert cookix.overall["path_acc"] > 0.0
    assert lexical.overall["path_acc"] == 0.0
    # Lexical is still a real baseline, comfortably above the no-skill floor.
    assert lexical.overall["hits@5"] > random_floor.overall["hits@5"]


def test_report_renderers():
    report = run_benchmark(seed=0, n_worlds=5)
    md = to_markdown(report)
    assert "cookix-graph" in md and "path_acc" in md
    js = to_json(report)
    assert run_benchmark(seed=0, n_worlds=5)  # determinism sanity
    assert to_json(report) == js  # rendering is pure
