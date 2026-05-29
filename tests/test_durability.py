from __future__ import annotations

import pickle
import threading

import pytest

from cookix import connect
from cookix.model import Edge, KnowledgeObject
from cookix.storage.durable import SNAPSHOT_FORMAT_VERSION, DurableBackend
from cookix.storage.wal import WriteAheadLog


def _obj(oid: str, edges=None) -> KnowledgeObject:
    return KnowledgeObject(
        id=oid, content=oid,
        edges=[Edge(r, t) for r, t in (edges or [])],
    )


# --------------------------------------------------------------------------- #
# WAL: durability + torn-write tolerance
# --------------------------------------------------------------------------- #
def test_wal_roundtrips_records(tmp_path):
    wal = WriteAheadLog(tmp_path / "w.log")
    wal.append({"op": "put", "id": "a"})
    wal.append({"op": "delete", "id": "b"})
    wal.close()
    assert WriteAheadLog(tmp_path / "w.log").replay() == [
        {"op": "put", "id": "a"}, {"op": "delete", "id": "b"}
    ]


def test_wal_drops_a_torn_final_frame(tmp_path):
    p = tmp_path / "w.log"
    wal = WriteAheadLog(p)
    wal.append({"op": "put", "id": "a"})
    wal.append({"op": "put", "id": "b"})
    wal.close()
    # Simulate a crash mid-append: chop the last few bytes off the file.
    raw = p.read_bytes()
    p.write_bytes(raw[:-3])
    # The first fully-durable record survives; the torn tail is discarded.
    assert WriteAheadLog(p).replay() == [{"op": "put", "id": "a"}]


# --------------------------------------------------------------------------- #
# Crash recovery: WAL replay onto the last snapshot
# --------------------------------------------------------------------------- #
def test_committed_writes_survive_a_crash_without_snapshot(tmp_path):
    db_dir = tmp_path / "db"
    backend = DurableBackend(db_dir, autosnapshot_ops=10_000)  # never auto-snapshots
    backend.put(_obj("x", [("causes", "y")]))
    backend.put(_obj("y"))
    # Simulate a crash: release the WAL handle WITHOUT snapshotting. The writes
    # were already fsync'd to the WAL, so it is the only record of them.
    backend._wal.close()

    reopened = DurableBackend(db_dir)
    assert "x" in reopened
    assert "y" in reopened
    assert reopened.out_edges("x")[0].target == "y"


def test_snapshot_then_more_writes_recover(tmp_path):
    db_dir = tmp_path / "db"
    b = DurableBackend(db_dir, autosnapshot_ops=10_000)
    b.put(_obj("a"))
    b.snapshot()          # 'a' is now in the snapshot, WAL cleared
    b.put(_obj("b"))      # 'b' is only in the WAL
    b._wal.close()        # crash before next snapshot
    r = DurableBackend(db_dir)
    assert "a" in r and "b" in r


# --------------------------------------------------------------------------- #
# Atomic transactions
# --------------------------------------------------------------------------- #
def test_transaction_commits_all_or_nothing(tmp_path):
    b = DurableBackend(tmp_path / "db", autosnapshot_ops=10_000)
    with b.transaction() as tx:
        tx.put(_obj("a"))
        tx.put(_obj("b"))
    assert len(b) == 2
    # Reopen: the committed batch is durable.
    b._wal.close()
    assert len(DurableBackend(tmp_path / "db")) == 2


def test_transaction_rolls_back_on_error(tmp_path):
    b = DurableBackend(tmp_path / "db", autosnapshot_ops=10_000)
    b.put(_obj("keep"))
    with pytest.raises(RuntimeError):
        with b.transaction() as tx:
            tx.put(_obj("dropped"))
            raise RuntimeError("boom")
    assert "keep" in b
    assert "dropped" not in b
    # And nothing from the failed txn was made durable.
    b._wal.close()
    r = DurableBackend(tmp_path / "db")
    assert "keep" in r and "dropped" not in r


# --------------------------------------------------------------------------- #
# Concurrency: many writers, no corruption, no lost updates
# --------------------------------------------------------------------------- #
def test_concurrent_writers_do_not_lose_updates(tmp_path):
    store = DurableBackend(tmp_path / "db", autosnapshot_ops=50)
    n_threads, per_thread = 8, 50

    def worker(t: int) -> None:
        for i in range(per_thread):
            store.put(_obj(f"t{t}_{i}"))

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert len(store) == n_threads * per_thread
    # Every write is durable after recovery — no corruption from interleaving.
    store.close()
    assert len(DurableBackend(tmp_path / "db")) == n_threads * per_thread


