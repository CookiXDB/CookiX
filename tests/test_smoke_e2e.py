"""End-to-end production smoke test.

Exercises the pieces a real deployment uses *together*: the durable backend, the
HTTP server with auth, the typed client, a server restart with crash recovery,
and a perf-regression guardrail. If this passes, the production path works.
"""

from __future__ import annotations

import time

import pytest

from cookix import connect
from cookix.storage.durable import DurableBackend

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from cookix.client import CookixClient  # noqa: E402
from cookix.server import ServerConfig, create_app  # noqa: E402


def _client_for(db, api_key=None):
    cfg = ServerConfig(api_key=api_key) if api_key else None
    test_client = TestClient(create_app(db, cfg))

    def transport(method, path, payload, headers):
        resp = test_client.request(method, path, json=payload, headers=headers)
        return resp.status_code, (resp.json() if resp.content else {})

    return CookixClient("http://test", api_key=api_key, transport=transport)


def test_durable_server_client_and_recovery(tmp_path):
    db_path = tmp_path / "prod_db"

    # 1. Stand up a durable-backed, authenticated server and talk to it via the
    #    typed client.
    db = connect(str(db_path), backend="durable")
    api = _client_for(db, api_key="prod-key")

    assert api.info()["api_version"] == "1"
    assert api.health() is True

    # 2. Ingest a small relational graph through the HTTP path.
    api.insert({"_id": "umbrella", "content": "umbrella", "edges": [("prevents", "rain")]})
    api.insert({"_id": "rain", "content": "rain", "edges": [("causes", "wet_coat")]})
    api.insert({"_id": "wet_coat", "content": "a wet coat"})

    # 3. Multi-hop reasoning over the wire returns the justified path.
    results = api.query(anchor="umbrella", target="wet_coat", mode="graph")
    assert results[0]["object_id"] == "wet_coat"
    assert [s["relation"] for s in results[0]["path"]] == ["prevents", "causes"]

    # 4. Simulate a crash (release the WAL handle without a clean shutdown) and
    #    reopen — committed data must survive.
    db.storage._wal.close()
    reopened = connect(str(db_path), backend="durable")
    assert len(reopened) == 3
    again = reopened.query(anchor="umbrella", target="wet_coat", mode="graph")
    assert again[0].object_id == "wet_coat"


def test_auth_is_enforced_end_to_end(tmp_path):
    db = connect(str(tmp_path / "db"), backend="durable")
    from cookix import CookixError

    unauth = _client_for(db, api_key=None)  # client sends no key
    # Server requires a key, client has none -> rejected.
    secured = TestClient(create_app(db, ServerConfig(api_key="k")))

    def transport(method, path, payload, headers):
        resp = secured.request(method, path, json=payload, headers=headers)
        return resp.status_code, (resp.json() if resp.content else {})

    unauth._transport = transport
    with pytest.raises(CookixError) as exc:
        unauth.graph()
    assert exc.value.status == 401


def test_perf_regression_guardrail():
    """A generous latency ceiling that catches catastrophic regressions only.

    Not a benchmark (CI machines vary) — a single small multi-hop query must
    complete well under 100 ms. If this trips, something is algorithmically wrong
    (e.g. settle-once traversal regressed into re-expansion).
    """
    db = connect("guardrail")
    for i in range(200):
        db.insert({"_id": f"n{i}", "content": f"node {i}",
                   "edges": [("causes", f"n{(i + 1) % 200}")]})
    start = time.perf_counter()
    db.query(anchor="n0", target="n50", mode="graph")
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert elapsed_ms < 100.0, f"query took {elapsed_ms:.1f} ms (regression?)"


def test_backup_and_restore_for_disaster_recovery(tmp_path):
    db = connect(str(tmp_path / "live"), backend="durable")
    for i in range(10):
        db.insert({"_id": f"n{i}", "content": f"n{i}", "edges": [("causes", f"n{(i + 1) % 10}")]})
    backup = tmp_path / "backup.pkl"
    db.storage.backup(backup)

    restored = DurableBackend.restore(backup, tmp_path / "restored")
    assert set(restored.all_ids()) == {f"n{i}" for i in range(10)}
