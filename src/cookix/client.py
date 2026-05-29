"""A typed Python client for the CookiX HTTP server.

The embedded library (``import cookix``) is the in-process interface. When CookiX
runs as a server (``cookix serve``), this client is the supported way to talk to
it from another Python process or service — a thin, dependency-free wrapper over
the stable wire API (see :data:`API_VERSION`).

It uses only the standard library (``urllib``), so it adds no dependencies. For
testing or advanced transports, pass ``transport=`` — any callable with the
signature ``(method, path, payload, headers) -> (status_code, json_dict)`` — so
the client can be driven against an in-process app without a real socket.

Example::

    from cookix.client import CookixClient

    db = CookixClient("http://localhost:8000", api_key="…")
    db.insert({"_id": "umbrella", "content": "umbrella", "edges": [("prevents", "rain")]})
    for r in db.query("what prevents rain?"):
        print(r["explain"])
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

# Wire-API version. Bumped only on a breaking change to request/response shapes;
# the server reports it at /api/info under "api_version". See API_STABILITY.md.
API_VERSION = "1"

Transport = Callable[[str, str, "dict | None", "dict[str, str]"], "tuple[int, dict]"]


class CookixError(RuntimeError):
    """Raised when the server returns a non-2xx response."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


class CookixClient:
    """Typed client over the CookiX HTTP API."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
        transport: Transport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._transport = transport or self._urllib_transport

    # ------------------------------------------------------------------ #
    # Transport
    # ------------------------------------------------------------------ #
    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _urllib_transport(
        self, method: str, path: str, payload: dict | None, headers: dict[str, str]
    ) -> tuple[int, dict]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                return resp.status, (json.loads(body) if body else {})
        except urllib.error.HTTPError as exc:  # non-2xx
            body = exc.read().decode("utf-8", "replace")
            try:
                return exc.code, json.loads(body)
            except json.JSONDecodeError:
                return exc.code, {"detail": body}

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        status, body = self._transport(method, path, payload, self._headers())
        if not (200 <= status < 300):
            detail = body.get("detail") if isinstance(body, dict) else body
            raise CookixError(status, str(detail))
        return body

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    def info(self) -> dict[str, Any]:
        """Server metadata: name, version, object count, modes, relations."""
        return self._request("GET", "/api/info")

    def health(self) -> bool:
        """True if the server's liveness probe responds OK."""
        try:
            return self._request("GET", "/healthz").get("status") == "ok"
        except CookixError:
            return False

    def insert(self, document: dict[str, Any]) -> str:
        """Insert a document; returns the object id."""
        return self._request("POST", "/api/insert", {"document": document})["id"]

    def query(
        self,
        query: str | None = None,
        *,
        anchor: str | None = None,
        relation: str | None = None,
        target: str | None = None,
        k: int = 5,
        mode: str = "reasoning",
        max_hops: int | None = None,
    ) -> list[dict[str, Any]]:
        """Run a relational query; returns ranked results with reasoning paths."""
        payload = {
            "query": query, "anchor": anchor, "relation": relation,
            "target": target, "k": k, "mode": mode, "max_hops": max_hops,
        }
        return self._request("POST", "/api/query", payload)["results"]

    def graph(self) -> dict[str, Any]:
        """The whole graph as ``{nodes, edges}`` for visualisation."""
        return self._request("GET", "/api/graph")
