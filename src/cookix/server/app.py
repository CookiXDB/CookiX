"""HTTP server for CookiX: the substrate for non-Python clients and the UI.

The embedded library (``import cookix``) is the primary interface. This module
exposes the same operations over HTTP so a browser, or a non-Python service,
can talk to a CookiX database. It also serves the reasoning-path explorer UI,
which is the feature a vector database cannot offer: every answer comes with
the *path* that justifies it, rendered as an interactive graph.

Run with ``cookix serve`` (see :mod:`cookix.cli`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from ..database import Database
from ..engine import RetrievalMode
from ..model import QueryResult

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


def create_app(db: Database) -> Any:
    """Build a FastAPI app bound to ``db``.

    Imported lazily so the core library has no hard dependency on FastAPI;
    ``cookix[server]`` installs it. Raises a helpful error if it is missing.
    """
    try:
        from fastapi import Body, FastAPI
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "The CookiX server requires extra dependencies. Install them with:\n"
            '    pip install "cookix[server]"'
        ) from exc

    app = FastAPI(title="CookiX", version=_version())

    @app.get("/api/info")
    def info() -> dict[str, Any]:
        from .. import relations

        return {
            "name": "CookiX",
            "version": _version(),
            "objects": len(db),
            "modes": [m.value for m in RetrievalMode],
            "relations": relations.vocabulary(),
        }

    @app.get("/api/graph")
    def graph() -> dict[str, Any]:
        return _serialize_graph(db)

    @app.get("/api/sheaf")
    def sheaf_geometry() -> dict[str, Any]:
        """Stalks as 3D unit vectors + the edges connecting them."""
        return _serialize_sheaf(db, dim=3)

    @app.post("/api/sheaf/trace")
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

    @app.post("/api/insert")
    def insert(payload: dict = Body(...)) -> dict[str, str]:
        document = payload.get("document", payload)
        obj_id = db.insert(document)
        return {"id": obj_id}

    @app.post("/api/query")
    def query(payload: dict = Body(...)) -> dict[str, Any]:
        results = db.query(
            payload.get("query"),
            anchor=payload.get("anchor"),
            relation=payload.get("relation"),
            target=payload.get("target"),
            k=int(payload.get("k", 5)),
            mode=payload.get("mode", "reasoning"),
            max_hops=payload.get("max_hops"),
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
) -> None:
    """Start the CookiX HTTP server + reasoning-path explorer UI.

    If no database is supplied, loads a named ``demo`` (default ``"umbrella"``)
    so the UI has something to show on first launch.
    """
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            'The CookiX server requires uvicorn. Install it with: pip install "cookix[server]"'
        ) from exc

    if db is None:
        from ..demos import DEMOS

        builder = DEMOS.get(demo or "umbrella")
        db = builder() if builder else Database()

    app = create_app(db)
    uvicorn.run(app, host=host, port=port)
