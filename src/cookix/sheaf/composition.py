"""Sheaf-theoretic composition (experimental research layer).

This is NoVectDB's second research layer (paper Sec. 5). A cellular sheaf
assigns a vector space (a *stalk*) to every Knowledge Object and a linear
*restriction map* to every typed edge, modelling how meaning transforms across a
relation. Composing the maps along a path π gives ``S_π``; the *composition
residual* ``||S_π(x_a) - x_b||`` measures how consistently object a's meaning
arrives at object b via that path. Low residual = a coherent reasoning chain.

Honest status
-------------
The paper defers *learning* the restriction maps to future work. Until learned
maps exist, this module uses a deterministic, relation-typed placeholder: each
relation name seeds a fixed orthogonal map, and inverse relations use the
transpose. This makes composition well-defined, reproducible, and direction-
aware, but the maps are not yet trained on data — so the sheaf term should be
treated as an *ablatable hypothesis*, not a proven contributor. The engine keeps
it behind a switch precisely so its value can be measured rather than assumed.
"""

from __future__ import annotations

import hashlib

import numpy as np

from .. import relations

AVAILABLE = True  # numpy-only; always importable

# Optional learned maps (see :mod:`cookix.sheaf.learning`). When installed via
# :func:`set_learned_maps`, they replace the placeholder for any relation they
# cover, at the dimension they were trained for.
_LEARNED: dict[str, np.ndarray] | None = None


def set_learned_maps(maps: dict[str, np.ndarray] | None) -> None:
    """Install (or clear with ``None``) learned restriction maps globally.

    Maps are keyed by relation name and already direction-resolved (inverse
    relations hold the transpose). They are consulted by :func:`restriction_map`
    only when the requested dimension matches the learned matrices.
    """
    global _LEARNED
    _LEARNED = maps


def _seed_from_relation(relation: str) -> int:
    digest = hashlib.sha256(relation.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def restriction_map(relation: str, dim: int) -> np.ndarray:
    """Restriction map for a relation type.

    Returns a learned map when one has been installed for this relation at the
    matching dimension (see :func:`set_learned_maps`); otherwise a deterministic
    orthogonal placeholder. Same relation name always yields the same map; the
    inverse relation yields its transpose, so walking an edge backwards undoes
    the transform. Symmetric relations are their own inverse.
    """
    if _LEARNED is not None:
        learned = _LEARNED.get(relation)
        if learned is not None and learned.shape == (dim, dim):
            return learned

    inverse = relations.inverse_of(relation)
    # For one direction of each inverse pair, build the map; the other direction
    # transposes it. Pick the lexicographically smaller name as the "forward" one
    # so both directions agree on the base matrix.
    if inverse is not None and inverse != relation and inverse < relation:
        return restriction_map(inverse, dim).T

    rng = np.random.default_rng(_seed_from_relation(relation))
    a = rng.standard_normal((dim, dim))
    q, r = np.linalg.qr(a)
    # Fix signs so the decomposition is unique and stable.
    q *= np.sign(np.diag(r))
    return q


def compose(path_relations: list[str], dim: int) -> np.ndarray:
    """Composed restriction map ``S_π = F_{e_k} ∘ ... ∘ F_{e_1}``."""
    result = np.eye(dim)
    for relation in path_relations:
        result = restriction_map(relation, dim) @ result
    return result


def composition_residual(
    stalk_a: np.ndarray, stalk_b: np.ndarray, path_relations: list[str]
) -> float:
    """Normalised composition residual ``||S_π(x_a) - x_b|| / ||x_b||`` (paper Eq. 2).

    Returns a value in ``[0, ~2]``; 0 means a's meaning composes perfectly into
    b along the path. Returns 0.0 for empty paths (an object composes with
    itself trivially).
    """
    if not path_relations:
        return 0.0
    dim = stalk_a.shape[0]
    composed = compose(path_relations, dim) @ stalk_a
    denom = float(np.linalg.norm(stalk_b)) or 1.0
    return float(np.linalg.norm(composed - stalk_b) / denom)


def default_stalk(obj_id: str, dim: int) -> np.ndarray:
    """Deterministic unit stalk for an object lacking an explicit semantic frame.

    Derived from the object id so results are reproducible. Real deployments
    should populate stalks from learned or LLM-derived semantic frames.
    """
    rng = np.random.default_rng(_seed_from_relation(obj_id))
    v = rng.standard_normal(dim)
    norm = np.linalg.norm(v)
    return v / norm if norm else v
