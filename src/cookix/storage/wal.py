"""A crash-safe write-ahead log (WAL).

Durability for a database means: once an operation is acknowledged, it survives a
crash. The standard mechanism is a write-ahead log — every mutation is appended
to an on-disk log and flushed *before* it is acknowledged, so recovery can replay
the log onto the last snapshot.

Two correctness properties this implementation guarantees:

* **Durability on commit** — :meth:`append` (and :meth:`append_batch`) flush the
  Python buffer and ``os.fsync`` the file descriptor before returning, so an
  acknowledged record is on stable storage.
* **Torn-write tolerance** — each record is framed as a 4-byte big-endian length
  followed by that many bytes of pickled payload, terminated by a 4-byte CRC32 of
  the payload. On replay, a final record whose length runs past EOF, or whose CRC
  does not match (a half-written tail from a crash mid-append), is discarded — the
  log recovers to the last *fully durable* record rather than raising.

Pickle is used (not JSON) because Knowledge Objects carry numpy arrays; the WAL
is a local, trusted file, never a deserialisation surface for external input.
"""

from __future__ import annotations

import os
import pickle
import struct
import zlib
from pathlib import Path
from typing import Any

_LEN = struct.Struct(">I")  # 4-byte big-endian frame length
_CRC = struct.Struct(">I")  # 4-byte big-endian CRC32 trailer


class WriteAheadLog:
    """Append-only, fsync-on-commit, torn-write-tolerant record log."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._fh = open(self.path, "ab")  # noqa: SIM115 (kept open for the WAL's lifetime)

    def _frame(self, record: Any) -> bytes:
        payload = pickle.dumps(record, protocol=pickle.HIGHEST_PROTOCOL)
        return _LEN.pack(len(payload)) + payload + _CRC.pack(zlib.crc32(payload))

    def append_nosync(self, record: Any) -> None:
        """Write one record to the OS buffer **without** an fsync.

        The bytes are handed to the kernel but not yet guaranteed durable; a
        later :meth:`sync` makes every preceding ``append_nosync`` durable in one
        barrier. This is the primitive group-commit batches many writers onto.
        """
        self._fh.write(self._frame(record))
        self._fh.flush()

    def sync(self) -> None:
        """Force everything written so far to stable storage (one fsync)."""
        os.fsync(self._fh.fileno())

    def append(self, record: Any) -> None:
        """Append one record and flush it to stable storage before returning."""
        self.append_nosync(record)
        self.sync()

    def append_batch(self, records: list[Any]) -> None:
        """Append many records with a *single* fsync — the atomic-commit path.

        Either all frames reach stable storage or (on a crash mid-write) the
        trailing partial frame is dropped on replay, so a batch never applies
        half a transaction's worth of durable records past the torn point.
        """
        if not records:
            return
        blob = b"".join(self._frame(r) for r in records)
        self._fh.write(blob)
        self._fh.flush()
        os.fsync(self._fh.fileno())

    @staticmethod
    def read_records(path: str | Path) -> list[Any]:
        """Read all fully-durable records from ``path`` without opening it for append.

        Used by recovery and by read-only replicas, which must not hold a writable
        handle on the primary's log.
        """
        path = Path(path)
        if not path.exists():
            return []
        records: list[Any] = []
        with open(path, "rb") as fh:
            data = fh.read()
        off, n = 0, len(data)
        while off + _LEN.size <= n:
            (length,) = _LEN.unpack(data[off:off + _LEN.size])
            start = off + _LEN.size
            end = start + length
            if end + _CRC.size > n:
                break
            payload = data[start:end]
            (crc,) = _CRC.unpack(data[end:end + _CRC.size])
            if zlib.crc32(payload) != crc:
                break
            records.append(pickle.loads(payload))
            off = end + _CRC.size
        return records

    def replay(self) -> list[Any]:
        """Return every fully-durable record, stopping at the first torn frame."""
        records: list[Any] = []
        with open(self.path, "rb") as fh:
            data = fh.read()
        off, n = 0, len(data)
        while off + _LEN.size <= n:
            (length,) = _LEN.unpack(data[off:off + _LEN.size])
            start = off + _LEN.size
            end = start + length
            if end + _CRC.size > n:
                break  # truncated payload/CRC — crash tail, stop
            payload = data[start:end]
            (crc,) = _CRC.unpack(data[end:end + _CRC.size])
            if zlib.crc32(payload) != crc:
                break  # corrupt/torn final frame — stop
            records.append(pickle.loads(payload))
            off = end + _CRC.size
        return records

    def truncate(self) -> None:
        """Empty the log (called after a successful snapshot folds it in)."""
        self._fh.close()
        self._fh = open(self.path, "wb")  # noqa: SIM115
        self._fh.flush()
        os.fsync(self._fh.fileno())

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.flush()
            os.fsync(self._fh.fileno())
            self._fh.close()
