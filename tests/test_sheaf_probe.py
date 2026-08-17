"""Tests for the sheaf residual discrimination probe.

The probe's job is to be *hard to fool*, so these tests check the guards as much as
the happy path: that a degenerate fit is flagged rather than reported as a win, that
the identity control really does ignore relations, and that AUC is orientation-correct
(lower residual = more coherent).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from cookix.eval import load_2wiki, run_sheaf_probe, text_stalks, to_markdown_sheaf_probe
from cookix.eval.sheaf_probe import Chain, auc, corrupt, extract_chains, residual

FIXTURE = Path(__file__).parent / "fixtures" / "twowiki_sample.json"


def test_auc_orientation():
    # Positives scoring lower than negatives is a perfect result.
    assert auc([0.1, 0.2], [0.8, 0.9]) == 1.0
    assert auc([0.8, 0.9], [0.1, 0.2]) == 0.0
    assert auc([0.5], [0.5]) == 0.5


def test_auc_empty_is_nan():
    assert np.isnan(auc([], [0.1]))
    assert np.isnan(auc([0.1], []))


def test_text_stalks_are_content_derived_and_normalised():
    stalks = text_stalks(
        {"a": "polish film director warsaw", "b": "polish film director warsaw", "c": "coral reef marine biology"},
        dim=32,
    )
    assert set(stalks) == {"a", "b", "c"}
    for vec in stalks.values():
        assert vec.shape == (32,)
        assert np.isclose(np.linalg.norm(vec), 1.0)
    # Identical text must give identical stalks; different text must not.
    assert np.allclose(stalks["a"], stalks["b"])
    assert not np.allclose(stalks["a"], stalks["c"])


def test_text_stalks_skip_empty_text():
    stalks = text_stalks({"a": "", "b": "real words here"}, dim=8)
    assert "a" not in stalks
    assert "b" in stalks


def test_extract_chains_keeps_only_connected_evidence():
    ds = load_2wiki(str(FIXTURE))
    chains, edges = extract_chains(ds)
    assert edges, "fixture should yield edges"
    for chain in chains:
        # Each chain is a genuine path: consecutive triples must link up.
        for first, second in zip(chain.triples, chain.triples[1:], strict=False):
            assert first[2] == second[0]
        assert chain.source == chain.triples[0][0]
        assert chain.target == chain.triples[-1][2]
        assert chain.relations == tuple(r for _, r, _ in chain.triples)


def test_identity_maps_ignore_the_relation_chain():
    """The control must depend only on the endpoints - that is what makes it a control."""
    stalks = {"a": np.array([1.0, 0.0]), "b": np.array([0.0, 1.0])}
    eye = np.eye(2)
    one_hop = residual(Chain("a", ("causes",), "b"), stalks, lambda r: eye)
    other_rel = residual(Chain("a", ("prevents",), "b"), stalks, lambda r: eye)
    three_hop = residual(Chain("a", ("is_a", "part_of", "uses"), "b"), stalks, lambda r: eye)
    assert one_hop == other_rel == three_hop


def test_residual_is_none_when_a_stalk_is_missing():
    stalks = {"a": np.array([1.0, 0.0])}
    assert residual(Chain("a", ("causes",), "missing"), stalks, lambda r: np.eye(2)) is None


def test_corruptions_differ_from_the_gold_chain():
    gold = Chain(
        "a", ("director", "father"), "c",
        (("a", "director", "b"), ("b", "father", "c")),
    )
    adjacency = {"a": [("director", "b"), ("writer", "x")], "b": [("father", "c")], "x": [("father", "c")]}
    import random

    negatives = corrupt(
        gold,
        vocabulary=["director", "father", "writer", "spouse"],
        entities=["a", "b", "c", "x", "y"],
        adjacency=adjacency,
        rng=random.Random(0),
        max_hops=4,
    )
    assert negatives, "expected at least one corruption"
    for kind, bad in negatives.items():
        assert (bad.source, bad.relations, bad.target) != (
            gold.source, gold.relations, gold.target
        ), f"{kind} produced an uncorrupted chain"
    # Shuffle must preserve the multiset of relations but change their order.
    if "shuffle" in negatives:
        assert sorted(negatives["shuffle"].relations) == sorted(gold.relations)
        assert negatives["shuffle"].relations != gold.relations
    # A detour is a real alternative path between the same endpoints.
    if "detour" in negatives:
        assert negatives["detour"].source == gold.source
        assert negatives["detour"].target == gold.target
        assert negatives["detour"].relations != gold.relations


def test_probe_flags_a_degenerate_fit_instead_of_claiming_a_win():
    """The fixture is far too small to fit dim-64 maps; the verdict must say so."""
    ds = load_2wiki(str(FIXTURE))
    report = run_sheaf_probe(ds, dim=64, seed=0)
    assert report.degenerate
    assert report.verdict.startswith("UNRELIABLE")
    # A degenerate run must never be reported as evidence for the sheaf layer.
    assert "POSITIVE" not in report.verdict


def test_probe_report_renders_and_scores_all_three_map_families():
    ds = load_2wiki(str(FIXTURE))
    report = run_sheaf_probe(ds, dim=16, seed=0)
    assert {s.name for s in report.scores} == {"placeholder", "identity", "learned"}
    text = to_markdown_sheaf_probe(report)
    assert "Sheaf residual discrimination probe" in text
    assert "Verdict:" in text
    assert text.isascii(), "report must be ASCII-safe for Windows consoles"


def test_probe_is_deterministic():
    ds = load_2wiki(str(FIXTURE))
    a = run_sheaf_probe(ds, dim=16, seed=7)
    b = run_sheaf_probe(ds, dim=16, seed=7)
    assert [s.pooled_auc for s in a.scores] == [s.pooled_auc for s in b.scores]


def test_test_chain_edges_are_withheld_from_map_learning(tmp_path):
    """Strict split: no triple scored at test time may appear in the training edges."""
    rows = []
    for i in range(40):
        a, b, c = f"Ent A{i}", f"Ent B{i}", f"Ent C{i}"
        rows.append({
            "_id": f"ex{i}",
            "question": f"q{i}",
            "answer": c,
            "type": "compositional",
            "context": [
                [a, [f"{a} is a film directed by {b} in the year {1980 + i}."]],
                [b, [f"{b} is a director born in {1940 + i} in some city."]],
                [c, [f"{c} is a writer and the parent of {b}."]],
            ],
            "evidences": [[a, "director", b], [b, "father", c]],
        })
    path = tmp_path / "synth.json"
    path.write_text(json.dumps(rows), encoding="utf-8")

    ds = load_2wiki(str(path))
    report = run_sheaf_probe(ds, dim=8, seed=1)
    assert report.n_test_chains > 0
    assert report.n_train_edges > 0
    assert report.median_edges_per_relation > 0
