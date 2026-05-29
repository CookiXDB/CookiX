from __future__ import annotations

import math

from cookix.eval.extraction import (
    Triple,
    gold_extraction_corpus,
    projected_multihop_accuracy,
    run_extraction_study,
    score_extractor,
    to_markdown_extraction,
)


class _PerfectExtractor:
    """Oracle that returns exactly the gold triples for each sentence."""

    def __init__(self, corpus):
        self._by_text = {a.text: list(a.triples) for a in corpus}

    def extract(self, text: str):
        return self._by_text.get(text, [])


class _EmptyExtractor:
    def extract(self, text: str):
        return []


def test_corpus_is_fixed_and_nonempty():
    a = gold_extraction_corpus()
    b = gold_extraction_corpus()
    assert a == b  # deterministic, hand-annotated
    assert len(a) >= 12
    assert sum(len(item.triples) for item in a) > len(a)  # some multi-triple sentences


def test_perfect_extractor_scores_one():
    corpus = gold_extraction_corpus()
    score = score_extractor(_PerfectExtractor(corpus), "oracle", corpus)
    assert score.precision == 1.0
    assert score.recall == 1.0
    assert score.f1 == 1.0
    assert score.relation_accuracy == 1.0
    assert score.n_exact == score.n_gold


def test_empty_extractor_scores_zero():
    corpus = gold_extraction_corpus()
    score = score_extractor(_EmptyExtractor(), "empty", corpus)
    assert score.precision == 0.0
    assert score.recall == 0.0
    assert score.f1 == 0.0
    assert math.isnan(score.relation_accuracy)  # no argument-matched predictions


def test_normalisation_ignores_articles_and_case():
    corpus = [type(gold_extraction_corpus()[0])(
        text="x", triples=(Triple("The Umbrella", "prevents", "the Rain"),)
    )]

    class _Cased:
        def extract(self, text):
            return [Triple("umbrella", "prevents", "rain")]

    score = score_extractor(_Cased(), "cased", corpus)
    assert score.n_exact == 1  # case + article differences normalised away


def test_relation_accuracy_isolates_typing():
    # Right entities, wrong relation -> arg-matched but relation_accuracy 0.
    corpus = [type(gold_extraction_corpus()[0])(
        text="x", triples=(Triple("a", "causes", "b"),)
    )]

    class _Mistyped:
        def extract(self, text):
            return [Triple("a", "prevents", "b")]

    score = score_extractor(_Mistyped(), "mistyped", corpus)
    assert score.n_arg_matched == 1
    assert score.relation_accuracy == 0.0
    assert score.n_exact == 0


def test_projected_curve_compounds():
    curve = projected_multihop_accuracy(0.5, max_hops=4)
    assert curve == [0.5, 0.25, 0.125, 0.0625]


def test_study_runs_and_renders():
    report = run_extraction_study()
    assert report.n_sentences == len(gold_extraction_corpus())
    assert [s.name for s in report.scores] == ["rule-based"]
    rb = report.scores[0]
    # Rule-based typing is reliable when it finds the entities, but free-text
    # recall is the bottleneck — this is the study's headline finding.
    assert rb.relation_accuracy == 1.0
    assert rb.recall < 1.0
    md = to_markdown_extraction(report)
    assert "rule-based" in md and "multi-hop ceiling" in md
