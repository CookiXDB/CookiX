"""Sheaf-theoretic composition layer (experimental)."""

from __future__ import annotations

from .composition import (
    AVAILABLE,
    compose,
    composition_residual,
    default_stalk,
    restriction_map,
)

__all__ = [
    "AVAILABLE",
    "compose",
    "composition_residual",
    "default_stalk",
    "restriction_map",
]
