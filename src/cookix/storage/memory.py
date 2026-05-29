"""In-memory storage backend backed by a NetworkX directed multigraph.

This is the default backend: zero external services, deterministic, and fast
for the corpus sizes used in research and prototyping. It supports type-filtered
traversal and inverse-edge walking, which the query engine relies on.
"""

from __future__ import annotations

import os
import pickle
from collections.abc import Iterator
from pathlib import Path

import networkx as nx

from ..model import Edge, KnowledgeObject
from .base import StorageBackend


class InMemoryBackend(StorageBackend):
    """Volatile graph store. Optionally snapshots to disk via pickle."""

    def __init__(self) -> None:
        self._objects: dict[str, KnowledgeObject] = {}
        self._graph = nx.MultiDiGraph()

    def put(self, obj: KnowledgeObject) -> None:
        if obj.id in self._objects:
            self._remove_edges(obj.id)
        self._objects[obj.id] = obj
        self._graph.add_node(obj.id)
        for edge in obj.edges:
            # Ensure the target node exists even if not yet inserted (dangling
            # edges are valid; the target may arrive later).
            self._graph.add_node(edge.target)
            self._graph.add_edge(
                obj.id, edge.target, key=f"{edge.relation}:{edge.target}",
                relation=edge.relation, weight=edge.weight, meta=edge.meta,
            )

    def get(self, obj_id: str) -> KnowledgeObject | None:
        return self._objects.get(obj_id)

    def delete(self, obj_id: str) -> bool:
        if obj_id not in self._objects:
            return False
        del self._objects[obj_id]
        if self._graph.has_node(obj_id):
            self._graph.remove_node(obj_id)
        return True

    def __contains__(self, obj_id: str) -> bool:
        return obj_id in self._objects

    def __len__(self) -> int:
        return len(self._objects)

    def all_ids(self) -> Iterator[str]:
        return iter(list(self._objects.keys()))

    def out_edges(self, obj_id: str) -> list[Edge]:
        if not self._graph.has_node(obj_id):
            return []
        edges = []
        for _, target, data in self._graph.out_edges(obj_id, data=True):
            edges.append(Edge(relation=data["relation"], target=target,
                              weight=data["weight"], meta=data.get("meta", {})))
        return edges

    def in_edges(self, obj_id: str) -> list[tuple[str, Edge]]:
        if not self._graph.has_node(obj_id):
            return []
        result = []
        for source, _, data in self._graph.in_edges(obj_id, data=True):
            result.append((source, Edge(relation=data["relation"], target=obj_id,
                                        weight=data["weight"], meta=data.get("meta", {}))))
        return result

    def _remove_edges(self, obj_id: str) -> None:
        for _, target, key in list(self._graph.out_edges(obj_id, keys=True)):
            self._graph.remove_edge(obj_id, target, key=key)

    @property
    def graph(self) -> nx.MultiDiGraph:
        """The underlying NetworkX graph (read-only use by the engine)."""
        return self._graph

    def save(self, path: str | Path) -> None:
        """Snapshot to disk atomically: write a temp file, fsync, then replace.

        Writing in place would leave a corrupt half-written file if the process
        died mid-write; temp-file-plus-atomic-replace guarantees the destination
        is always either the old snapshot or the complete new one.
        """
        path = Path(path)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "wb") as fh:
            pickle.dump(self._objects, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: str | Path) -> InMemoryBackend:
        backend = cls()
        with open(path, "rb") as fh:
            objects: dict[str, KnowledgeObject] = pickle.load(fh)
        for obj in objects.values():
            backend.put(obj)
        return backend
