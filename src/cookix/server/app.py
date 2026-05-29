"""HTTP server for CookiX: the substrate for non-Python clients and the UI.

The embedded library (``import cookix``) is the primary interface. This module
exposes the same operations over HTTP so a browser, or a non-Python service,
can talk to a CookiX database. It also serves the reasoning-path explorer UI,
which is the feature a vector database cannot offer: every answer comes with
the *path* that justifies it, rendered as an interactive graph.

Run with ``cookix serve`` (see :mod:`cookix.cli`).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np

from ..database import Database
from ..engine import RetrievalMode
from ..model import QueryResult
from .security import (
    Metrics,
    RateLimiter,
    ServerConfig,
    check_api_key,
    extract_key,
    log_request,
)

_STATIC_DIR = Path(__file__).parent / "static"


def _serialize_graph(db: Database) -> dict[str, Any]:
    """Whole-database graph for visualization: nodes + typed directed edges."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for obj_id in db.storage.all_ids():
        obj = db.storage.get(obj_id)
        nodes.append({"id": obj_id, "label": obj_id, "content": obj.content if obj else ""})
        for edge in db.storage.out_edges(obj_id):
            edges.append(
                {
                    "source": obj_id,
                    "target": edge.target,
                    "relation": edge.relation,
                    "weight": edge.weight,
                }
            )
    # Include dangling edge targets as light placeholder nodes so the graph
    # renders even when an edge points at an object that was never inserted.
    known = {n["id"] for n in nodes}
    for e in edges:
        if e["target"] not in known:
            nodes.append({"id": e["target"], "label": e["target"], "content": "", "dangling": True})
            known.add(e["target"])
    return {"nodes": nodes, "edges": edges}


def _sheaf_stalk(db: Database, obj_id: str, dim: int) -> Any:
    """The object's sheaf stalk at ``dim`` (its own if it matches, else default)."""
    from .. import sheaf

    obj = db.storage.get(obj_id)
    if obj is not None and obj.sheaf_stalk is not None and obj.sheaf_stalk.shape[0] == dim:
        return obj.sheaf_stalk
    return sheaf.default_stalk(obj_id, dim)


def _serialize_sheaf(db: Database, dim: int = 3) -> dict[str, Any]:
    """The sheaf as 3D geometry: each object's stalk is a unit vector on the sphere.

    At ``dim=3`` the restriction maps are 3x3 orthogonal matrices (rotations),
    so the whole sheaf is directly visualizable: objects are points on the unit
    sphere and relations rotate them. This is a *visualizable instance* of the
    same construction the engine runs at its configured ``sheaf_dim``.
    """
    nodes = []
    seen = set()
    edges = _serialize_graph(db)["edges"]
    for obj_id in db.storage.all_ids():
        nodes.append({"id": obj_id, "stalk": _sheaf_stalk(db, obj_id, dim).tolist()})
        seen.add(obj_id)
    for e in edges:
        if e["target"] not in seen:
            nodes.append({"id": e["target"], "stalk": _sheaf_stalk(db, e["target"], dim).tolist()})
            seen.add(e["target"])
    return {"dim": dim, "nodes": nodes, "edges": edges}


def _serialize_result(r: QueryResult) -> dict[str, Any]:
    return {
        "object_id": r.object_id,
        "content": r.content,
        "score": r.score,
        "hops": r.hops,
        "explain": r.explain(),
        "components": r.components,
        "path": [
            {"source": s.source, "relation": s.relation, "target": s.target, "weight": s.weight}
            for s in r.path
        ],
    }


