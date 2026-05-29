"""A crash-safe, thread-safe durable storage backend.

This wraps the fast in-memory graph store with the three properties a production
database is expected to have but that a volatile store lacks:

* **Durability** — every mutation is written to a write-ahead log and fsync'd
  before it is acknowledged (:mod:`cookix.storage.wal`). On reopen, the backend
  loads its last snapshot and replays the WAL tail, so committed state survives a
  crash. A snapshot is an *atomic* file replace (temp file + ``os.replace``), so a
  crash mid-snapshot can never corrupt the previous good snapshot.

* **Atomic transactions** — :meth:`transaction` is an all-or-nothing write batch:
  mutations are buffered, then committed with a *single* fsync, so a crash leaves
  the store either fully before or fully after the batch, never halfway. An
  exception in the block discards the buffer (rollback) and writes nothing.

* **Thread safety** — a re-entrant lock serialises writers (single-writer,
  multi-reader). Concurrent ``put``/``delete`` from many threads cannot interleave
  into a corrupt graph or a corrupt log.

Read/traversal operations delegate to the in-memory backend unchanged, so the
query engine sees an identical interface and behaviour — durability is additive,
not a different data model.
"""

from __future__ import annotations

import os
import pickle
import threading
from collections.abc import Iterator
from pathlib import Path

from ..model import Edge, KnowledgeObject
from .base import StorageBackend
from .memory import InMemoryBackend
from .wal import WriteAheadLog

# On-disk snapshot format version. Bumped on any change to the serialised layout;
# load() refuses a newer version with a clear error rather than mis-reading it.
SNAPSHOT_FORMAT_VERSION = 1


