from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from cookix.demos import umbrella_db  # noqa: E402
from cookix.server import ServerConfig, create_app, serve  # noqa: E402


def _client(config):
    return TestClient(create_app(umbrella_db(), config))


# --------------------------------------------------------------------------- #
# Role resolution (unit)
# --------------------------------------------------------------------------- #
def test_role_for_resolves_and_hierarchy():
    cfg = ServerConfig(api_keys={"r": "read", "w": "write", "a": "admin"})
    assert cfg.role_for("r") == "read"
    assert cfg.role_for("bogus") is None
    assert cfg.has_role("w", "read") is True       # write implies read
    assert cfg.has_role("r", "write") is False     # read cannot write
    assert cfg.has_role("a", "write") is True      # admin implies all


def test_single_api_key_is_admin_shorthand():
    cfg = ServerConfig(api_key="solo")
    assert cfg.role_for("solo") == "admin"
    assert cfg.has_role("solo", "write") is True


# --------------------------------------------------------------------------- #
# Role enforcement over HTTP
# --------------------------------------------------------------------------- #
def test_read_key_can_query_but_not_insert():
    client = _client(ServerConfig(api_keys={"ro": "read", "rw": "write"}))

    # Read key: query (read) OK, insert (write) forbidden.
    q = client.post("/api/query", json={"anchor": "umbrella", "mode": "graph"},
                    headers={"X-API-Key": "ro"})
    assert q.status_code == 200
    ins = client.post("/api/insert", json={"_id": "x", "content": "x"},
                      headers={"X-API-Key": "ro"})
    assert ins.status_code == 403

    # Write key: insert OK.
    ok = client.post("/api/insert", json={"_id": "y", "content": "y"},
                     headers={"X-API-Key": "rw"})
    assert ok.status_code == 200


def test_unknown_key_is_401():
    client = _client(ServerConfig(api_keys={"ro": "read"}))
    assert client.get("/api/graph", headers={"X-API-Key": "nope"}).status_code == 401


# --------------------------------------------------------------------------- #
# Secure-by-default binding
# --------------------------------------------------------------------------- #
def test_serve_refuses_public_bind_without_auth():
    with pytest.raises(RuntimeError, match="refusing to bind"):
        serve(db=umbrella_db(), host="0.0.0.0", config=ServerConfig())


def test_serve_allows_public_bind_with_auth_or_override(monkeypatch):
    # We don't actually start uvicorn; assert the guard passes by stubbing run.
    import cookix.server.app as appmod

    started = {}

    def fake_run(app, host, port):
        started["ok"] = True

    monkeypatch.setattr(appmod, "create_app", lambda db, cfg: object())
    import uvicorn
    monkeypatch.setattr(uvicorn, "run", fake_run)

    # With auth configured, a public bind is permitted.
    serve(db=umbrella_db(), host="0.0.0.0", config=ServerConfig(api_key="k"))
    assert started.get("ok") is True
