"""Storage backends for the Dynamic Graph Manifold."""

from __future__ import annotations

from .base import StorageBackend
from .durable import DurableBackend
from .memory import InMemoryBackend

__all__ = ["StorageBackend", "InMemoryBackend", "DurableBackend", "get_backend"]


def get_backend(kind: str = "memory", **kwargs) -> StorageBackend:
    """Factory for storage backends.

    Args:
        kind: ``"memory"`` (default, volatile), ``"durable"`` (crash-safe WAL +
            atomic snapshots, pure-Python), or ``"kuzu"`` (embedded property graph).
        **kwargs: backend-specific options (e.g. ``path`` for durable/Kùzu).
    """
    if kind == "memory":
        return InMemoryBackend()
    if kind == "durable":
        return DurableBackend(**kwargs)
    if kind == "kuzu":
        from .kuzu_backend import KuzuBackend

        return KuzuBackend(**kwargs)
    raise ValueError(
        f"unknown storage backend: {kind!r} (expected 'memory', 'durable' or 'kuzu')"
    )
