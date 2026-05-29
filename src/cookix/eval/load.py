"""Load & soak testing for the CookiX HTTP server (Phase 13).

The scaling benchmark (`cookix eval --scale`) times the engine in-process. This
goes further: it stands up the **real HTTP server** on a socket and drives it
with many **concurrent clients** for a chosen duration, so we measure what a
deployment actually experiences — throughput, tail latency, error rate — and,
over a long run (a *soak*), whether memory grows (a leak) or stays flat.

It is deliberately dependency-light: the server is `uvicorn` (the `server`
extra), clients use stdlib `urllib` over real sockets in a thread pool, and
memory is read best-effort (psutil if present, else OS-native).

Run a quick check::

    cookix loadtest --duration 10 --workers 8 --objects 5000

Run a soak (watch the memory columns for growth)::

    cookix loadtest --duration 1800 --workers 16 --objects 50000
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from dataclasses import dataclass
from statistics import median

from .. import connect
from .perf import _percentile, _scale_graph


def _rss_mb() -> float | None:
    """Resident set size in MB, best-effort and cross-platform."""
    try:
        import psutil  # type: ignore

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        pass
    import sys

    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class _PMC(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            k32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi
            # Declare signatures so the 64-bit pseudo-handle isn't truncated.
            k32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            counters = _PMC()
            counters.cb = ctypes.sizeof(_PMC)
            if psapi.GetProcessMemoryInfo(
                k32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
            ):
                return counters.WorkingSetSize / (1024 * 1024)
        except Exception:
            return None
    else:
        try:
            import resource

            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # ru_maxrss is bytes on macOS, kilobytes on Linux.
            divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
            return rss / divisor
        except Exception:
            return None
    return None


@dataclass
class LoadReport:
    objects: int
    workers: int
    duration_s: float
    requests: int
    errors: int
    rps: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    mem_start_mb: float | None
    mem_peak_mb: float | None
    mem_end_mb: float | None

    @property
    def error_rate(self) -> float:
        return self.errors / self.requests if self.requests else 0.0

    @property
    def mem_growth_mb(self) -> float | None:
        if self.mem_start_mb is None or self.mem_end_mb is None:
            return None
        return self.mem_end_mb - self.mem_start_mb


def _start_server(app, host: str, port: int):
    """Start uvicorn in a background thread; return (server, thread)."""
    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):  # up to ~10s for startup
        if server.started:
            break
        time.sleep(0.05)
    return server, thread


def run_load_test(
    objects: int = 5_000,
    workers: int = 8,
    duration_s: float = 10.0,
    host: str = "127.0.0.1",
    port: int = 8917,
    avg_degree: int = 4,
    seed: int = 0,
) -> LoadReport:
    """Drive the real HTTP server with ``workers`` concurrent clients for ``duration_s``.

    Each client issues anchor-only multi-hop queries against a pre-built graph of
    ``objects`` nodes. Returns throughput, tail latency, error rate, and memory
    samples (start / peak / end) for leak detection over long soaks.
    """
    from ..server import create_app

    db = connect("loadtest")
    db.insert_many(_scale_graph(objects, avg_degree, seed))
    app = create_app(db)
    server, thread = _start_server(app, host, port)

    url = f"http://{host}:{port}/api/query"
    deadline = time.time() + duration_s
    latencies: list[float] = []
    errors = [0]
    lock = threading.Lock()
    mem_samples: list[float] = []

    def sample_memory() -> None:
        while time.time() < deadline:
            m = _rss_mb()
            if m is not None:
                mem_samples.append(m)
            time.sleep(0.5)

    def worker(wid: int) -> None:
        local: list[float] = []
        local_err = 0
        i = 0
        while time.time() < deadline:
            anchor = f"n{(wid * 7919 + i * 31) % objects}"
            body = json.dumps({"anchor": anchor, "mode": "graph", "k": 5}).encode()
            req = urllib.request.Request(
                url, data=body, headers={"Content-Type": "application/json"}, method="POST"
            )
            t = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp.read()
                    if resp.status != 200:
                        local_err += 1
            except Exception:
                local_err += 1
            local.append((time.perf_counter() - t) * 1000.0)
            i += 1
        with lock:
            latencies.extend(local)
            errors[0] += local_err

    start_mem = _rss_mb()
    mem_thread = threading.Thread(target=sample_memory, daemon=True)
    mem_thread.start()

    threads = [threading.Thread(target=worker, args=(w,)) for w in range(workers)]
    actual_start = time.time()
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    elapsed = time.time() - actual_start
    end_mem = _rss_mb()

    server.should_exit = True
    thread.join(timeout=5)

    n = len(latencies)
    return LoadReport(
        objects=objects,
        workers=workers,
        duration_s=elapsed,
        requests=n,
        errors=errors[0],
        rps=(n / elapsed) if elapsed > 0 else 0.0,
        median_ms=median(latencies) if latencies else 0.0,
        p95_ms=_percentile(latencies, 95.0),
        p99_ms=_percentile(latencies, 99.0),
        mem_start_mb=start_mem,
        mem_peak_mb=max(mem_samples) if mem_samples else None,
        mem_end_mb=end_mem,
    )


def to_markdown_load(report: LoadReport) -> str:
    def _mb(v: float | None) -> str:
        return f"{v:.1f} MB" if v is not None else "n/a"

    growth = report.mem_growth_mb
    lines = [
        "### Load / soak: HTTP server",
        "",
        f"{report.objects:,} objects · {report.workers} concurrent clients · "
        f"{report.duration_s:.1f}s",
        "",
        f"- **Throughput:** {report.rps:,.0f} req/s ({report.requests:,} requests)",
        f"- **Errors:** {report.errors} ({report.error_rate * 100:.3f}%)",
        f"- **Latency:** median {report.median_ms:.2f} ms · "
        f"p95 {report.p95_ms:.2f} ms · p99 {report.p99_ms:.2f} ms",
        f"- **Memory:** start {_mb(report.mem_start_mb)} · peak {_mb(report.mem_peak_mb)} · "
        f"end {_mb(report.mem_end_mb)}"
        + (f" · growth {growth:+.1f} MB" if growth is not None else ""),
        "",
        "A flat memory `growth` over a long `--duration` is the soak signal: the "
        "read path holds no leak. Throughput/latency are machine-dependent.",
    ]
    return "\n".join(lines)
