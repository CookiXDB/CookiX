"""CookiX — the open-source topological-relational memory database.

Reference implementation of the NoVectDB paradigm (Hafdi, 2026): knowledge has
shape, direction, and composition, and our databases should too.

Quickstart::

    import cookix

    db = cookix.connect("demo")
    db.insert({"_id": "umbrella", "content": "umbrella", "edges": [("prevents", "rain")]})
    db.insert({"_id": "rain", "content": "rain", "edges": [("causes", "wet_coat")]})

    for r in db.query(anchor="umbrella", target="wet_coat", mode="reasoning"):
        print(r.explain())
"""

from __future__ import annotations

from . import relations
from .client import API_VERSION, CookixClient, CookixError
from .database import Database, connect
from .engine import EngineConfig, QueryEngine, RetrievalMode
from .model import Edge, KnowledgeObject, QueryResult, ReasoningStep

__version__ = "1.1.0"

__all__ = [
    "__version__",
    "API_VERSION",
    "connect",
    "Database",
    "QueryEngine",
    "EngineConfig",
    "RetrievalMode",
    "KnowledgeObject",
    "Edge",
    "QueryResult",
    "ReasoningStep",
    "CookixClient",
    "CookixError",
    "relations",
]
