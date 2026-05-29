"""Embedded property-graph backend built on Kùzu.

Kùzu is an embedded, columnar property-graph database ("SQLite for graphs").
It gives CookiX durable, on-disk storage and fast type-filtered traversal
without running a server. This backend is optional::

    pip install "cookix[kuzu]"

It is intentionally schema-light: a single ``KObject`` node table and a single
``REL`` relationship table carrying the relation type as a property, which keeps
the controlled vocabulary open-ended.

Semantics are kept at **parity** with :class:`~cookix.storage.memory.InMemoryBackend`:

* A node referenced only as an edge *target* (a "dangling" target that was never
  explicitly inserted) is materialised with ``materialized = false`` and is
  invisible to :meth:`get`, :meth:`__contains__`, :meth:`__len__` and
  :meth:`all_ids` — exactly as a dangling target is in the memory backend — yet
  remains traversable as an edge endpoint until it is inserted for real.
* :meth:`put` replaces only the object's **outgoing** edges; incoming edges from
  other objects survive, so materialising a previously-dangling target never
  destroys the edges that pointed at it.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from ..model import Edge, KnowledgeObject
from .base import StorageBackend


class KuzuBackend(StorageBackend):
    """Durable graph store backed by an embedded Kùzu database."""

    def __init__(self, path: str) -> None:
        try:
            import kuzu  # noqa: F401
        except ImportError as exc:  # pragma: no cover - depends on optional dep
            raise ImportError(
                "KuzuBackend requires the 'kuzu' package. Install with: "
                'pip install "cookix[kuzu]"'
            ) from exc
        import kuzu

        self._db = kuzu.Database(path)
        self._conn = kuzu.Connection(self._db)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            "CREATE NODE TABLE IF NOT EXISTS KObject("
            "id STRING, content STRING, meta STRING, materialized BOOLEAN, PRIMARY KEY(id))"
        )
        self._conn.execute(
            "CREATE REL TABLE IF NOT EXISTS REL("
            "FROM KObject TO KObject, relation STRING, weight DOUBLE, meta STRING)"
        )

    def put(self, obj: KnowledgeObject) -> None:
        # Upsert the node and promote it to materialised, preserving any incoming
        # edges (a previously-dangling target keeps the edges that point at it).
        self._conn.execute(
            "MERGE (o:KObject {id: $id}) "
            "SET o.content = $content, o.meta = $meta, o.materialized = true",
            {"id": obj.id, "content": obj.content, "meta": json.dumps(obj.meta)},
        )
        # Replace semantics: drop only this object's existing outgoing edges.
        self._conn.execute("MATCH (s:KObject {id: $id})-[r:REL]->() DELETE r", {"id": obj.id})
        for edge in obj.edges:
            # Target must exist; a brand-new target is dangling (not materialised).
            self._conn.execute(
                "MERGE (t:KObject {id: $tid}) "
                "ON CREATE SET t.content = '', t.meta = '{}', t.materialized = false",
                {"tid": edge.target},
            )
            self._conn.execute(
                "MATCH (s:KObject {id: $sid}), (t:KObject {id: $tid}) "
                "CREATE (s)-[:REL {relation: $rel, weight: $w, meta: $meta}]->(t)",
                {"sid": obj.id, "tid": edge.target, "rel": edge.relation,
                 "w": edge.weight, "meta": json.dumps(edge.meta)},
            )

    def get(self, obj_id: str) -> KnowledgeObject | None:
        res = self._conn.execute(
            "MATCH (o:KObject {id: $id}) WHERE o.materialized RETURN o.content, o.meta",
            {"id": obj_id},
        )
        if not res.has_next():
            return None
        content, meta = res.get_next()
        obj = KnowledgeObject(id=obj_id, content=content, meta=json.loads(meta or "{}"))
        obj.edges = self.out_edges(obj_id)
        return obj

    def delete(self, obj_id: str) -> bool:
        if obj_id not in self:
            return False
        self._conn.execute("MATCH (o:KObject {id: $id}) DETACH DELETE o", {"id": obj_id})
        return True

    def __contains__(self, obj_id: str) -> bool:
        res = self._conn.execute(
            "MATCH (o:KObject {id: $id}) WHERE o.materialized RETURN count(o)", {"id": obj_id}
        )
        return bool(res.has_next() and res.get_next()[0] > 0)

    def __len__(self) -> int:
        res = self._conn.execute("MATCH (o:KObject) WHERE o.materialized RETURN count(o)")
        return int(res.get_next()[0]) if res.has_next() else 0

    def all_ids(self) -> Iterator[str]:
        res = self._conn.execute("MATCH (o:KObject) WHERE o.materialized RETURN o.id")
        while res.has_next():
            yield res.get_next()[0]

    def out_edges(self, obj_id: str) -> list[Edge]:
        res = self._conn.execute(
            "MATCH (s:KObject {id: $id})-[r:REL]->(t:KObject) "
            "RETURN r.relation, t.id, r.weight, r.meta", {"id": obj_id}
        )
        edges = []
        while res.has_next():
            rel, tid, w, meta = res.get_next()
            edges.append(Edge(relation=rel, target=tid, weight=w, meta=json.loads(meta or "{}")))
        return edges

    def in_edges(self, obj_id: str) -> list[tuple[str, Edge]]:
        res = self._conn.execute(
            "MATCH (s:KObject)-[r:REL]->(t:KObject {id: $id}) "
            "RETURN s.id, r.relation, r.weight, r.meta", {"id": obj_id}
        )
        result = []
        while res.has_next():
            sid, rel, w, meta = res.get_next()
            result.append((sid, Edge(relation=rel, target=obj_id, weight=w,
                                    meta=json.loads(meta or "{}"))))
        return result

    def close(self) -> None:  # pragma: no cover - optional lifecycle hook
        self._conn.close()
        self._db.close()
