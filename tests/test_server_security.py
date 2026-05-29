from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from cookix.demos import umbrella_db  # noqa: E402
from cookix.server import ServerConfig, create_app  # noqa: E402
from cookix.server.security import RateLimiter, check_api_key  # noqa: E402


# --------------------------------------------------------------------------- #
# Unit: primitives
# --------------------------------------------------------------------------- #
def test_api_key_check_is_permissive_when_unset():
    assert check_api_key(None, None) is True
    assert check_api_key("anything", None) is True


def test_api_key_check_requires_exact_match():
    assert check_api_key("secret", "secret") is True
    assert check_api_key("wrong", "secret") is False
    assert check_api_key(None, "secret") is False


def test_rate_limiter_blocks_after_limit():
    rl = RateLimiter(limit_per_minute=2)
    assert rl.check("c")[0] is True
    assert rl.check("c")[0] is True
    allowed, retry = rl.check("c")
    assert allowed is False and 0 < retry <= 60
    # A different client has its own budget.
    assert rl.check("other")[0] is True


# --------------------------------------------------------------------------- #
# Integration: auth
# --------------------------------------------------------------------------- #
def test_open_server_allows_data_endpoints():
    client = TestClient(create_app(umbrella_db()))
    assert client.get("/api/graph").status_code == 200


def test_auth_required_when_key_set():
    client = TestClient(create_app(umbrella_db(), ServerConfig(api_key="s3cret")))
    assert client.get("/api/graph").status_code == 401
    ok = client.get("/api/graph", headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200
    ok2 = client.get("/api/graph", headers={"X-API-Key": "s3cret"})
    assert ok2.status_code == 200
    assert client.get("/api/graph", headers={"X-API-Key": "nope"}).status_code == 401


def test_health_and_metrics_need_no_auth():
    client = TestClient(create_app(umbrella_db(), ServerConfig(api_key="s3cret")))
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/readyz").json()["status"] == "ready"
    assert client.get("/metrics").status_code == 200


# --------------------------------------------------------------------------- #
# Integration: limits, read-only, metrics
# --------------------------------------------------------------------------- #
def test_read_only_rejects_inserts():
    client = TestClient(create_app(umbrella_db(), ServerConfig(read_only=True)))
    r = client.post("/api/insert", json={"_id": "x", "content": "x"})
    assert r.status_code == 403


def test_body_size_limit():
    client = TestClient(create_app(umbrella_db(), ServerConfig(max_body_bytes=10)))
    r = client.post("/api/query", json={"query": "what prevents rain?" * 50})
    assert r.status_code == 413


def test_k_is_clamped_to_max():
    client = TestClient(create_app(umbrella_db(), ServerConfig(max_k=3)))
    r = client.post("/api/query", json={"anchor": "umbrella", "mode": "graph", "k": 9999})
    assert r.status_code == 200
    assert len(r.json()["results"]) <= 3


def test_rate_limit_returns_429():
    client = TestClient(create_app(umbrella_db(), ServerConfig(rate_limit_rpm=2)))
    codes = [client.get("/healthz").status_code for _ in range(4)]
    assert 429 in codes


def test_metrics_report_request_counts():
    client = TestClient(create_app(umbrella_db()))
    client.get("/api/graph")
    body = client.get("/metrics").text
    assert "cookix_requests_total" in body
    assert "cookix_request_latency_ms_avg" in body


def test_invalid_document_is_rejected():
    client = TestClient(create_app(umbrella_db()))
    r = client.post("/api/insert", json={"document": "not-an-object"})
    assert r.status_code == 422
