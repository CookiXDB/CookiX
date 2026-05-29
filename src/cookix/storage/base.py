"""Storage backend interface.

CookiX separates *what* is stored (Knowledge Objects + typed edges) from *how*
it is persisted. The default backend is in-memory; an embedded property-graph
backend (Kùzu) is available for durability and scale. The query engine depends
only on this interface, never on a concrete backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator

from ..model import Edge, KnowledgeObject


class StorageBackend(ABC):
    """Abstract persistent store for a Dynamic Graph Manifold."""

    @abstractmethod
    def put(self, obj: KnowledgeObject) -> None:
        """Insert or replace a Knowledge Object (including its edges)."""

    @abstractmethod
    def get(self, obj_id: str) -> KnowledgeObject | None:
        """Return the object with ``obj_id`` or ``None`` if absent."""

    @abstractmethod
    def delete(self, obj_id: str) -> bool:
        """Remove an object and all edges touching it. Returns True if removed."""

    @abstractmethod
    def __contains__(self, obj_id: str) -> bool: ...

    @abstractmethod
    def __len__(self) -> int: ...

    @abstractmethod
    def all_ids(self) -> Iterator[str]:
        """Iterate over every object id."""

    @abstractmethod
    def out_edges(self, obj_id: str) -> list[Edge]:
        """Outgoing edges of ``obj_id`` (forward direction only)."""

    @abstractmethod
    def in_edges(self, obj_id: str) -> list[tuple[str, Edge]]:
        """Incoming edges as ``(source_id, edge)`` pairs."""

    def get_many(self, ids: Iterable[str]) -> list[KnowledgeObject]:
        out = []
        for i in ids:
            obj = self.get(i)
            if obj is not None:
                out.append(obj)
        return out

    def close(self) -> None:  # noqa: B027  # pragma: no cover
        """Flush/close underlying resources. No-op for volatile backends."""
        return None
