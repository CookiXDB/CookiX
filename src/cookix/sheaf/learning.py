"""Learning sheaf restriction maps from observed edges (Phase 3).

The base :mod:`cookix.sheaf.composition` layer ships *placeholder* restriction
maps: each relation name seeds a fixed random orthogonal matrix. They make
composition well-defined and direction-aware but carry no information learned
from data, so the composition residual of a real reasoning chain is essentially
arbitrary.

This module closes that gap. Given a set of object stalks and the typed edges
between them, it learns, per relation, the orthogonal map that best transports a
source stalk onto its target — the closed-form **orthogonal Procrustes**
solution to ``min_{F orthogonal} sum ||F x_a - x_b||``. Inverse relations are
tied to the transpose (so walking an edge backwards undoes the transform) and
symmetric relations pool both orderings, exactly mirroring the placeholder's
algebra. The result is a drop-in replacement: install learned maps with
:func:`cookix.sheaf.set_learned_maps` and the engine's ``mode="sheaf"`` path
uses them.

This is the linear, closed-form rung of "learned sheaves"; gradient-based neural
sheaf diffusion (jointly learning stalks and maps) is a further step. Everything
here is deterministic and numpy-only.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

import numpy as np

from .. import relations


def orthogonal_procrustes(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Orthogonal ``F`` minimising ``||F·source - target||_F``.

    ``source`` and ``target`` are ``(dim, n)`` matrices of matched column
    vectors. Closed form: ``F = U Vᵀ`` where ``U S Vᵀ = target·sourceᵀ``.
    With no evidence (``n == 0``) the identity is returned.
    """
    if source.shape[1] == 0:
        return np.eye(source.shape[0])
    m = target @ source.T
    u, _, vt = np.linalg.svd(m)
    return u @ vt


def _canonical(relation: str) -> tuple[str, bool, bool]:
    """Return ``(canonical_name, is_transpose, is_symmetric)`` for a relation.

    The canonical name of an inverse pair is the lexicographically smaller one;
    the larger name's map is the transpose of the canonical's. Symmetric
    relations are their own canonical and use one map in both directions.
    """
    inv = relations.inverse_of(relation)
    if inv is None or inv == relation:
        return relation, False, True
    if relation < inv:
        return relation, False, False
    return inv, True, False


def learn_restriction_maps(
    edges: list[tuple[str, str, str]],
    stalks: dict[str, np.ndarray],
    dim: int,
) -> dict[str, np.ndarray]:
    """Learn an orthogonal restriction map per relation from edge evidence.

    Args:
        edges: ``(source_id, relation, target_id)`` triples.
        stalks: object id -> stalk vector (``dim``-dimensional).
        dim: stalk dimension.

    Returns:
        A map from every relation name seen (and its inverse) to a learned
        orthogonal ``(dim, dim)`` matrix, with inverse pairs tied to transposes.
    """
    # Pool matched (source, target) columns onto each canonical representative.
    src: dict[str, list[np.ndarray]] = defaultdict(list)
    tgt: dict[str, list[np.ndarray]] = defaultdict(list)
    seen: set[str] = set()
    for a, rel, b in edges:
        if a not in stalks or b not in stalks:
            continue
        seen.add(rel)
        canon, is_t, is_sym = _canonical(rel)
        xa, xb = stalks[a], stalks[b]
        # Express every edge as forward evidence for the canonical map.
        if is_t:
            xa, xb = xb, xa  # this relation is the transpose direction
        src[canon].append(xa)
        tgt[canon].append(xb)
        if is_sym:  # symmetric: also feed the reversed ordering
            src[canon].append(xb)
            tgt[canon].append(xa)

    maps: dict[str, np.ndarray] = {}
    for canon in src:
        f = orthogonal_procrustes(
            np.array(src[canon]).T, np.array(tgt[canon]).T
        )
        maps[canon] = f
        inv = relations.inverse_of(canon)
        if inv is not None and inv != canon:
            maps[inv] = f.T

    # Ensure every relation that appeared has an entry (identity if no evidence).
    for rel in seen:
        maps.setdefault(rel, np.eye(dim))
    return maps


def mean_composition_residual(
    paths: Sequence[tuple[str, Sequence[str], str]],
    stalks: dict[str, np.ndarray],
    map_fn,
) -> float:
    """Mean normalised residual ``||S_π(x_a) - x_b|| / ||x_b||`` over ``paths``.

    ``paths`` are ``(source_id, relation_chain, target_id)``. ``map_fn`` maps a
    relation name to its restriction matrix, so the same evaluation works for
    placeholder and learned maps.
    """
    if not paths:
        return 0.0
    total = 0.0
    for a, chain, b in paths:
        xa, xb = stalks[a], stalks[b]
        composed = xa
        for rel in chain:
            composed = map_fn(rel) @ composed
        denom = float(np.linalg.norm(xb)) or 1.0
        total += float(np.linalg.norm(composed - xb) / denom)
    return total / len(paths)