def create_app(db: Database, config: ServerConfig | None = None) -> Any:
    """Build a FastAPI app bound to ``db``.

    Imported lazily so the core library has no hard dependency on FastAPI;
    ``cookix[server]`` installs it. Raises a helpful error if it is missing.

    ``config`` carries the operational policy (auth, rate limiting, resource
    limits, read-only, metrics). It defaults to :meth:`ServerConfig.from_env`, so
    all protections are off unless explicitly enabled — the demo UI just works.
    """
    try:
        from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request
        from fastapi.responses import FileResponse, PlainTextResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "The CookiX server requires extra dependencies. Install them with:\n"
            '    pip install "cookix[server]"'
        ) from exc

    cfg = config or ServerConfig.from_env()
    metrics = Metrics()
    limiter = RateLimiter(cfg.rate_limit_rpm)

    app = FastAPI(title="CookiX", version=_version())

    def _client(request: Request) -> str:
        key = extract_key(request.headers)
        if key:
            return f"key:{key[:8]}"
        return request.client.host if request.client else "unknown"

    @app.middleware("http")
    async def _ops_middleware(request: Request, call_next):
        start = time.perf_counter()
        client = _client(request)

        # Body-size cap (reject before reading the payload).
        clen = request.headers.get("content-length")
        if clen and clen.isdigit() and int(clen) > cfg.max_body_bytes:
            metrics.observe(request.url.path, 413, 0.0)
            return PlainTextResponse("request body too large", status_code=413)

        # Rate limit.
        allowed, retry = limiter.check(client)
        if not allowed:
            metrics.inc_rate_limited()
            elapsed = (time.perf_counter() - start) * 1000.0
            log_request(request.method, request.url.path, 429, elapsed, client)
            metrics.observe(request.url.path, 429, elapsed)
            return PlainTextResponse(
                "rate limit exceeded", status_code=429, headers={"Retry-After": str(retry)}
            )

        response = await call_next(request)
        elapsed = (time.perf_counter() - start) * 1000.0
        if cfg.enable_metrics:
            metrics.observe(request.url.path, response.status_code, elapsed)
        log_request(request.method, request.url.path, response.status_code, elapsed, client)
        return response

    def require_auth(
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None),
    ) -> None:
        """FastAPI dependency: enforce the API key on protected endpoints.

        Reads the key from ``Authorization: Bearer <key>`` or ``X-API-Key``. Uses
        header parameters (not the raw Request) so the annotation resolves cleanly
        under ``from __future__ import annotations``.
        """
        if not cfg.auth_enabled:
            return
        provided = None
        if authorization and authorization.lower().startswith("bearer "):
            provided = authorization[7:].strip()
        elif x_api_key:
            provided = x_api_key
        if not check_api_key(provided, cfg.api_key):
            metrics.inc_auth_failure()
            raise HTTPException(status_code=401, detail="invalid or missing API key")

    auth = [Depends(require_auth)]

    @app.get("/api/info")
    def info() -> dict[str, Any]:
        from .. import relations
        from ..client import API_VERSION

        return {
            "name": "CookiX",
            "version": _version(),
            "api_version": API_VERSION,
            "objects": len(db),
            "modes": [m.value for m in RetrievalMode],
            "relations": relations.vocabulary(),
        }

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Liveness probe: the process is up and serving."""
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict[str, Any]:
        """Readiness probe: the database is reachable."""
        try:
            n = len(db)
        except Exception:  # pragma: no cover - defensive
            raise HTTPException(status_code=503, detail="database not ready") from None
        return {"status": "ready", "objects": n}

    @app.get("/metrics")
    def metrics_endpoint() -> Any:
        if not cfg.enable_metrics:
            raise HTTPException(status_code=404, detail="metrics disabled")
        return PlainTextResponse(metrics.render_prometheus())

    @app.get("/api/graph", dependencies=auth)
    def graph() -> dict[str, Any]:
        return _serialize_graph(db)

    @app.get("/api/sheaf", dependencies=auth)
    def sheaf_geometry() -> dict[str, Any]:
        """Stalks as 3D unit vectors + the edges connecting them."""
        return _serialize_sheaf(db, dim=3)

    @app.post("/api/sheaf/trace", dependencies=auth)
    def sheaf_trace(payload: dict = Body(...)) -> dict[str, Any]:
        """Carry an object's stalk along a reasoning path, step by step.

        Resolves a path from ``anchor`` to ``target`` (via graph traversal, or a
        supplied ``relation_chain``), then applies each relation's restriction
        map in turn. The returned ``steps`` are the cumulative transformed
        vectors; ``residual`` is how far the carried meaning lands from the
        target's own stalk (0 = perfect composition).
        """
        from .. import sheaf

        dim = 3
        anchor = payload.get("anchor")
        target = payload.get("target")
        relation_chain = payload.get("relation_chain")

        if anchor is None:
            return {"error": "anchor is required"}

        if relation_chain:
            chain = list(relation_chain)
            path = []
            cur = anchor
            for r in chain:
                path.append({"source": cur, "relation": r, "target": "?"})
        else:
            results = db.query(anchor=anchor, target=target, mode="graph")
            if not results:
                return {"anchor": anchor, "target": target, "path": [], "steps": [],
                        "residual": None, "error": "no path found"}
            best = results[0]
            path = [
                {"source": s.source, "relation": s.relation, "target": s.target}
                for s in best.path
            ]
            chain = [s.relation for s in best.path]
            target = best.object_id

        v = _sheaf_stalk(db, anchor, dim)
        steps = [{"relation": None, "label": anchor, "vector": v.tolist()}]
        for step, r in zip(path, chain, strict=True):
            v = sheaf.restriction_map(r, dim) @ v
            steps.append({"relation": r, "label": step.get("target", "?"), "vector": v.tolist()})

        target_stalk = _sheaf_stalk(db, target, dim) if target else None
        residual = None
        if target_stalk is not None:
            denom = float(np.linalg.norm(target_stalk)) or 1.0
            residual = float(np.linalg.norm(v - target_stalk) / denom)

        return {
            "anchor": anchor,
            "target": target,
            "path": path,
            "steps": steps,
            "target_stalk": target_stalk.tolist() if target_stalk is not None else None,
            "residual": residual,
        }

    @app.post("/api/insert", dependencies=auth)
    def insert(payload: dict = Body(...)) -> dict[str, str]:
        if cfg.read_only:
            raise HTTPException(status_code=403, detail="server is read-only")
        document = payload.get("document", payload)
        if not isinstance(document, dict):
            raise HTTPException(status_code=422, detail="document must be an object")
        obj_id = db.insert(document)
        return {"id": obj_id}

    @app.post("/api/query", dependencies=auth)
    def query(payload: dict = Body(...)) -> dict[str, Any]:
        # Clamp resource-bounding parameters so one request cannot ask the engine
        # to do unbounded work.
        try:
            k = max(1, min(int(payload.get("k", 5)), cfg.max_k))
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="k must be an integer") from None
        max_hops = payload.get("max_hops")
        if max_hops is not None:
            try:
                max_hops = max(1, min(int(max_hops), cfg.max_hops_limit))
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail="max_hops must be an integer") from None
        results = db.query(
            payload.get("query"),
            anchor=payload.get("anchor"),
            relation=payload.get("relation"),
            target=payload.get("target"),
            k=k,
            mode=payload.get("mode", "reasoning"),
            max_hops=max_hops,
        )
        return {"results": [_serialize_result(r) for r in results]}

    @app.get("/")
    def index() -> Any:
        return FileResponse(_STATIC_DIR / "index.html")

    @app.get("/sheaf")
    def sheaf_page() -> Any:
        return FileResponse(_STATIC_DIR / "sheaf.html")

    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    return app


def _version() -> str:
    from .. import __version__

    return __version__


def serve(
    db: Database | None = None,
    *,
    demo: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8000,
    config: ServerConfig | None = None,
) -> None:
    """Start the CookiX HTTP server + reasoning-path explorer UI.

    If no database is supplied, loads a named ``demo`` (default ``"umbrella"``)
    so the UI has something to show on first launch. ``config`` (or the
    ``COOKIX_*`` environment) controls auth, rate limiting and resource limits.
    """
    import logging

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            'The CookiX server requires uvicorn. Install it with: pip install "cookix[server]"'
        ) from exc

    logging.basicConfig(level=logging.INFO)  # surface the structured access logs

    if db is None:
        from ..demos import DEMOS

        builder = DEMOS.get(demo or "umbrella")
        db = builder() if builder else Database()

    app = create_app(db, config)
    uvicorn.run(app, host=host, port=port)
