"""Sheaf-theoretic composition layer (experimental)."""

from __future__ import annotations

from .composition import (
    AVAILABLE,
    compose,
    composition_residual,
    default_stalk,
    restriction_map,
    set_learned_maps,
)
from .learning import (
    learn_restriction_maps,
    mean_composition_residual,
    orthogonal_procrustes,
)

__all__ = [
    "AVAILABLE",
    "compose",
    "composition_residual",
    "default_stalk",
    "restriction_map",
    "set_learned_maps",
    "learn_restriction_maps",
    "mean_composition_residual",
    "orthogonal_procrustes",
]
