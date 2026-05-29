"""Operational hardening for the CookiX HTTP server.

The embedded library is the primary, trusted interface. The moment CookiX is
exposed over HTTP it needs the controls any production service does, so this
module adds them as **opt-in** layers (all default to off, so the demo UI and the
existing test suite keep working unchanged):

* **Authentication** — an optional API key (``Authorization: Bearer <key>`` or
  ``X-API-Key``), compared in constant time. When set, the data endpoints require it.
* **Rate limiting** — a fixed-window per-client limiter (keyed by API key, else
  client host) returning ``429`` with ``Retry-After``.
* **Resource limits** — a request body-size cap (``413``) and clamps on ``k`` and
  ``max_hops`` so a single query cannot ask the engine to do unbounded work.
* **Read-only mode** — reject all mutations with ``403`` for serving a frozen DB.
* **Observability** — structured JSON request logs, Prometheus-format ``/metrics``,
  and ``/healthz`` / ``/readyz`` probes.

Everything here is standard-library + Starlette (already a FastAPI dependency);
no new packages, no `prometheus_client`, so it ships with `cookix[server]` as-is.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger("cookix.server")


@dataclass
class ServerConfig:
    """Operational policy for the HTTP server. All protections default to off."""

    api_key: str | None = None
    rate_limit_rpm: int = 0          # requests/minute/client; 0 disables
    max_body_bytes: int = 1_000_000  # 1 MB request-body cap
    max_k: int = 100                 # upper bound on retrieval k
    max_hops_limit: int = 8          # upper bound on traversal depth
    read_only: bool = False          # reject mutations
    enable_metrics: bool = True

    @classmethod
    def from_env(cls) -> ServerConfig:
        """Build config from ``COOKIX_*`` environment variables."""
        def _int(name: str, default: int) -> int:
            raw = os.environ.get(name)
            return int(raw) if raw and raw.isdigit() else default

        return cls(
            api_key=os.environ.get("COOKIX_API_KEY") or None,
            rate_limit_rpm=_int("COOKIX_RATE_LIMIT_RPM", 0),
            max_body_bytes=_int("COOKIX_MAX_BODY_BYTES", 1_000_000),
            max_k=_int("COOKIX_MAX_K", 100),
            max_hops_limit=_int("COOKIX_MAX_HOPS", 8),
            read_only=os.environ.get("COOKIX_READ_ONLY", "").lower() in ("1", "true", "yes"),
            enable_metrics=os.environ.get("COOKIX_METRICS", "1").lower() not in ("0", "false"),
        )

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_key)


# --------------------------------------------------------------------------- #
# Metrics registry (Prometheus text exposition, no external dependency)
# --------------------------------------------------------------------------- #
@dataclass
class Metrics:
    _lock: threading.Lock = field(default_factory=threading.Lock)
    requests: dict[tuple[str, int], int] = field(default_factory=lambda: defaultdict(int))
    latency_sum_ms: float = 0.0
    latency_count: int = 0
    rate_limited: int = 0
    auth_failures: int = 0

    def observe(self, path: str, status: int, elapsed_ms: float) -> None:
        with self._lock:
            self.requests[(path, status)] += 1
            self.latency_sum_ms += elapsed_ms
            self.latency_count += 1

    def inc_rate_limited(self) -> None:
        with self._lock:
            self.rate_limited += 1

    def inc_auth_failure(self) -> None:
        with self._lock:
            self.auth_failures += 1

    def render_prometheus(self) -> str:
        with self._lock:
            lines = [
                "# HELP cookix_requests_total HTTP requests by path and status.",
                "# TYPE cookix_requests_total counter",
            ]
            for (path, status), count in sorted(self.requests.items()):
                safe = path.replace('"', "")
                lines.append(
                    f'cookix_requests_total{{path="{safe}",status="{status}"}} {count}'
                )
            avg = (self.latency_sum_ms / self.latency_count) if self.latency_count else 0.0
            lines += [
                "# HELP cookix_request_latency_ms_avg Mean request latency (ms).",
                "# TYPE cookix_request_latency_ms_avg gauge",
                f"cookix_request_latency_ms_avg {avg:.4f}",
                "# HELP cookix_rate_limited_total Requests rejected by the rate limiter.",
                "# TYPE cookix_rate_limited_total counter",
                f"cookix_rate_limited_total {self.rate_limited}",
                "# HELP cookix_auth_failures_total Requests rejected for bad credentials.",
                "# TYPE cookix_auth_failures_total counter",
                f"cookix_auth_failures_total {self.auth_failures}",
            ]
            return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Fixed-window rate limiter
# --------------------------------------------------------------------------- #
class RateLimiter:
    """Per-client fixed-window limiter: ``limit`` requests per 60-second window."""

    def __init__(self, limit_per_minute: int) -> None:
        self.limit = limit_per_minute
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[int, int]] = {}  # client -> (window_start, count)

    def check(self, client: str) -> tuple[bool, int]:
        """Return ``(allowed, retry_after_seconds)``."""
        if self.limit <= 0:
            return True, 0
        now = int(time.time())
        window = now - (now % 60)
        with self._lock:
            start, count = self._windows.get(client, (window, 0))
            if start != window:
                start, count = window, 0
            if count >= self.limit:
                return False, 60 - (now % 60)
            self._windows[client] = (start, count + 1)
            return True, 0


# --------------------------------------------------------------------------- #
# Helpers used by the app
# --------------------------------------------------------------------------- #
def check_api_key(provided: str | None, expected: str | None) -> bool:
    """Constant-time API-key comparison; ``True`` when auth is disabled."""
    if not expected:
        return True
    if not provided:
        return False
    return hmac.compare_digest(provided, expected)


def extract_key(headers) -> str | None:
    """Pull a bearer token or ``X-API-Key`` from request headers."""
    auth = headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return headers.get("x-api-key")


def log_request(method: str, path: str, status: int, elapsed_ms: float, client: str) -> None:
    """Emit a structured (JSON) access log line."""
    logger.info(json.dumps({
        "event": "request",
        "method": method,
        "path": path,
        "status": status,
        "ms": round(elapsed_ms, 2),
        "client": client,
    }))
