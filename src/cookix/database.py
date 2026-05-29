"""The CookiX database: a MongoDB-style document interface over NoVectDB.

    import cookix

    db = cookix.connect("mydb")
    db.insert({"_id": "umbrella", "content": "an umbrella",
               "edges": [("prevents", "rain")]})
    results = db.query("What prevents rain?", k=5, mode="reasoning")
    for r in results:
        print(r.explain())

Documents are stored as Knowledge Objects. Queries return interpretable
reasoning paths, not scalar distances.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np

from . import topology
from .engine import EngineConfig, QueryEngine, RetrievalMode
from .extraction import Extractor, RuleBasedExtractor
from .model import KnowledgeObject, QueryResult
from .storage import StorageBackend, get_backend

# Aliases so users can pass friendly mode names to query().
_MODE_ALIASES = {
    "reasoning": RetrievalMode.FULL,
    "full": RetrievalMode.FULL,
    "graph": RetrievalMode.GRAPH_ONLY,
    "graph_only": RetrievalMode.GRAPH_ONLY,
    "topo": RetrievalMode.GRAPH_TOPO,
    "graph_topo": RetrievalMode.GRAPH_TOPO,
    "sheaf": RetrievalMode.GRAPH_SHEAF,
    "graph_sheaf": RetrievalMode.GRAPH_SHEAF,
}


class Database:
    """A topological-relational document store."""

    def __init__(
        self,
        storage: StorageBackend | None = None,
        config: EngineConfig | None = None,
        extractor: Extractor | None = None,
    ) -> None:
        # NB: an empty backend is falsy (``__len__ == 0``), so test against None
        # explicitly — ``storage or ...`` would silently discard a real backend.
        self.storage = storage if storage is not None else get_backend("memory")
        self.engine = QueryEngine(self.storage, config)
        self.extractor = extractor or RuleBasedExtractor()
        self._topo_dirty = False

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def insert(self, document: dict[str, Any] | KnowledgeObject) -> str:
        """Insert a document (dict or Knowledge Object). Returns the object id."""
        obj = (
            document
            if isinstance(document, KnowledgeObject)
            else KnowledgeObject.from_dict(document)
        )
        self.storage.put(obj)
        self._topo_dirty = True
        return obj.id

    def insert_many(self, documents: Iterable[dict[str, Any] | KnowledgeObject]) -> list[str]:
        return [self.insert(d) for d in documents]

    def insert_text(self, text: str, obj_id: str | None = None) -> list[str]:
        """Ingest free text: extract relational triples and store them.

        Each distinct subject/object becomes a Knowledge Object; each triple
        becomes a typed edge. Extraction quality depends on the configured
        extractor (see :mod:`cookix.extraction`).
        """
        triples = self.extractor.extract(text)
        ids: set[str] = set()
        for t in triples:
            for node in (t.subject, t.object):
                if node not in self.storage:
                    self.insert({"_id": node, "content": node})
                ids.add(node)
            obj = self.storage.get(t.subject)
            assert obj is not None
            obj.add_edge(t.relation, t.object, t.weight)
            self.storage.put(obj)
        self._topo_dirty = True
        return sorted(ids)

    def get(self, obj_id: str) -> KnowledgeObject | None:
        return self.storage.get(obj_id)

    def delete(self, obj_id: str) -> bool:
        deleted = self.storage.delete(obj_id)
        if deleted:
            self._topo_dirty = True
        return deleted

    def update(self, obj_id: str, *, content: str | None = None,
               add_edges: list[Any] | None = None) -> bool:
        """Patch an existing object's content and/or append edges."""
        obj = self.storage.get(obj_id)
        if obj is None:
            return False
        if content is not None:
            obj.content = content
        if add_edges:
            from .model import Edge

            obj.edges.extend(Edge.from_any(e) for e in add_edges)
        self.storage.put(obj)
        self._topo_dirty = True
        return True

    def __len__(self) -> int:
        return len(self.storage)

    def __contains__(self, obj_id: str) -> bool:
        return obj_id in self.storage

    # ------------------------------------------------------------------ #
    # Query
    # ------------------------------------------------------------------ #
    def query(
        self,
        query: str | None = None,
        *,
        anchor: str | None = None,
        relation: str | None = None,
        relation_chain: list[str] | None = None,
        target: str | None = None,
        k: int = 5,
        mode: str | RetrievalMode = RetrievalMode.FULL,
        max_hops: int | None = None,
    ) -> list[QueryResult]:
        """Run a relational query.

        Either pass a natural-language ``query`` string (parsed into an intent),
        or pass structured ``anchor``/``relation``/``target`` directly. ``mode``
        selects the retrieval layers (e.g. ``"reasoning"`` for the full pipeline,
        ``"graph"`` for the pure-traversal baseline).
        """
        mode_enum = _MODE_ALIASES.get(mode, mode) if isinstance(mode, str) else mode
        if mode_enum.use_topo:
            self._ensure_topology()

        if query is not None and anchor is None:
            intent = self.extractor.parse_intent(query, list(self.storage.all_ids()))
            anchor = intent.anchor
            target = target or intent.target
            # A relation parsed from natural language is a *hint*, not a hard
            # constraint: only apply it as a single-hop filter when no explicit
            # target was found. When a target is known, search for any path to
            # it so a phrasing mismatch (e.g. "compatible" vs the stored
            # "similar_to" edge) doesn't suppress the answer.
            if target is None and relation is None and relation_chain is None:
                relation = intent.relation

        if anchor is None:
            return []

        return self.engine.query(
            anchor=anchor,
            relation=relation,
            relation_chain=relation_chain,
            target=target,
            k=k,
            mode=mode_enum,
            max_hops=max_hops,
        )

    def contradictions(self, anchor: str) -> list[QueryResult]:
        """Find objects that contradict ``anchor`` (with explanatory paths)."""
        return self.engine.contradictions(anchor)

    # ------------------------------------------------------------------ #
    # Topology maintenance
    # ------------------------------------------------------------------ #
    def reindex_topology(self, r_hops: int = 2) -> int:
        """Recompute persistent-homology signatures for every object.

        Builds each object's r-hop neighbourhood as a weighted graph, derives a
        shortest-path distance matrix, and stores the vectorised barcode as the
        object's signature ``T``. No-op (returns 0) if the topology extra is not
        installed. Returns the number of signatures computed.
        """
        if not topology.AVAILABLE:
            return 0
        import networkx as nx

        graph = getattr(self.storage, "graph", None)
        if graph is None:
            return 0  # backend does not expose a graph (e.g. Kùzu): skip

        undirected = graph.to_undirected()
        count = 0
        for obj_id in list(self.storage.all_ids()):
            if obj_id not in undirected:
                continue
            nbrs = nx.single_source_shortest_path_length(undirected, obj_id, cutoff=r_hops)
            nodes = list(nbrs.keys())
            if len(nodes) < 2:
                continue
            sub = undirected.subgraph(nodes)
            dist = self._distance_matrix(sub, nodes)
            obj = self.storage.get(obj_id)
            if obj is not None:
                obj.topo_signature = topology.signature(dist)
                self.storage.put(obj)
                count += 1
        self._topo_dirty = False
        return count

    @staticmethod
    def _distance_matrix(subgraph: Any, nodes: list[str]) -> np.ndarray:
        import networkx as nx

        n = len(nodes)
        index = {node: i for i, node in enumerate(nodes)}
        lengths = dict(nx.all_pairs_dijkstra_path_length(subgraph, weight="weight"))
        big = float(n + 1)
        mat = np.full((n, n), big, dtype=float)
        for src, targets in lengths.items():
            for dst, d in targets.items():
                if src in index and dst in index:
                    mat[index[src], index[dst]] = d
        np.fill_diagonal(mat, 0.0)
        return mat

    def _ensure_topology(self) -> None:
        if self._topo_dirty:
            self.reindex_topology()

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def save(self, path: str) -> None:
        save = getattr(self.storage, "save", None)
        if save is None:
            raise NotImplementedError(f"{type(self.storage).__name__} does not support save()")
        save(path)

    def transaction(self):
        """An atomic, durable write batch (durable backend only).

        Usage::

            with db.transaction():
                db.insert(a)
                db.insert(b)   # both committed together, or neither on error

        Raises :class:`NotImplementedError` on backends without transactions.
        """
        txn = getattr(self.storage, "transaction", None)
        if txn is None:
            raise NotImplementedError(
                f"{type(self.storage).__name__} does not support transactions; "
                "use the 'durable' backend"
            )
        self._topo_dirty = True
        return txn()


def connect(
    name: str | None = None,
    *,
    backend: str = "memory",
    config: EngineConfig | None = None,
    extractor: Extractor | None = None,
    **backend_kwargs: Any,
) -> Database:
    """Open (or create) a CookiX database.

    Args:
        name: database name/path. For the Kùzu backend this is the on-disk path.
        backend: ``"memory"`` (default) or ``"kuzu"`` (durable).
        config: engine tuning (composite-distance weights, max hops, …).
        extractor: relation/intent extractor (defaults to rule-based).
        **backend_kwargs: forwarded to the backend factory.
    """
    if backend in ("kuzu", "durable") and name and "path" not in backend_kwargs:
        backend_kwargs["path"] = name
    storage = get_backend(backend, **backend_kwargs)
    return Database(storage=storage, config=config, extractor=extractor)
