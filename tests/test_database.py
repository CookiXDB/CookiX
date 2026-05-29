from __future__ import annotations

import cookix
from cookix.demos import pipe_db, umbrella_db


def test_insert_and_get():
    db = cookix.connect()
    obj_id = db.insert({"_id": "umbrella", "content": "umbrella", "edges": [("prevents", "rain")]})
    assert obj_id == "umbrella"
    assert "umbrella" in db
    assert len(db) == 1  # only explicitly-inserted objects count; 'rain' is a dangling target
    assert db.get("rain") is None  # referenced but not yet inserted
    obj = db.get("umbrella")
    assert obj is not None and obj.edges[0].relation == "prevents"


def test_direct_single_hop_query():
    db = umbrella_db()
    results = db.query(anchor="umbrella", relation="prevents")
    assert [r.object_id for r in results] == ["rain"]
    assert results[0].score == 0.0  # exact typed match


def test_multi_hop_reasoning_path():
    db = umbrella_db()
    results = db.query(anchor="umbrella", target="wet_coat", mode="graph")
    assert results, "expected a reasoning path to wet_coat"
    best = results[0]
    assert best.object_id == "wet_coat"
    relations = [s.relation for s in best.path]
    assert relations == ["prevents", "causes"]


def test_natural_language_intent_parsing():
    db = pipe_db()
    results = db.query("is pipe_120mm compatible with pipe_130mm?", mode="graph")
    ids = [r.object_id for r in results]
    assert "pipe_130mm" in ids


def test_delete():
    db = umbrella_db()
    assert db.delete("storm") is True
    assert "storm" not in db
    assert db.delete("storm") is False


def test_update_adds_edges():
    db = cookix.connect()
    db.insert({"_id": "a", "content": "a"})
    db.insert({"_id": "b", "content": "b"})
    assert db.update("a", add_edges=[("causes", "b")]) is True
    results = db.query(anchor="a", relation="causes")
    assert results[0].object_id == "b"


def test_contradiction_detection():
    db = pipe_db()
    results = db.contradictions("steel_pipe")
    assert any(r.object_id == "iso_4422" for r in results)


def test_ingest_free_text():
    db = cookix.connect()
    ids = db.insert_text("aspirin prevents clotting. warfarin contradicts aspirin.")
    assert ids  # produced some objects
    # 'aspirin' should have a 'prevents' edge
    obj = db.get("aspirin")
    assert obj is not None
    assert any(e.relation == "prevents" for e in obj.edges)
