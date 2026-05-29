"""Storage backends for the Dynamic Graph Manifold."""

from __future__ import annotations

from .base import StorageBackend
from .memory import InMemoryBackend

__all__ = ["StorageBackend", "InMemoryBackend", "get_backend"]


def get_backend(kind: str = "memory", **kwargs) -> StorageBackend:
    """Factory for storage backends.

    Args:
        kind: ``"memory"`` (default, volatile) or ``"kuzu"`` (durable, on-disk).
        **kwargs: backend-specific options (e.g. ``path`` for Kùzu).
    """
    if kind == "memory":
        return InMemoryBackend()
    if kind == "kuzu":
        from .kuzu_backend import KuzuBackend

        return KuzuBackend(**kwargs)
    raise ValueError(f"unknown storage backend: {kind!r} (expected 'memory' or 'kuzu')")