# --------------------------------------------------------------------------- #
# Backup / restore round-trip
# --------------------------------------------------------------------------- #
def test_backup_restore_round_trip_is_equivalent(tmp_path):
    b = DurableBackend(tmp_path / "db", autosnapshot_ops=10_000)
    for i in range(20):
        b.put(_obj(f"n{i}", [("causes", f"n{(i + 1) % 20}")]))
    backup_file = tmp_path / "backup.pkl"
    b.backup(backup_file)

    restored = DurableBackend.restore(backup_file, tmp_path / "db2")
    assert len(restored) == len(b)
    assert set(restored.all_ids()) == set(b.all_ids())
    assert restored.out_edges("n5")[0].target == "n6"


# --------------------------------------------------------------------------- #
# Group commit (Phase 14): correctness must hold in both modes
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("group_commit", [True, False])
def test_group_commit_modes_are_durable(tmp_path, group_commit):
    db_dir = tmp_path / f"db_{group_commit}"
    b = DurableBackend(db_dir, autosnapshot_ops=10_000, group_commit=group_commit)
    for i in range(100):
        b.put(_obj(f"n{i}"))
    assert len(b) == 100
    # Crash (drop the WAL handle) and recover: every write must survive.
    b._wal.close()
    assert len(DurableBackend(db_dir)) == 100


def test_group_commit_concurrent_writers_lose_nothing(tmp_path):
    store = DurableBackend(tmp_path / "db", autosnapshot_ops=10_000, group_commit=True)
    n_threads, per = 8, 60

    def worker(t: int) -> None:
        for i in range(per):
            store.put(_obj(f"t{t}_{i}"))

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert len(store) == n_threads * per
    store.close()
    assert len(DurableBackend(tmp_path / "db")) == n_threads * per


# --------------------------------------------------------------------------- #
# Read-only follower replicas (Phase 17)
# --------------------------------------------------------------------------- #
def test_read_replica_sees_committed_data_and_refuses_writes(tmp_path):
    primary = DurableBackend(tmp_path / "db", autosnapshot_ops=10_000)
    primary.put(_obj("a", [("causes", "b")]))
    primary.put(_obj("b"))

    replica = DurableBackend(tmp_path / "db", read_only=True)
    assert "a" in replica and "b" in replica
    assert replica.out_edges("a")[0].target == "b"

    with pytest.raises(RuntimeError, match="read-only"):
        replica.put(_obj("c"))
    with pytest.raises(RuntimeError, match="read-only"):
        with replica.transaction():
            pass


def test_read_replica_refresh_picks_up_new_writes(tmp_path):
    primary = DurableBackend(tmp_path / "db", autosnapshot_ops=10_000)
    primary.put(_obj("a"))

    replica = DurableBackend(tmp_path / "db", read_only=True)
    assert len(replica) == 1

    # Primary keeps writing; replica is stale until it refreshes.
    primary.put(_obj("b"))
    primary.put(_obj("c"))
    assert len(replica) == 1
    replica.refresh()
    assert len(replica) == 3 and "c" in replica


# --------------------------------------------------------------------------- #
# On-disk format versioning (migration guard)
# --------------------------------------------------------------------------- #
def test_snapshot_is_versioned_and_legacy_is_still_readable(tmp_path):
    b = DurableBackend(tmp_path / "db", autosnapshot_ops=10_000)
    b.put(_obj("a"))
    b.snapshot()
    with open(tmp_path / "db" / "snapshot.pkl", "rb") as fh:
        blob = pickle.load(fh)
    assert blob["format_version"] == SNAPSHOT_FORMAT_VERSION

    # A pre-versioning bare-dict snapshot must still load (read as legacy).
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    with open(legacy_dir / "snapshot.pkl", "wb") as fh:
        pickle.dump({"a": _obj("a")}, fh)
    assert "a" in DurableBackend(legacy_dir)


def test_future_format_version_is_refused(tmp_path):
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    with open(db_dir / "snapshot.pkl", "wb") as fh:
        pickle.dump({"format_version": SNAPSHOT_FORMAT_VERSION + 99, "objects": {}}, fh)
    with pytest.raises(ValueError, match="newer than this build"):
        DurableBackend(db_dir)


# --------------------------------------------------------------------------- #
# Database-level integration
# --------------------------------------------------------------------------- #
def test_database_transaction_via_durable_backend(tmp_path):
    db = connect(str(tmp_path / "db"), backend="durable")
    with db.transaction():
        db.insert({"_id": "umbrella", "content": "umbrella", "edges": [("prevents", "rain")]})
        db.insert({"_id": "rain", "content": "rain"})
    assert len(db) == 2
    results = db.query(anchor="umbrella", relation="prevents", mode="graph")
    assert results and results[0].object_id == "rain"
