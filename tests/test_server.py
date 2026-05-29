from __future__ import annotations

import pytest

# The server is an optional extra (`cookix[server]`). Skip the whole module if
# FastAPI or the httpx-backed test client are not installed.
pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from cookix.demos import umbrella_db  # noqa: E402
from cookix.server import create_app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(umbrella_db()))


def test_info(client: TestClient):
    info = client.get("/api/info").json()
    assert info["name"] == "CookiX"
    assert info["objects"] == 6
    assert "full" in info["modes"]


def test_graph(client: TestClient):
    g = client.get("/api/graph").json()
    ids = {n["id"] for n in g["nodes"]}
    assert {"umbrella", "rain", "wet_coat"} <= ids
    assert any(e["relation"] == "prevents" for e in g["edges"])


def test_query_inverse(client: TestClient):
    r = client.post("/api/query", json={"query": "what prevents rain?", "mode": "reasoning"}).json()
    assert [x["object_id"] for x in r["results"]] == ["umbrella"]
    assert r["results"][0]["path"][0]["relation"] == "prevents"


def test_query_multi_hop(client: TestClient):
    r = client.post(
        "/api/query", json={"anchor": "umbrella", "target": "wet_coat", "mode": "graph"}
    ).json()
    assert r["results"]
    assert [s["relation"] for s in r["results"][0]["path"]] == ["prevents", "causes"]


def test_insert(client: TestClient):
    resp = client.post(
        "/api/insert",
        json={"document": {"_id": "galoshes", "content": "boots", "edges": [("prevents", "wet_coat")]}},
    ).json()
    assert resp["id"] == "galoshes"
    assert client.get("/api/info").json()["objects"] == 7
