from __future__ import annotations

from pathlib import Path

from cookix.eval.datasets import (
    BM25Retriever,
    build_graph,
    load_2wiki,
    normalise_entity,
    run_dataset_eval,
    to_markdown_dataset,
)

FIXTURE = str(Path(__file__).parent / "fixtures" / "twowiki_sample.json")


def test_loader_keeps_only_examples_with_evidence():
    ds = load_2wiki(FIXTURE)
    assert len(ds) == 3
    assert all(ex.evidences for ex in ds.examples)
    assert ds.type_counts()["compositional"] == 1


def test_anchor_and_gold_relations():
    ds = load_2wiki(FIXTURE)
    ex = next(e for e in ds.examples if e.qid == "ex_bridge_1")
    assert normalise_entity(ex.anchor) == "polish russian war film"
    assert ex.gold_relations == ("director", "father")


def test_graph_builds_typed_edges_from_triples():
    ds = load_2wiki(FIXTURE)
    db, text = build_graph(ds)
    director = db.get(normalise_entity("Polish-Russian War (film)"))
    assert director is not None
    rels = {(e.relation, e.target) for e in director.edges}
    assert ("director", normalise_entity("Xawery Zulawski")) in rels


def test_bm25_ranks_lexically_matching_paragraph_first():
    bm = BM25Retriever({
        "kabul": "Kabul is the capital and largest city of Afghanistan.",
        "coral": "An article about marine biology and coral reefs.",
    })
    top = bm.retrieve_ids("What is the capital of Afghanistan?", k=2)
    assert top[0].object_id == "kabul"


def test_cookix_traversal_recovers_multihop_answer():
    # The whole point: a 2-hop answer (director -> father) that is not lexically
    # adjacent to the question should be reachable by typed traversal.
    ds = load_2wiki(FIXTURE)
    report = run_dataset_eval(ds, k=10, modes=("graph",))
    cookix = next(s for s in report.scores if s.name == "cookix-graph")
    # Both bridge examples are evaluable (yes/no comparison answer is dropped).
    assert report.n_evaluable == 2
    assert cookix.overall["hits@k"] == 1.0  # traversal finds both answers
    # path_match is 0.5, not 1.0, and that is the honest result: the comparison
    # example injects a direct `boraq airlines --country--> afghanistan` edge into
    # the *global* graph, so bridge_2's answer is reached via that 1-hop shortcut
    # rather than its gold 2-hop chain. Strict gold-chain matching catches this —
    # exactly the distractor realism a single shared KG is meant to expose.
    assert cookix.overall["path_match"] == 0.5


def test_report_renders_markdown_with_both_retrievers():
    ds = load_2wiki(FIXTURE)
    md = to_markdown_dataset(run_dataset_eval(ds, k=10, modes=("graph", "reasoning")))
    assert "2wikimultihop" in md
    assert "bm25" in md
    assert "cookix-graph" in md
    assert "path_match" in md
    assert "Oracle entity-linking" in md
