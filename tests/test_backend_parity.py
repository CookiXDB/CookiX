"""Behavioural parity between the in-memory and Kùzu backends.

The query engine depends only on the :class:`StorageBackend` contract, so every
backend must agree on the same observable behaviour. These tests run the same
battery against each backend. The Kùzu cases are skipped automatically when the
optional ``kuzu`` package is not installed (e.g. local dev), and exercised in CI
where it is.
"""

from __future__ import annotations

import pytest

import cookix


def _make_db(backend: str, tmp_path):
    if backend == "kuzu":
        pytest.importorskip("kuzu")
        return cookix.connect(str(tmp_path / "kuzu_db"), backend="kuzu")
    return cookix.connect(backend="memory")


BACKENDS = ["memory", "kuzu"]


@pytest.fixture(params=BACKENDS)
def db(request, tmp_path):
    database = _make_db(request.param, tmp_path)
    yield database
    database.storage.close()


def test_insert_get_contains_len(db):
    db.insert({"_id": "umbrella", "content": "an umbrella", "edges": [("prevents", "rain")]})
    assert "umbrella" in db
    obj = db.get("umbrella")
    assert obj is not None and obj.content == "an umbrella"
    assert obj.edges[0].relation == "prevents" and obj.edges[0].target == "rain"
    # A dangling edge target is NOT a materialised object.
    assert len(db) == 1
    assert "rain" not in db
    assert db.get("rain") is None


def test_dangling_target_is_traversable_then_materialisable(db):
    db.insert({"_id": "umbrella", "content": "umbrella", "edges": [("prevents", "rain")]})
    # Traversable as an endpoint even while dangling.
    assert db.storage.out_edges("umbrella")[0].target == "rain"
    assert db.storage.in_edges("rain") == [("umbrella", db.storage.in_edges("rain")[0][1])]
    # Materialising the target must preserve the incoming edge (the hardening fix).
    db.insert({"_id": "rain", "content": "the rain", "edges": [("causes", "wet_coat")]})
    assert "rain" in db and len(db) == 2
    in_edges = db.storage.in_edges("rain")
    assert [(s, e.relation) for s, e in in_edges] == [("umbrella", "prevents")]


def test_put_replaces_only_outgoing_edges(db):
    db.insert({"_id": "a", "content": "a", "edges": [("causes", "b"), ("causes", "c")]})
    # Re-inserting with different out-edges replaces them, not incoming ones.
    db.insert({"_id": "z", "content": "z", "edges": [("requires", "a")]})
    db.insert({"_id": "a", "content": "a2", "edges": [("prevents", "d")]})
    out = {(e.relation, e.target) for e in db.storage.out_edges("a")}
    assert out == {("prevents", "d")}
    assert [(s, e.relation) for s, e in db.storage.in_edges("a")] == [("z", "requires")]


def test_delete(db):
    db.insert({"_id": "x", "content": "x", "edges": [("causes", "y")]})
    assert db.delete("x") is True
    assert "x" not in db
    assert db.delete("x") is False


def test_multi_hop_query_parity(db):
    db.insert({"_id": "umbrella", "content": "umbrella", "edges": [("prevents", "rain")]})
    db.insert({"_id": "rain", "content": "rain", "edges": [("causes", "wet_coat")]})
    db.insert({"_id": "wet_coat", "content": "wet coat"})
    results = db.query(anchor="umbrella", target="wet_coat", mode="graph")
    assert results and results[0].object_id == "wet_coat"
    assert [s.relation for s in results[0].path] == ["prevents", "causes"]


def test_inverse_relation_query_parity(db):
    db.insert({"_id": "umbrella", "content": "umbrella", "edges": [("prevents", "rain")]})
    db.insert({"_id": "rain", "content": "rain"})
    results = db.query("what prevents rain?", mode="graph")
    assert [r.object_id for r in results] == ["umbrella"]
