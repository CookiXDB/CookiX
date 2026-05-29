"""The NoVectDB query engine (paper Algorithm 1).

Retrieval is a multi-stage pipeline over the Dynamic Graph Manifold:

1. **Deterministic lookup** — exact typed-edge match from the anchor object.
   For single-hop relational queries this is precision-1.0 and we stop early.
2. **Geodesic BFS** — type-filtered breadth-first search for multi-hop paths,
   pruning by relation-type compatibility at each hop.
3. **Topological expansion** — re-rank candidates by similarity of their
   persistent-homology signatures (optional layer).
4. **Sheaf composition** — re-rank by how consistently meaning composes along
   each reasoning path (optional, experimental layer).

The composite distance combines a geodesic, topological and sheaf term::

    d = alpha * geodesic + beta * (1 - TVS) + gamma * sheaf_residual

Ablation is first-class: :class:`RetrievalMode` selects which layers are active,
so the contribution of the topological and sheaf layers can be *measured*
against a pure graph baseline rather than assumed.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from enum import Enum

from . import relations as rel
from . import sheaf, topology
from .model import KnowledgeObject, QueryResult, ReasoningStep
from .storage.base import StorageBackend


class RetrievalMode(str, Enum):
    """Which retrieval layers are active. Drives ablation studies."""

    GRAPH_ONLY = "graph_only"  # geodesic traversal only (the proven baseline)
    GRAPH_TOPO = "graph_topo"  # + topological re-ranking
    GRAPH_SHEAF = "graph_sheaf"  # + sheaf composition re-ranking
    FULL = "full"  # all layers (paper's NoVectDB composite distance)

    @property
    def use_topo(self) -> bool:
        return self in (RetrievalMode.GRAPH_TOPO, RetrievalMode.FULL)

    @property
    def use_sheaf(self) -> bool:
        return self in (RetrievalMode.GRAPH_SHEAF, RetrievalMode.FULL)


@dataclass
class EngineConfig:
    """Tunable parameters for the composite distance and traversal."""

    alpha: float = 0.5  # geodesic weight
    beta: float = 0.3  # topological weight
    gamma: float = 0.2  # sheaf weight
    max_hops: int = 4
    sheaf_dim: int = 16
    tvs_bandwidth: float = 1.0


class QueryEngine:
    """Executes relational queries against a storage backend."""

    def __init__(self, storage: StorageBackend, config: EngineConfig | None = None) -> None:
        self.storage = storage
        self.config = config or EngineConfig()

    # ------------------------------------------------------------------ #
    # Stage 1: deterministic typed-edge lookup
    # ------------------------------------------------------------------ #
    def direct(self, anchor: str, relation: str | None = None) -> list[QueryResult]:
        """Exact one-hop typed-edge match from ``anchor`` (precision 1.0).

        Inverse relations are *virtual*: querying ``prevented_by`` from an object
        resolves against incoming ``prevents`` edges without those reverse edges
        being physically stored. This lets "what prevents rain?" (rain is the
        grammatical object) find the subject by walking the edge backwards.
        """
        results: list[QueryResult] = []
        seen: set[str] = set()
        for edge in self.storage.out_edges(anchor):
            if relation is not None and edge.relation != relation:
                continue
            target = self.storage.get(edge.target)
            content = target.content if target else ""
            step = ReasoningStep(anchor, edge.relation, edge.target, edge.weight)
            results.append(
                QueryResult(
                    object_id=edge.target,
                    content=content,
                    score=0.0,  # exact match: zero distance
                    path=[step],
                    components={"geodesic": edge.weight},
                )
            )
            seen.add(edge.target)

        # Inverse direction: an incoming edge whose relation is the inverse of
        # the requested one satisfies the query (e.g. asking ``prevented_by``
        # matches a stored ``prevents`` edge pointing at ``anchor``).
        inverse = rel.inverse_of(relation) if relation is not None else None
        if inverse is not None:
            for source, edge in self.storage.in_edges(anchor):
                if edge.relation != inverse or source in seen:
                    continue
                src_obj = self.storage.get(source)
                step = ReasoningStep(source, edge.relation, anchor, edge.weight)
                results.append(
                    QueryResult(
                        object_id=source,
                        content=src_obj.content if src_obj else "",
                        score=0.0,
                        path=[step],
                        components={"geodesic": edge.weight},
                    )
                )
                seen.add(source)

        results.sort(key=lambda r: r.components.get("geodesic", 0.0))
        return results

    # ------------------------------------------------------------------ #
    # Stage 2: type-filtered geodesic BFS (multi-hop)
    # ------------------------------------------------------------------ #
    def geodesic_paths(
        self,
        anchor: str,
        relation_chain: list[str] | None = None,
        target: str | None = None,
        max_hops: int | None = None,
    ) -> list[QueryResult]:
        """Find reasoning paths from ``anchor`` via Dijkstra over edge weights.

        If ``relation_chain`` is given, only edges whose relation matches the
        chain at the corresponding hop are traversed (deterministic typed walk).
        If ``target`` is given, only paths reaching it are returned. Otherwise
        all reachable objects are returned ranked by geodesic distance.
        """
        max_hops = max_hops or self.config.max_hops
        # Priority queue of (cost, node, path_of_steps).
        pq: list[tuple[float, str, list[ReasoningStep]]] = [(0.0, anchor, [])]
        best_cost: dict[str, float] = {anchor: 0.0}
        results: dict[str, QueryResult] = {}

        while pq:
            cost, node, path = heapq.heappop(pq)
            hop = len(path)
            if hop > 0 and node != anchor:
                if node not in results or cost < results[node].score:
                    obj = self.storage.get(node)
                    results[node] = QueryResult(
                        object_id=node,
                        content=obj.content if obj else "",
                        score=cost,
                        path=list(path),
                        components={"geodesic": cost},
                    )
            if hop >= max_hops:
                continue
            allowed = relation_chain[hop] if relation_chain and hop < len(relation_chain) else None
            for edge in self.storage.out_edges(node):
                if allowed is not None and edge.relation != allowed:
                    continue
                new_cost = cost + edge.weight
                if edge.target in best_cost and best_cost[edge.target] <= new_cost:
                    continue
                best_cost[edge.target] = new_cost
                step = ReasoningStep(node, edge.relation, edge.target, edge.weight)
                heapq.heappush(pq, (new_cost, edge.target, path + [step]))

        ordered = sorted(results.values(), key=lambda r: r.score)
        if target is not None:
            ordered = [r for r in ordered if r.object_id == target]
        return ordered

    # ------------------------------------------------------------------ #
    # Stages 3-4: topological + sheaf re-ranking
    # ------------------------------------------------------------------ #
    def _get_cached(
        self, obj_id: str, cache: dict[str, KnowledgeObject | None] | None
    ) -> KnowledgeObject | None:
        """Fetch an object, memoising within a single ranking pass.

        Ranking re-ranks every candidate against the same ``anchor`` and the
        topology + sheaf terms each look the anchor up again, so without a cache
        the anchor is fetched O(candidates) times. Storage is not mutated during
        ranking, so memoising is safe and bounded to one query.
        """
        if cache is None:
            return self.storage.get(obj_id)
        if obj_id not in cache:
            cache[obj_id] = self.storage.get(obj_id)
        return cache[obj_id]

    def _topo_term(
        self,
        anchor: str,
        candidate: str,
        cache: dict[str, KnowledgeObject | None] | None = None,
    ) -> float | None:
        if not topology.AVAILABLE:
            return None
        a = self._get_cached(anchor, cache)
        b = self._get_cached(candidate, cache)
        if a is None or b is None or a.topo_signature is None or b.topo_signature is None:
            return None
        similarity = topology.tvs(a.topo_signature, b.topo_signature, self.config.tvs_bandwidth)
        return 1.0 - similarity

    def _sheaf_term(
        self,
        anchor: str,
        candidate: str,
        path: list[ReasoningStep],
        cache: dict[str, KnowledgeObject | None] | None = None,
    ) -> float:
        dim = self.config.sheaf_dim
        a = self._get_cached(anchor, cache)
        b = self._get_cached(candidate, cache)
        stalk_a = (
            a.sheaf_stalk if a is not None and a.sheaf_stalk is not None
            else sheaf.default_stalk(anchor, dim)
        )
        stalk_b = (
            b.sheaf_stalk if b is not None and b.sheaf_stalk is not None
            else sheaf.default_stalk(candidate, dim)
        )
        return sheaf.composition_residual(stalk_a, stalk_b, [s.relation for s in path])

    def rank(
        self, anchor: str, candidates: list[QueryResult], mode: RetrievalMode
    ) -> list[QueryResult]:
        """Apply the composite distance to re-rank candidate paths."""
        cfg = self.config
        cache: dict[str, KnowledgeObject | None] = {}
        for result in candidates:
            geodesic = result.components.get("geodesic", result.score)
            score = cfg.alpha * geodesic
            components = {"geodesic": geodesic}

            if mode.use_topo:
                topo = self._topo_term(anchor, result.object_id, cache)
                if topo is not None:
                    score += cfg.beta * topo
                    components["topo"] = topo

            if mode.use_sheaf:
                residual = self._sheaf_term(anchor, result.object_id, result.path, cache)
                score += cfg.gamma * residual
                components["sheaf"] = residual

            result.score = score
            result.components = components

        candidates.sort(key=lambda r: r.score)
        return candidates

    # ------------------------------------------------------------------ #
    # Top-level pipeline (Algorithm 1)
    # ------------------------------------------------------------------ #
    def query(
        self,
        anchor: str,
        relation: str | None = None,
        relation_chain: list[str] | None = None,
        target: str | None = None,
        k: int = 5,
        mode: RetrievalMode = RetrievalMode.FULL,
        max_hops: int | None = None,
    ) -> list[QueryResult]:
        """Run the full NoVectDB retrieval pipeline and return the top ``k``."""
        if anchor not in self.storage:
            return []

        # Stage 1: deterministic single-hop typed lookup. A bare relation query
        # ("what does X prevent?") returns exactly the matching edges — never
        # padded with unrelated multi-hop neighbours.
        if relation is not None and relation_chain is None and target is None:
            return self.direct(anchor, relation)[:k]

        # Stage 2: multi-hop geodesic traversal. ``relation_chain`` (when set
        # explicitly) hard-filters each hop; ``target`` restricts to paths that
        # reach it.
        candidates = self.geodesic_paths(
            anchor, relation_chain=relation_chain, target=target, max_hops=max_hops
        )

        # Stages 3-4: composite re-ranking.
        ranked = self.rank(anchor, candidates, mode)
        return ranked[:k]

    def contradictions(self, anchor: str, relation: str = "contradicts") -> list[QueryResult]:
        """Find objects that contradict ``anchor``, surfacing the explanatory edge.

        ``contradicts`` is symmetric, so both outgoing edges (anchor -> other)
        and incoming edges (other -> anchor) count. Each result records the
        actual stored direction in its path.
        """
        seen: set[str] = set()
        results: list[QueryResult] = []

        def _add(other: str, weight: float, step: ReasoningStep) -> None:
            if other in seen:
                return
            seen.add(other)
            obj = self.storage.get(other)
            results.append(
                QueryResult(
                    object_id=other,
                    content=obj.content if obj else "",
                    score=weight,
                    path=[step],
                    components={"geodesic": weight},
                )
            )

        for edge in self.storage.out_edges(anchor):
            if edge.relation == relation:
                _add(edge.target, edge.weight,
                     ReasoningStep(anchor, edge.relation, edge.target, edge.weight))

        if rel.properties(relation).symmetric:
            for source, edge in self.storage.in_edges(anchor):
                if edge.relation == relation:
                    _add(source, edge.weight,
                         ReasoningStep(source, edge.relation, anchor, edge.weight))

        return sorted(results, key=lambda r: r.score)
