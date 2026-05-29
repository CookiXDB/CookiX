"""External multi-hop QA evaluation (the credibility gate, Phase 6).

The synthetic benchmark (:mod:`cookix.eval.harness`) shows CookiX recovers
relational answers a content baseline cannot — but on a corpus CookiX designed.
This module runs the same question on data CookiX did **not** design:
**2WikiMultiHopQA**, which is uniquely suited because each example ships *gold*
``(subject, relation, object)`` evidence triples alongside the supporting
paragraphs. That lets us separate two very different questions:

1. *Does the relational engine work?* — build the knowledge graph from the gold
   evidence triples and ask whether typed multi-hop traversal recovers the answer
   entity better than strong lexical passage retrieval (Okapi BM25) over the same
   paragraphs. This is the **oracle entity-linking** setting standard in KG-QA:
   the question's head entity (anchor) is given, so we measure the *reasoning*
   engine in isolation, not the upstream extraction/linking pipeline.

2. *Does the end-to-end product work?* — that depends on triple extraction from
   free text, measured separately (``cookix eval --extraction``) and known to be
   the current bottleneck. We do not conflate the two.

Honest framing, stated in the report itself: result (1) is a claim about the
**engine under oracle linking**, which is exactly what the NoVectDB paper's
Algorithm 1 is. It is a fair, recognised setting — and a real win there is real —
but it is not an end-to-end open-domain QA number, and we never present it as one.

The 2Wiki schema we parse (one JSON list of examples)::

    {"_id", "question", "answer", "type",
     "context":    [[title, [sentence, ...]], ...],
     "evidences":  [[subject, relation, object], ...],
     "supporting_facts": [[title, sent_id], ...]}

Loaders are format-real; a tiny fixture in the same schema ships with the tests
so the whole pipeline runs offline and in CI. Point ``--path`` at the full
2Wiki dev download to reproduce at scale.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .. import connect
from .baselines import Retrieved

_TOKEN = re.compile(r"[a-z0-9]+")
_PUNCT = re.compile(r"[^a-z0-9 ]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def normalise_entity(name: str) -> str:
    """Canonical entity key: lowercase, punctuation-stripped, whitespace-folded.

    Entity surfaces in 2Wiki differ in case/punctuation between the answer field,
    the context titles, and the evidence triples; this folds them so the same
    real-world entity maps to one graph node.
    """
    return _PUNCT.sub(" ", name.lower()).strip().replace("  ", " ")


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RelExample:
    """One multi-hop question with its gold relational chain and answer."""

    qid: str
    question: str
    answer: str
    qtype: str
    evidences: tuple[tuple[str, str, str], ...]  # (subject, relation, object)
    context: tuple[tuple[str, str], ...]  # (title, joined sentences)

    @property
    def anchor(self) -> str | None:
        """The head entity of the reasoning chain (oracle-linked anchor)."""
        return self.evidences[0][0] if self.evidences else None

    @property
    def gold_relations(self) -> tuple[str, ...]:
        return tuple(r for _, r, _ in self.evidences)


@dataclass
class RelationalDataset:
    name: str
    examples: list[RelExample] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.examples)

    def type_counts(self) -> dict[str, int]:
        c: Counter[str] = Counter(e.qtype for e in self.examples)
        return dict(c)


# --------------------------------------------------------------------------- #
# Loader (real 2WikiMultiHopQA schema)
# --------------------------------------------------------------------------- #
def load_2wiki(path: str, limit: int | None = None) -> RelationalDataset:
    """Load a 2WikiMultiHopQA split (``train``/``dev``) from its JSON file.

    Only examples that carry gold ``evidences`` are kept — those are the ones
    with an explicit relational chain to evaluate the engine against.
    """
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    examples: list[RelExample] = []
    for row in raw:
        evidences = row.get("evidences") or []
        if not evidences:
            continue
        ctx = tuple(
            (title, " ".join(sents)) for title, sents in row.get("context", [])
        )
        examples.append(
            RelExample(
                qid=str(row.get("_id", len(examples))),
                question=row["question"],
                answer=row["answer"],
                qtype=row.get("type", "unknown"),
                evidences=tuple((s, r, o) for s, r, o in evidences),
                context=ctx,
            )
        )
        if limit is not None and len(examples) >= limit:
            break
    return RelationalDataset(name="2wikimultihop", examples=examples)


# --------------------------------------------------------------------------- #
# Strong lexical baseline: Okapi BM25 over paragraph text
# --------------------------------------------------------------------------- #
class BM25Retriever:
    """Okapi BM25 (k1=1.5, b=0.75) over per-entity paragraph text.

    BM25 is the standard strong lexical baseline for passage retrieval — a far
    more honest comparison than raw TF-IDF. It retrieves the entity whose
    paragraph best lexically matches the question; it has no notion of typed,
    directed edges, so multi-hop answers that are never lexically adjacent to the
    question are exactly what it cannot reach.
    """

    name = "bm25"

    def __init__(self, docs: dict[str, str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self._ids = list(docs)
        toks = [_tokenize(docs[i]) for i in self._ids]
        self._len = [len(t) for t in toks]
        self._avglen = (sum(self._len) / len(self._len)) if self._len else 0.0
        self._tf = [Counter(t) for t in toks]
        df: Counter[str] = Counter()
        for t in self._tf:
            df.update(t.keys())
        n = max(len(self._ids), 1)
        # BM25 idf with the +0.5 smoothing, floored at a small positive value.
        self._idf = {
            term: max(1e-6, math.log((n - d + 0.5) / (d + 0.5) + 1.0))
            for term, d in df.items()
        }

    def retrieve_ids(self, question: str, k: int) -> list[Retrieved]:
        q = _tokenize(question)
        scored: list[Retrieved] = []
        for i, tf in enumerate(self._tf):
            dl = self._len[i] or 1
            s = 0.0
            for term in q:
                if term not in tf:
                    continue
                f = tf[term]
                denom = f + self.k1 * (1 - self.b + self.b * dl / (self._avglen or 1))
                s += self._idf.get(term, 0.0) * (f * (self.k1 + 1)) / denom
            if s > 0:
                scored.append(Retrieved(self._ids[i], s))
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:k]


# --------------------------------------------------------------------------- #
# Build the knowledge graph from gold evidence triples
# --------------------------------------------------------------------------- #
def _slug(relation: str) -> str:
    return re.sub(r"\s+", "_", relation.strip().lower())


def build_graph(dataset: RelationalDataset):
    """Construct one global CookiX graph from every example's gold triples.

    Building a *single* graph (not one per question) is what makes this a real
    retrieval task: traversal from an anchor must find the right multi-hop path
    among the distractor edges contributed by every other example.

    Returns ``(db, entity_text)`` where ``entity_text`` maps each entity key to
    its paragraph text — the shared corpus BM25 ranks over, so both retrievers
    see identical content.
    """
    entity_text: dict[str, str] = {}
    for ex in dataset.examples:
        for title, text in ex.context:
            key = normalise_entity(title)
            if text and (key not in entity_text or len(text) > len(entity_text[key])):
                entity_text[key] = text

    # Collect typed edges between normalised entity keys.
    edges: dict[str, list[tuple[str, str]]] = defaultdict(list)
    nodes: set[str] = set(entity_text)
    for ex in dataset.examples:
        for s, r, o in ex.evidences:
            sk, ok = normalise_entity(s), normalise_entity(o)
            nodes.add(sk)
            nodes.add(ok)
            edges[sk].append((_slug(r), ok))

    db = connect(dataset.name)
    docs = []
    for key in nodes:
        seen: set[tuple[str, str]] = set()
        uniq = []
        for rel, tgt in edges.get(key, []):
            if (rel, tgt) not in seen:
                seen.add((rel, tgt))
                uniq.append((rel, tgt))
        docs.append(
            {"_id": key, "content": entity_text.get(key, key), "edges": uniq}
        )
    db.insert_many(docs)
    return db, entity_text


# --------------------------------------------------------------------------- #
# Experiment
# --------------------------------------------------------------------------- #
@dataclass
class DatasetScore:
    name: str
    n: int
    overall: dict[str, float]
    by_type: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class DatasetReport:
    dataset: str
    n_examples: int
    n_evaluable: int
    k: int
    type_counts: dict[str, int]
    scores: list[DatasetScore]
    note: str = ""


def _answer_key(ex: RelExample) -> str:
    return normalise_entity(ex.answer)


def _evaluable(ex: RelExample, nodes: set[str]) -> bool:
    """Keep examples whose answer is a graph entity and whose anchor exists.

    Comparison questions with yes/no answers are excluded — they are not an
    entity-retrieval target — and we report how many were dropped.
    """
    a = ex.anchor
    return (
        a is not None
        and normalise_entity(a) in nodes
        and _answer_key(ex) in nodes
    )


def run_dataset_eval(
    dataset: RelationalDataset,
    k: int = 10,
    modes: tuple[str, ...] = ("graph", "reasoning"),
    max_hops: int = 4,
) -> DatasetReport:
    """Score CookiX traversal vs BM25 on multi-hop answer-entity retrieval.

    For each evaluable example: BM25 ranks all entities by the question text;
    CookiX traverses from the oracle anchor and ranks reachable entities. We
    measure whether the gold answer entity appears in the top-``k`` (hits/MRR),
    and for CookiX additionally whether the recovered path's relation sequence
    matches the gold chain (``path_match`` — something BM25 cannot score).
    """
    db, entity_text = build_graph(dataset)
    nodes = set(entity_text) | {
        normalise_entity(x) for ex in dataset.examples
        for s, _, o in ex.evidences for x in (s, o)
    }
    evaluable = [ex for ex in dataset.examples if _evaluable(ex, nodes)]

    bm25 = BM25Retriever({key: entity_text.get(key, key) for key in nodes})

    rows: dict[str, _Acc] = {"bm25": _Acc()}
    for m in modes:
        rows[f"cookix-{m}"] = _Acc()

    for ex in evaluable:
        gold = _answer_key(ex)
        anchor = normalise_entity(ex.anchor) if ex.anchor else None

        bm = bm25.retrieve_ids(ex.question, k)
        rows["bm25"].add(ex, _hit(bm, gold, k), _mrr(bm, gold), path_match=None)

        for m in modes:
            results = db.query(anchor=anchor, k=k, mode=m, max_hops=max_hops)
            ranked = [Retrieved(r.object_id, -r.score) for r in results]
            pm = _path_match(results, gold, ex.gold_relations)
            rows[f"cookix-{m}"].add(ex, _hit(ranked, gold, k), _mrr(ranked, gold), pm)

    scores = [
        DatasetScore(name=name, n=len(evaluable),
                     overall=acc.means(), by_type=acc.by_type())
        for name, acc in rows.items()
    ]
    note = (
        "Oracle entity-linking setting: CookiX is given the question's head "
        "entity as anchor and traverses the gold-evidence knowledge graph; BM25 "
        "ranks the same paragraphs by the raw question. This measures the "
        "relational reasoning engine, not free-text extraction (see "
        "`cookix eval --extraction` for that, separately)."
    )
    return DatasetReport(
        dataset=dataset.name,
        n_examples=len(dataset),
        n_evaluable=len(evaluable),
        k=k,
        type_counts=dataset.type_counts(),
        scores=scores,
        note=note,
    )


# --------------------------------------------------------------------------- #
# Scoring helpers
# --------------------------------------------------------------------------- #
def _hit(ranked: list[Retrieved], gold: str, k: int) -> float:
    return 1.0 if any(r.object_id == gold for r in ranked[:k]) else 0.0


def _mrr(ranked: list[Retrieved], gold: str) -> float:
    for i, r in enumerate(ranked, start=1):
        if r.object_id == gold:
            return 1.0 / i
    return 0.0


def _path_match(results, gold: str, gold_relations: tuple[str, ...]) -> float | None:
    """1.0 if CookiX reached the answer via the gold relation sequence.

    Only a path-returning retriever can score this; BM25 gets ``None`` (n/a).
    """
    gold_slugs = tuple(_slug(r) for r in gold_relations)
    for r in results:
        if r.object_id == gold:
            chain = tuple(s.relation for s in r.path)
            return 1.0 if chain == gold_slugs else 0.0
    return 0.0


@dataclass
class _Acc:
    _sums: dict[str, float] = field(default_factory=dict)
    _counts: dict[str, int] = field(default_factory=dict)
    _by_type: dict[str, dict[str, float]] = field(default_factory=dict)
    _type_n: dict[str, int] = field(default_factory=dict)

    def add(self, ex: RelExample, hit: float, mrr: float, path_match: float | None) -> None:
        self._bump("hits@k", hit)
        self._bump("mrr", mrr)
        if path_match is not None:
            self._bump("path_match", path_match)
        t = ex.qtype
        self._type_n[t] = self._type_n.get(t, 0) + 1
        bucket = self._by_type.setdefault(t, {})
        bucket["hits@k"] = bucket.get("hits@k", 0.0) + hit

    def _bump(self, key: str, value: float) -> None:
        self._sums[key] = self._sums.get(key, 0.0) + value
        self._counts[key] = self._counts.get(key, 0) + 1

    def means(self) -> dict[str, float]:
        return {k: self._sums[k] / self._counts[k] for k in self._sums if self._counts[k]}

    def by_type(self) -> dict[str, dict[str, float]]:
        return {
            t: {"hits@k": vals.get("hits@k", 0.0) / self._type_n[t]}
            for t, vals in self._by_type.items() if self._type_n.get(t)
        }


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def to_markdown_dataset(report: DatasetReport) -> str:
    metrics = ["hits@k", "mrr", "path_match"]
    lines = [
        f"### External dataset: `{report.dataset}`",
        "",
        f"{report.n_examples} examples with gold chains · "
        f"{report.n_evaluable} evaluable (answer is a graph entity) · k={report.k}",
        "",
        "| retriever | " + " | ".join(metrics) + " |",
        "|" + "---|" * (len(metrics) + 1),
    ]
    for s in report.scores:
        cells = [s.name]
        for m in metrics:
            v = s.overall.get(m)
            cells.append(f"{v:.3f}" if v is not None else "n/a")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append(f"_{report.note}_")
    return "\n".join(lines)
