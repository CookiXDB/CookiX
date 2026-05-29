from __future__ import annotations

import pytest

from cookix import API_VERSION, CookixClient, CookixError

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from cookix.demos import umbrella_db  # noqa: E402
from cookix.server import ServerConfig, create_app  # noqa: E402


def _client(config: ServerConfig | None = None, api_key: str | None = None) -> CookixClient:
    """A CookixClient whose transport is backed by an in-process TestClient."""
    test_client = TestClient(create_app(umbrella_db(), config))

    def transport(method, path, payload, headers):
        resp = test_client.request(method, path, json=payload, headers=headers)
        body = resp.json() if resp.content else {}
        return resp.status_code, body

    return CookixClient("http://test", api_key=api_key, transport=transport)


def test_info_reports_api_version():
    info = _client().info()
    assert info["name"] == "CookiX"
    assert info["api_version"] == API_VERSION


def test_health():
    assert _client().health() is True


def test_query_returns_paths():
    results = _client().query("what prevents rain?", mode="reasoning")
    assert results[0]["object_id"] == "umbrella"
    assert results[0]["path"][0]["relation"] == "prevents"


def test_insert_then_query():
    client = _client()
    oid = client.insert({"_id": "galoshes", "content": "boots",
                         "edges": [("prevents", "wet_coat")]})
    assert oid == "galoshes"
    res = client.query(anchor="galoshes", relation="prevents", mode="graph")
    assert res[0]["object_id"] == "wet_coat"


def test_graph_shape():
    g = _client().graph()
    assert {"nodes", "edges"} <= g.keys()


def test_auth_error_raises_cookix_error():
    secured = ServerConfig(api_key="s3cret")
    # Wrong key -> 401 -> CookixError.
    with pytest.raises(CookixError) as exc:
        _client(config=secured, api_key="wrong").graph()
    assert exc.value.status == 401
    # Correct key works.
    assert "nodes" in _client(config=secured, api_key="s3cret").graph()
