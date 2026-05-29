from __future__ import annotations

import numpy as np

from cookix.model import Edge, KnowledgeObject, QueryResult, ReasoningStep


def test_edge_from_tuple_and_dict():
    e1 = Edge.from_any(("prevents", "rain"))
    assert e1.relation == "prevents" and e1.target == "rain" and e1.weight == 1.0

    e2 = Edge.from_any(("causes", "wet", 2.5))
    assert e2.weight == 2.5

    e3 = Edge.from_any({"relation": "is_a", "target": "thing", "weight": 0.5})
    assert e3.relation == "is_a" and e3.weight == 0.5


def test_knowledge_object_roundtrip():
    obj = KnowledgeObject(id="a", content="alpha", edges=[Edge("causes", "b")])
    obj.vector = np.array([1.0, 2.0, 3.0])
    doc = obj.to_dict()
    assert doc["_id"] == "a"
    assert doc["edges"][0]["relation"] == "causes"

    restored = KnowledgeObject.from_dict(doc)
    assert restored.id == "a"
    assert restored.content == "alpha"
    assert restored.edges[0].target == "b"
    assert np.allclose(restored.vector, [1.0, 2.0, 3.0])


def test_from_dict_accepts_text_and_id_aliases():
    obj = KnowledgeObject.from_dict({"id": "x", "text": "hello"})
    assert obj.id == "x" and obj.content == "hello"


def test_neighbors_filter():
    obj = KnowledgeObject(content="n", edges=[Edge("a", "1"), Edge("b", "2"), Edge("a", "3")])
    assert obj.neighbors("a") == ["1", "3"]
    assert set(obj.neighbors()) == {"1", "2", "3"}


def test_query_result_explain():
    result = QueryResult(
        object_id="coat",
        content="a coat",
        score=1.23,
        path=[ReasoningStep("umbrella", "prevents", "rain"),
              ReasoningStep("rain", "causes", "coat")],
        components={"geodesic": 2.0},
    )
    text = result.explain()
    assert "umbrella" in text and "prevents" in text and "rain" in text
    assert result.hops == 2
