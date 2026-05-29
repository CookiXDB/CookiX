from __future__ import annotations

import numpy as np

from cookix.topology import TopoIndex, recall_at_k


def _clustered_signatures(n_clusters=8, per_cluster=20, dim=32, seed=0):
    """Signatures drawn from tight clusters, so nearest neighbours are well-defined."""
    rng = np.random.default_rng(seed)
    sigs: dict[str, np.ndarray] = {}
    centres = rng.standard_normal((n_clusters, dim))
    for c in range(n_clusters):
        for i in range(per_cluster):
            v = np.abs(centres[c] + 0.05 * rng.standard_normal(dim))  # signatures are histograms (>=0)
            sigs[f"c{c}_{i}"] = v
    return sigs, centres


def test_exact_query_finds_self_first():
    sigs, _ = _clustered_signatures()
    idx = TopoIndex(seed=0)
    idx.add_many(sigs)
    obj_id, sig = next(iter(sigs.items()))
    top = idx.query_exact(sig, k=1)
    assert top[0][0] == obj_id
    assert top[0][1] > 0.99  # a signature is maximally similar to itself


def test_query_returns_same_cluster_neighbours():
    sigs, _ = _clustered_signatures()
    idx = TopoIndex(seed=0)
    idx.add_many(sigs)
    results = idx.query(sigs["c3_0"], k=5, probe_radius=2)
    assert results
    # Top neighbours should overwhelmingly come from the same cluster.
    same = sum(1 for oid, _ in results if oid.startswith("c3_"))
    assert same >= 4


def test_lsh_recall_is_high_on_clustered_data():
    sigs, _ = _clustered_signatures()
    idx = TopoIndex(n_planes=12, seed=0)
    idx.add_many(sigs)
    queries = [sigs[f"c{c}_0"] for c in range(8)]
    recall = recall_at_k(idx, queries, k=5, probe_radius=2)
    assert recall >= 0.8  # approximate, but should recover most exact neighbours


def test_index_is_deterministic():
    sigs, _ = _clustered_signatures()
    a, b = TopoIndex(seed=7), TopoIndex(seed=7)
    a.add_many(sigs)
    b.add_many(sigs)
    q = sigs["c1_0"]
    assert a.query(q, k=5) == b.query(q, k=5)


def test_empty_index_returns_nothing():
    idx = TopoIndex()
    assert idx.query(np.ones(16), k=5) == []
    assert len(idx) == 0


def test_dim_mismatch_raises():
    idx = TopoIndex()
    idx.add("a", np.ones(8))
    try:
        idx.add("b", np.ones(16))
    except ValueError as exc:
        assert "dim" in str(exc)
    else:
        raise AssertionError("expected ValueError on dimension mismatch")


def test_probe_radius_zero_subset_of_exact():
    sigs, _ = _clustered_signatures()
    idx = TopoIndex(seed=0)
    idx.add_many(sigs)
    q = sigs["c2_0"]
    approx_ids = {oid for oid, _ in idx.query(q, k=5, probe_radius=0)}
    exact_ids = {oid for oid, _ in idx.query_exact(q, k=len(sigs))}
    assert approx_ids <= exact_ids  # LSH never invents non-members
