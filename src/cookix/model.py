"""Core data model: the Knowledge Object and query results.

A Knowledge Object is the atomic unit of storage in NoVectDB::

    K = (V, E, T, S)

where ``V`` is an optional embedding vector, ``E`` a set of typed directed
edges, ``T`` a topological signature derived from the local neighbourhood, and
``S`` a sheaf section describing how the object's meaning transforms in context.

Only ``content`` and ``edges`` are required; ``V``, ``T`` and ``S`` are optional
and may be computed lazily by the engine. This is deliberate: pure
topological-relational storage (no vectors) is a valid NoVectDB configuration.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class Edge:
    """A typed, directed, weighted relation to another Knowledge Object.

    Attributes:
        relation: relation type from the controlled vocabulary (see
            :mod:`cookix.relations`).
        target: id of the target Knowledge Object.
        weight: edge weight; lower means "closer" for geodesic search.
        meta: arbitrary edge metadata (provenance, confidence, …).
    """

    relation: str
    target: str
    weight: float = 1.0
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"relation": self.relation, "target": self.target, "weight": self.weight}
        if self.meta:
            d["meta"] = self.meta
        return d

    @classmethod
    def from_any(cls, value: Any) -> Edge:
        """Build an Edge from a dict or a ``(relation, target[, weight])`` tuple."""
        if isinstance(value, Edge):
            return value
        if isinstance(value, dict):
            return cls(
                relation=value["relation"],
                target=value["target"],
                weight=float(value.get("weight", 1.0)),
                meta=dict(value.get("meta", {})),
            )
        if isinstance(value, (list, tuple)):
            relation, target = value[0], value[1]
            weight = float(value[2]) if len(value) > 2 else 1.0
            return cls(relation=relation, target=target, weight=weight)
        raise TypeError(f"cannot build Edge from {type(value).__name__}: {value!r}")


@dataclass
class KnowledgeObject:
    """The atomic unit of NoVectDB storage: ``K = (V, E, T, S)``."""

    content: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    edges: list[Edge] = field(default_factory=list)
    vector: np.ndarray | None = None  # V: optional legacy embedding
    topo_signature: np.ndarray | None = None  # T: persistent-homology signature
    sheaf_stalk: np.ndarray | None = None  # S: local semantic frame
    meta: dict[str, Any] = field(default_factory=dict)

    def add_edge(self, relation: str, target: str, weight: float = 1.0, **meta: Any) -> Edge:
        edge = Edge(relation=relation, target=target, weight=weight, meta=meta)
        self.edges.append(edge)
        return edge

    def neighbors(self, relation: str | None = None) -> list[str]:
        """Target ids reachable in one hop, optionally filtered by relation."""
        return [e.target for e in self.edges if relation is None or e.relation == relation]

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "_id": self.id,
            "content": self.content,
            "edges": [e.to_dict() for e in self.edges],
        }
        if self.vector is not None:
            d["vector"] = self.vector.tolist()
        if self.meta:
            d["meta"] = self.meta
        return d

    @classmethod
    def from_dict(cls, doc: dict[str, Any]) -> KnowledgeObject:
        """Build a Knowledge Object from a CookiX/Mongo-style document.

        Accepts ``_id`` or ``id`` for the identifier and ``text`` or ``content``
        for the body, so the API matches the paper's document interface.
        """
        obj_id = doc.get("_id") or doc.get("id") or uuid.uuid4().hex
        content = doc.get("content") or doc.get("text") or ""
        edges = [Edge.from_any(e) for e in doc.get("edges", [])]
        vector = doc.get("vector")
        return cls(
            id=obj_id,
            content=content,
            edges=edges,
            vector=np.asarray(vector, dtype=float) if vector is not None else None,
            meta=dict(doc.get("meta", {})),
        )


@dataclass
class ReasoningStep:
    """One hop in a reasoning path: ``source --relation--> target``."""

    source: str
    relation: str
    target: str
    weight: float = 1.0

    def __str__(self) -> str:
        return f"{self.source} --[{self.relation}]--> {self.target}"


@dataclass
class QueryResult:
    """A single retrieval result with its interpretable reasoning path.

    Unlike a vector database, which returns a scalar distance, every CookiX
    result carries the *path* that justifies it and a breakdown of the composite
    distance into its geodesic, topological and sheaf components.
    """

    object_id: str
    content: str
    score: float
    path: list[ReasoningStep] = field(default_factory=list)
    components: dict[str, float] = field(default_factory=dict)

    @property
    def hops(self) -> int:
        return len(self.path)

    def explain(self) -> str:
        """Human-readable justification for why this result was returned."""
        if not self.path:
            header = f"{self.object_id} (direct match, score={self.score:.4f})"
        else:
            chain = self.path[0].source
            for step in self.path:
                chain += f" --[{step.relation}]--> {step.target}"
            header = f"{chain}  (score={self.score:.4f}, hops={self.hops})"
        if self.components:
            parts = ", ".join(f"{k}={v:.4f}" for k, v in self.components.items())
            header += f"\n    components: {parts}"
        return header

    def __str__(self) -> str:
        return self.explain()
