"""Persistent-homology signatures and topological vector similarity (TVS).

This is one of NoVectDB's two research layers. The hypothesis (from the paper,
Sec. 4) is that the *shape* of a concept's local neighbourhood — captured as a
persistence diagram and vectorised — carries retrieval signal that flat
embeddings miss, and is immune to precision collapse because it is independent
of ambient dimension.

This module computes, for a Knowledge Object, the persistence barcode of its
r-hop neighbourhood (treated as a weighted graph / point cloud) and vectorises
it into a fixed-length signature T. TVS compares two signatures.

It depends on ``ripser``/``persim`` and degrades gracefully: if they are not
installed, :data:`AVAILABLE` is ``False`` and the engine simply skips the
topological term. This lets the graph-only core run with zero heavy deps, and
makes the topological layer an *ablatable* experiment rather than a hard
requirement — which is exactly how its value should be judged.
"""

from __future__ import annotations

import numpy as np

try:
    from ripser import ripser  # type: ignore

    AVAILABLE = True
except ImportError:  # pragma: no cover - depends on optional dep
    AVAILABLE = False


def _require() -> None:
    if not AVAILABLE:
        raise ImportError(
            "Topological signatures require 'ripser' and 'persim'. "
            'Install with: pip install "cookix[topology]"'
        )


def signature(distance_matrix: np.ndarray, max_dim: int = 1, n_bins: int = 32) -> np.ndarray:
    """Compute a fixed-length topological signature from a distance matrix.

    The neighbourhood is summarised by its persistence diagram (dims 0..max_dim),
    then vectorised into a simple, stable persistence-statistics histogram so two
    signatures are directly comparable with cosine/L2. We deliberately use a
    lightweight vectorisation (binned persistence lifetimes) rather than full
    persistence images to keep the signature cheap and dependency-light.

    Args:
        distance_matrix: square pairwise-distance matrix of the neighbourhood.
        max_dim: maximum homology dimension to compute (0=components, 1=loops).
        n_bins: histogram bins per homology dimension.

    Returns:
        A 1-D float array of length ``(max_dim + 1) * n_bins``.
    """
    _require()
    n = distance_matrix.shape[0]
    if n < 2:
        return np.zeros((max_dim + 1) * n_bins, dtype=float)

    result = ripser(distance_matrix, maxdim=max_dim, distance_matrix=True)
    diagrams = result["dgms"]

    finite_deaths = [
        d[np.isfinite(d[:, 1]), 1] for d in diagrams if len(d) and np.any(np.isfinite(d[:, 1]))
    ]
    max_death = max((float(arr.max()) for arr in finite_deaths if arr.size), default=1.0) or 1.0

    blocks = []
    for dim in range(max_dim + 1):
        diagram = diagrams[dim] if dim < len(diagrams) else np.empty((0, 2))
        lifetimes = []
        for birth, death in diagram:
            death = max_death * 1.05 if not np.isfinite(death) else death
            lifetimes.append(max(0.0, death - birth))
        if lifetimes:
            hist, _ = np.histogram(lifetimes, bins=n_bins, range=(0.0, max_death))
            blocks.append(hist.astype(float))
        else:
            blocks.append(np.zeros(n_bins, dtype=float))
    return np.concatenate(blocks)


def tvs(sig_a: np.ndarray | None, sig_b: np.ndarray | None, bandwidth: float = 1.0) -> float:
    """Topological Vector Similarity in ``[0, 1]`` (paper Def. 4.3).

    ``TVS = exp(-bandwidth * ||T_a - T_b||)`` using normalised signatures, so
    identical shapes score 1.0 and dissimilarity decays toward 0.0. Returns 0.0
    if either signature is missing.
    """
    if sig_a is None or sig_b is None:
        return 0.0
    a = np.asarray(sig_a, dtype=float)
    b = np.asarray(sig_b, dtype=float)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0.0 and nb == 0.0:
        return 1.0
    if na == 0.0 or nb == 0.0:
        return 0.0
    dist = float(np.linalg.norm(a / na - b / nb))
    return float(np.exp(-bandwidth * dist))
