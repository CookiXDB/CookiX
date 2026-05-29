"""TopoIndex: approximate nearest-neighbour search over topological signatures.

Once every Knowledge Object carries a fixed-length persistence signature ``T``
(see :func:`cookix.topology.signature`), "find the objects whose neighbourhood
*shape* most resembles this one" becomes a nearest-neighbour query under
Topological Vector Similarity (TVS). Done naively that is an O(N) scan per query.

TopoIndex makes it sublinear with **random-hyperplane LSH**. TVS ranks by the L2
distance between L2-normalised signatures, so cosine LSH is the right hash: each
random hyperplane contributes one bit (the sign of the projection), signatures
that are close almost always share most bits, and we only score candidates that
land in the query's bucket (or a nearby one). It is deterministic (seeded),
numpy-only, and falls back to an exact scan via :meth:`query_exact`.

This indexes signature *vectors*; producing them needs the ``topology`` extra,
but the index itself has no heavy dependencies, so it is fully testable offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np

from .signatures import tvs


def _unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n else v


@dataclass
class _Entry:
    obj_id: str
    signature: np.ndarray  # L2-normalised
    code: int


class TopoIndex:
    """LSH index over topological signatures, ranked exactly by TVS.

    Args:
        n_planes: number of random hyperplanes (hash bits). More planes = finer
            buckets (faster, lower recall); fewer = coarser (slower, higher recall).
        bandwidth: TVS bandwidth used for the final exact ranking.
        seed: RNG seed for the hyperplanes; fixes the index deterministically.
    """

    def __init__(self, n_planes: int = 16, bandwidth: float = 1.0, seed: int = 0) -> None:
        self.n_planes = n_planes
        self.bandwidth = bandwidth
        self._seed = seed
        self._dim: int | None = None
        self._planes: np.ndarray | None = None
        self._buckets: dict[int, list[_Entry]] = {}
        self._entries: list[_Entry] = []

    def __len__(self) -> int:
        return len(self._entries)

    def _ensure_planes(self, dim: int) -> None:
        if self._planes is None:
            rng = np.random.default_rng(self._seed)
            self._planes = rng.standard_normal((self.n_planes, dim))
            self._dim = dim
        elif dim != self._dim:
            raise ValueError(f"signature dim {dim} != index dim {self._dim}")

    def _hash(self, sig: np.ndarray) -> int:
        assert self._planes is not None
        bits = (self._planes @ sig) >= 0
        code = 0
        for b in bits:
            code = (code << 1) | int(b)
        return code

    def add(self, obj_id: str, signature: np.ndarray) -> None:
        sig = _unit(np.asarray(signature, dtype=float))
        self._ensure_planes(sig.shape[0])
        code = self._hash(sig)
        entry = _Entry(obj_id=obj_id, signature=sig, code=code)
        self._entries.append(entry)
        self._buckets.setdefault(code, []).append(entry)

    def add_many(self, items: dict[str, np.ndarray]) -> None:
        for obj_id, sig in items.items():
            self.add(obj_id, sig)

    def _probe_codes(self, code: int, radius: int) -> list[int]:
        """All bucket codes within ``radius`` bit-flips of ``code``."""
        codes = [code]
        positions = range(self.n_planes)
        for r in range(1, radius + 1):
            for flips in combinations(positions, r):
                mutated = code
                for p in flips:
                    mutated ^= 1 << p
                codes.append(mutated)
        return codes

    def query(
        self, signature: np.ndarray, k: int = 5, probe_radius: int = 2
    ) -> list[tuple[str, float]]:
        """Approximate top-``k`` by TVS, scanning only nearby LSH buckets.

        Returns ``(obj_id, tvs)`` pairs sorted by descending similarity. Widen
        ``probe_radius`` to trade speed for recall; ``query_exact`` is the ground
        truth.
        """
        if self._planes is None or not self._entries:
            return []
        q = _unit(np.asarray(signature, dtype=float))
        code = self._hash(q)
        seen: set[int] = set()
        candidates: list[_Entry] = []
        for c in self._probe_codes(code, probe_radius):
            if c in self._buckets:
                for entry in self._buckets[c]:
                    if id(entry) not in seen:
                        seen.add(id(entry))
                        candidates.append(entry)
        scored = [(e.obj_id, tvs(q, e.signature, self.bandwidth)) for e in candidates]
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:k]

    def query_exact(self, signature: np.ndarray, k: int = 5) -> list[tuple[str, float]]:
        """Exact top-``k`` by TVS over every entry (the recall ground truth)."""
        q = _unit(np.asarray(signature, dtype=float))
        scored = [(e.obj_id, tvs(q, e.signature, self.bandwidth)) for e in self._entries]
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:k]


def recall_at_k(index: TopoIndex, queries: list[np.ndarray], k: int = 5,
                probe_radius: int = 2) -> float:
    """Mean fraction of the exact top-``k`` that the LSH query also returns.

    A direct, honest measure of the speed/accuracy trade-off for a given
    ``probe_radius`` on a given index.
    """
    if not queries:
        return 0.0
    total = 0.0
    for q in queries:
        exact = {oid for oid, _ in index.query_exact(q, k)}
        approx = {oid for oid, _ in index.query(q, k, probe_radius)}
        total += len(exact & approx) / len(exact) if exact else 0.0
    return total / len(queries)
