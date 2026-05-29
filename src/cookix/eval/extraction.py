"""Extraction-quality study: extraction error is the multi-hop ceiling.

Ingestion quality bounds every relational result. If each edge is extracted
correctly with probability ``p``, an ``h``-hop answer is correct with
probability about ``p**h`` — errors compound. This module measures ``p`` for an
:class:`~cookix.extraction.extractor.Extractor` against a gold-annotated corpus
and projects the resulting multi-hop ceiling, so the claim in the extractor
docstring is backed by a real, reproducible number rather than asserted.

Two quality signals are reported, deliberately decomposed:

* **exact-triple** precision / recall / F1 — did the extractor recover the whole
  ``(subject, relation, object)`` after light normalisation (case, articles)?
* **relation accuracy** — restricted to predictions whose subject/object span
  the right entities, how often is the *relation type* correct? This isolates
  relation typing from argument-boundary detection.

The corpus and the rule-based extractor are fully deterministic, so the study
runs offline in CI. An :class:`~cookix.extraction.extractor.LLMExtractor` can be
plugged into the same scorer when an API key is available.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..extraction.extractor import RuleBasedExtractor, Triple

# Articles dropped during normalisation so "the rain" matches "rain". We do NOT
# strip prepositions: an extractor that returns "with carbon fiber" instead of
# "carbon fiber" genuinely got the boundary wrong, and the score should say so.
_ARTICLES = {"the", "a", "an"}
_WORD = re.compile(r"[a-z0-9]+")


def _norm(text: str) -> str:
    return " ".join(t for t in _WORD.findall(text.lower()) if t not in _ARTICLES)


def _key(t: Triple) -> tuple[str, str, str]:
    return (_norm(t.subject), t.relation, _norm(t.object))


def _args(t: Triple) -> tuple[str, str]:
    return (_norm(t.subject), _norm(t.object))


@dataclass(frozen=True)
class Annotated:
    """A sentence paired with its gold triples."""

    text: str
    triples: tuple[Triple, ...]


def gold_extraction_corpus() -> list[Annotated]:
    """A fixed, hand-annotated corpus spanning easy and realistically hard cases.

    It mixes sentences a keyword splitter handles cleanly with ones it cannot:
    relations expressed by out-of-vocabulary synonyms, two-relation sentences
    (a keyword splitter emits only the first), and phrasings where the naive
    before/after split captures the wrong span. That mix is the point — it shows
    where rule-based extraction breaks and why stronger extraction matters.
    """
    return [
        # --- clean single-relation sentences (subject verb object) ---
        Annotated("Aspirin prevents clotting.",
                  (Triple("aspirin", "prevents", "clotting"),)),
        Annotated("The umbrella prevents the rain.",
                  (Triple("umbrella", "prevents", "rain"),)),
        Annotated("Penicillin causes an allergic reaction.",
                  (Triple("penicillin", "causes", "allergic reaction"),)),
        Annotated("Smoking causes cancer.",
                  (Triple("smoking", "causes", "cancer"),)),
        Annotated("Warfarin contradicts aspirin.",
                  (Triple("warfarin", "contradicts", "aspirin"),)),
        Annotated("The new policy contradicts the old guidance.",
                  (Triple("new policy", "contradicts", "old guidance"),)),
        Annotated("Steel beams require proper support.",
                  (Triple("steel beams", "requires", "proper support"),)),
        Annotated("The engine requires fuel.",
                  (Triple("engine", "requires", "fuel"),)),
        # --- harder: out-of-vocabulary synonym (no keyword fires) ---
        Annotated("Smoking leads to heart disease.",
                  (Triple("smoking", "causes", "heart disease"),)),
        Annotated("The bridge collapsed due to corrosion.",
                  (Triple("corrosion", "causes", "bridge collapse"),)),
        Annotated("Antibiotics ward off infection.",
                  (Triple("antibiotics", "prevents", "infection"),)),
        # --- harder: two relations in one sentence (keyword splitter emits one) ---
        Annotated("The valve requires a gasket and prevents leakage.",
                  (Triple("valve", "requires", "gasket"),
                   Triple("valve", "prevents", "leakage"))),
        Annotated("Vaccination prevents measles and reduces transmission.",
                  (Triple("vaccination", "prevents", "measles"),
                   Triple("vaccination", "prevents", "transmission"))),
        # --- harder: boundary noise around the verb ---
        Annotated("Titanium is compatible with carbon fiber.",
                  (Triple("titanium", "compatible_with", "carbon fiber"),)),
        Annotated("This grade of steel conforms to ISO 4422.",
                  (Triple("steel", "conforms_to", "iso 4422"),)),
        Annotated("A flange is a kind of fitting.",
                  (Triple("flange", "is_a", "fitting"),)),
    ]


@dataclass
class ExtractionScore:
    name: str
    precision: float
    recall: float
    f1: float
    relation_accuracy: float  # nan if no prediction spanned the right entities
    n_gold: int
    n_pred: int
    n_exact: int
    n_arg_matched: int


@dataclass
class ExtractionReport:
    corpus_name: str
    n_sentences: int
    max_hops: int
    scores: list[ExtractionScore]
    # per-extractor projected multi-hop accuracy: name -> [p**1, ..., p**H]
    projected: dict[str, list[float]] = field(default_factory=dict)


def score_extractor(extractor, name: str, corpus: list[Annotated]) -> ExtractionScore:
    gold_keys: set[tuple[str, str, str]] = set()
    pred_keys: list[tuple[str, str, str]] = []
    gold_args: dict[tuple[str, str], str] = {}
    n_gold = 0
    for item in corpus:
        for g in item.triples:
            gold_keys.add(_key(g))
            gold_args[_args(g)] = g.relation
            n_gold += 1
        for p in extractor.extract(item.text):
            pred_keys.append(_key(p))

    n_pred = len(pred_keys)
    n_exact = sum(1 for k in pred_keys if k in gold_keys)
    # Of predictions that found the right entity pair, how many typed it right?
    arg_matched = [(s, r, o) for (s, r, o) in pred_keys if (s, o) in gold_args]
    n_arg = len(arg_matched)
    n_arg_correct = sum(1 for (s, r, o) in arg_matched if gold_args[(s, o)] == r)

    precision = n_exact / n_pred if n_pred else 0.0
    recall = n_exact / n_gold if n_gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    rel_acc = n_arg_correct / n_arg if n_arg else float("nan")
    return ExtractionScore(
        name=name, precision=precision, recall=recall, f1=f1,
        relation_accuracy=rel_acc, n_gold=n_gold, n_pred=n_pred,
        n_exact=n_exact, n_arg_matched=n_arg,
    )


def projected_multihop_accuracy(per_edge: float, max_hops: int = 4) -> list[float]:
    """Project the multi-hop ceiling from a per-edge correctness probability.

    With independent per-edge correctness ``per_edge``, an ``h``-hop chain is
    correct with probability ``per_edge ** h``.
    """
    return [per_edge**h for h in range(1, max_hops + 1)]


def run_extraction_study(
    extractors: dict[str, object] | None = None, max_hops: int = 4
) -> ExtractionReport:
    """Score each extractor on the gold corpus and project the multi-hop ceiling.

    Defaults to the deterministic :class:`RuleBasedExtractor` so the study runs
    offline. Pass additional extractors (e.g. an ``LLMExtractor``) to compare.
    """
    if extractors is None:
        extractors = {"rule-based": RuleBasedExtractor()}
    corpus = gold_extraction_corpus()
    scores = [score_extractor(ex, name, corpus) for name, ex in extractors.items()]
    projected = {
        s.name: projected_multihop_accuracy(s.recall, max_hops) for s in scores
    }
    return ExtractionReport(
        corpus_name="gold-extraction-v1",
        n_sentences=len(corpus),
        max_hops=max_hops,
        scores=scores,
        projected=projected,
    )


def _fmt(v: float) -> str:
    return "n/a" if v != v else f"{v:.3f}"  # v!=v is True only for NaN


def to_markdown_extraction(report: ExtractionReport) -> str:
    lines = [
        f"### Extraction quality: `{report.corpus_name}`",
        "",
        f"{report.n_sentences} gold-annotated sentences. Per-edge extraction "
        "accuracy is the ceiling on multi-hop retrieval.",
        "",
        "| extractor | precision | recall | f1 | relation_acc | gold | pred | exact |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in report.scores:
        lines.append(
            f"| {s.name} | {_fmt(s.precision)} | {_fmt(s.recall)} | {_fmt(s.f1)} "
            f"| {_fmt(s.relation_accuracy)} | {s.n_gold} | {s.n_pred} | {s.n_exact} |"
        )
    lines.append("")
    lines.append(
        f"Projected multi-hop ceiling `p**h` from per-edge recall (h=1..{report.max_hops}):"
    )
    lines.append("")
    hops = " | ".join(f"{h}-hop" for h in range(1, report.max_hops + 1))
    lines.append(f"| extractor | {hops} |")
    lines.append("|" + "---|" * (report.max_hops + 1))
    for name, curve in report.projected.items():
        cells = " | ".join(_fmt(v) for v in curve)
        lines.append(f"| {name} | {cells} |")
    return "\n".join(lines)