class DurableBackend(StorageBackend):
    """In-memory speed with on-disk durability, atomic batches and locking."""

    def __init__(
        self, path: str | Path, *, autosnapshot_ops: int = 1000, group_commit: bool = True
    ) -> None:
        self.dir = Path(path)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._snap_path = self.dir / "snapshot.pkl"
        self._wal_path = self.dir / "wal.log"
        self._mem = InMemoryBackend()
        self._lock = threading.RLock()
        self._autosnapshot_ops = autosnapshot_ops
        self._ops_since_snapshot = 0
        self._in_txn = False
        self._txn_buffer: list[dict] = []

        # Group commit: concurrent writers each write their record under the main
        # lock (so the log stays ordered), then share a single fsync instead of
        # paying one fsync apiece. ``_write_seq`` counts ordered writes;
        # ``_synced_seq`` is the highest seq known durable. A writer is only
        # acknowledged once a sync has covered its seq.
        self.group_commit = group_commit
        self._write_seq = 0
        self._synced_seq = 0
        self._fsync_lock = threading.Lock()

        self._recover()
        self._wal = WriteAheadLog(self._wal_path)

    # ------------------------------------------------------------------ #
    # Recovery
    # ------------------------------------------------------------------ #
    @staticmethod
    def _load_snapshot(path: Path) -> dict[str, KnowledgeObject]:
        """Load a snapshot, validating the format version (migration guard)."""
        with open(path, "rb") as fh:
            blob = pickle.load(fh)
        if isinstance(blob, dict) and "format_version" in blob:
            version = blob["format_version"]
            if version > SNAPSHOT_FORMAT_VERSION:
                raise ValueError(
                    f"snapshot format v{version} is newer than this build supports "
                    f"(v{SNAPSHOT_FORMAT_VERSION}); upgrade CookiX to read it"
                )
            return blob["objects"]
        # Legacy bare-dict snapshot (pre-versioning) — read as v0.
        return blob

    def _recover(self) -> None:
        if self._snap_path.exists():
            for obj in self._load_snapshot(self._snap_path).values():
                self._mem.put(obj)
        if self._wal_path.exists():
            for record in WriteAheadLog(self._wal_path).replay():
                self._apply(record)

    def _apply(self, record: dict) -> None:
        if record["op"] == "put":
            self._mem.put(record["obj"])
        elif record["op"] == "delete":
            self._mem.delete(record["id"])

    # ------------------------------------------------------------------ #
    # Mutations (durable)
    # ------------------------------------------------------------------ #
    def _group_commit(self, seq: int) -> None:
        """Ensure write ``seq`` is durable, sharing one fsync across writers.

        If another writer already synced past ``seq`` our bytes are durable and we
        return immediately; otherwise we take the fsync lock and sync everything
        written so far (>= ``seq``), covering every concurrent writer at once.
        """
        if self._synced_seq >= seq:
            return
        with self._fsync_lock:
            if self._synced_seq >= seq:
                return
            target = self._write_seq  # everything written up to now
            self._wal.sync()
            self._synced_seq = max(self._synced_seq, target)

    def _durable_write(self, record: dict) -> None:
        """Apply + persist a single record, via group commit when enabled."""
        if self.group_commit:
            with self._lock:
                self._wal.append_nosync(record)
                self._apply(record)
                self._write_seq += 1
                seq = self._write_seq
            self._group_commit(seq)  # fsync outside the main lock
            with self._lock:
                self._maybe_snapshot()
        else:
            with self._lock:
                self._wal.append(record)
                self._apply(record)
                self._write_seq += 1
                self._synced_seq = self._write_seq
                self._maybe_snapshot()

    def put(self, obj: KnowledgeObject) -> None:
        record = {"op": "put", "obj": obj}
        with self._lock:
            if self._in_txn:
                self._txn_buffer.append(record)
                return
        self._durable_write(record)

    def delete(self, obj_id: str) -> bool:
        with self._lock:
            if self._in_txn:
                # Buffer optimistically; report presence against current state.
                exists = obj_id in self._mem or any(
                    r["op"] == "put" and r["obj"].id == obj_id for r in self._txn_buffer
                )
                self._txn_buffer.append({"op": "delete", "id": obj_id})
                return exists
            if obj_id not in self._mem:
                return False
        self._durable_write({"op": "delete", "id": obj_id})
        return True

    # ------------------------------------------------------------------ #
    # Transactions (atomic write batch)
    # ------------------------------------------------------------------ #
    class _Txn:
        def __init__(self, backend: DurableBackend) -> None:
            self._backend = backend

        def __enter__(self) -> DurableBackend:
            self._backend._begin()
            return self._backend

        def __exit__(self, exc_type, exc, tb) -> bool:
            if exc_type is None:
                self._backend._commit()
            else:
                self._backend._rollback()
            return False  # never suppress exceptions

    def transaction(self) -> _Txn:
        """An atomic, durable write batch. Commits on clean exit, rolls back on error."""
        return DurableBackend._Txn(self)

    def _begin(self) -> None:
        self._lock.acquire()  # held for the whole transaction: serialisable writers
        self._in_txn = True
        self._txn_buffer = []

    def _commit(self) -> None:
        try:
            batch = self._txn_buffer
            self._txn_buffer = []
            self._in_txn = False
            if batch:
                self._wal.append_batch(batch)  # one fsync: all-or-nothing
                for record in batch:
                    self._apply(record)
                # The batch is durable; advance both counters together.
                self._write_seq += len(batch)
                self._synced_seq = self._write_seq
                self._ops_since_snapshot += len(batch)
                self._maybe_snapshot()
        finally:
            self._lock.release()

    def _rollback(self) -> None:
        self._txn_buffer = []
        self._in_txn = False
        self._lock.release()

    # ------------------------------------------------------------------ #
    # Snapshot / backup (atomic)
    # ------------------------------------------------------------------ #
    def _maybe_snapshot(self) -> None:
        self._ops_since_snapshot += 1
        if self._ops_since_snapshot >= self._autosnapshot_ops:
            self.snapshot()

    def snapshot(self) -> None:
        """Fold the WAL into an atomic on-disk snapshot, then clear the WAL."""
        with self._lock:
            self._atomic_write_snapshot(self._snap_path)
            # Hold the fsync lock while truncating so we never close/reopen the
            # WAL file out from under a concurrent group-commit ``sync()``.
            with self._fsync_lock:
                self._wal.truncate()
            self._ops_since_snapshot = 0

    def _atomic_write_snapshot(self, dest: Path) -> None:
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        envelope = {
            "format_version": SNAPSHOT_FORMAT_VERSION,
            "objects": self._mem._objects,
        }
        with open(tmp, "wb") as fh:
            pickle.dump(envelope, fh, protocol=pickle.HIGHEST_PROTOCOL)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, dest)  # atomic on POSIX and Windows

    def backup(self, dest: str | Path) -> None:
        """Write a standalone, point-in-time snapshot to ``dest`` (atomic)."""
        with self._lock:
            self._atomic_write_snapshot(Path(dest))

    @classmethod
    def restore(cls, backup_path: str | Path, into: str | Path) -> DurableBackend:
        """Rebuild a fresh durable store at ``into`` from a ``backup`` snapshot."""
        into = Path(into)
        into.mkdir(parents=True, exist_ok=True)
        objects = cls._load_snapshot(Path(backup_path))
        backend = cls(into)
        with backend.transaction() as tx:
            for obj in objects.values():
                tx.put(obj)
        backend.snapshot()
        return backend

    # ------------------------------------------------------------------ #
    # Reads (delegate to the in-memory graph)
    # ------------------------------------------------------------------ #
    def get(self, obj_id: str) -> KnowledgeObject | None:
        with self._lock:
            return self._mem.get(obj_id)

    def __contains__(self, obj_id: str) -> bool:
        with self._lock:
            return obj_id in self._mem

    def __len__(self) -> int:
        with self._lock:
            return len(self._mem)

    def all_ids(self) -> Iterator[str]:
        with self._lock:
            return self._mem.all_ids()

    def out_edges(self, obj_id: str) -> list[Edge]:
        with self._lock:
            return self._mem.out_edges(obj_id)

    def in_edges(self, obj_id: str) -> list[tuple[str, Edge]]:
        with self._lock:
            return self._mem.in_edges(obj_id)

    @property
    def graph(self):
        """Underlying NetworkX graph (read-only use by the engine's topology pass)."""
        return self._mem.graph

    def close(self) -> None:
        with self._lock:
            self.snapshot()
            self._wal.close()
