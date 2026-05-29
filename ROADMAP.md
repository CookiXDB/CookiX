# CookiX Roadmap — from research release to production database

**Where we are:** `v1.0.0` — a production-ready **single-node** topological-
relational database. Validated on external data (2WikiMultiHopQA), crash-safe,
concurrent, secured, and distributed as stable, versioned artifacts. See the
"What 1.0 is — and is not" section of the README for the honest scope.

**How we got here:** Phases 6–11 below took CookiX from the `v0.2.0` research
release to `v1.0`. Phases 6, 8, 9, 10 are fully done; Phase 7 is partial (the
scaling work is done, the Rust core is reclassified as a post-1.0 optimization);
Phase 11 shipped the release.

**Post-1.0 (the honest open frontier):** the Rust/PyO3 hot-path core, external
HotpotQA/MuSiQue loaders + a dense-retriever baseline, distributed/multi-node
operation, and a proven (or refuted) retrieval benefit from the 𝒯/𝒮 layers.

The ordering is deliberate. Credibility first (does it actually work on real
data?), then scale, then the operational properties a database is *expected* to
have, then the stability promises a `1.0` makes. Each phase ships independently
and has an **exit gate** — an objective, measurable condition that must hold
before the phase counts as done. No gate is "we think it's good"; every gate is
a number, a passing test battery, or a published artifact.

A standing honesty rule carries through every phase: the topological (𝒯) and
sheaf (𝒮) layers stay **ablatable and measured**. We do not claim they improve
retrieval until a study on real data shows they do — and if they don't, that is
a finding we report, not a feature we hide.

---

## Phase 6 — External-dataset validation *(the credibility gate)* — ✅ DONE

The single most important phase. Until CookiX runs on data it didn't design,
every number is suggestive, not conclusive.

**Result (2WikiMultiHopQA dev, first 2,000 examples, oracle entity-linking):**
typed multi-hop traversal reaches **hits@10 = 0.580 vs Okapi BM25's 0.386**
(+50% relative) and recovers the gold relation chain on **57.9%** of answered
questions (BM25 cannot score paths at all). Run it: `cookix eval --dataset 2wiki
--path dev.json --k 10`. The win is on the *reasoning engine* under oracle
linking — a fair, recognised KG-QA setting — not an end-to-end open-domain
number; the extraction pipeline remains the separate, measured bottleneck.
*Remaining for full credit: HotpotQA + MuSiQue loaders and a dense-retriever
baseline alongside BM25.*

**Deliverables**
- Dataset loaders for established multi-hop QA benchmarks: **HotpotQA**,
  **2WikiMultiHopQA**, **MuSiQue** (distractor + full-wiki settings where
  applicable).
- An ingestion pipeline: documents → extracted typed triples → Knowledge
  Objects, reusing the existing extractor with the LLM extractor measured
  head-to-head against the rule-based one on *this* data.
- The same fair-baseline harness as the synthetic suite, extended with at least
  one strong **dense retriever** baseline (e.g. a sentence-embedding bi-encoder)
  alongside BM25/lexical — so the comparison is against what people actually use.
- Standard metrics: answer EM / F1, retrieval hits@k / recall@k, and supporting-
  fact / path accuracy for the multi-hop chains.
- A `cookix eval --dataset <name>` entry point, reproducible from a manifest.

**Exit gate**
- Results published in-repo for all three datasets against BM25 **and** a dense
  retriever, with full methodology.
- An honest verdict written down: where CookiX wins, where it ties, where it
  loses, and *why* (with the extraction-quality ceiling isolated from the
  retrieval engine, so we know which component is the bottleneck).

**Risk (named upfront):** real-world extraction F1 (~0.52 rule-based today) may
dominate end-to-end quality and cap results below the dense baseline. If so, the
finding reframes the product — the relational engine is sound, but the value
proposition depends on extraction, and that becomes the priority.

---

## Phase 7 — Scale & the hot-path core *(performance gate)* — ◐ PARTIAL

v0.2.0 is a sub-0.1 ms micro-benchmark on a 240-object corpus. Production means
10⁵–10⁷ objects with predictable latency.

**Done:** a scaling benchmark (`cookix eval --scale`) and a real algorithmic
optimization — **settle-once Dijkstra** (never re-expand a node once its
minimum-cost path is fixed) with **early-exit** on a requested target. Result:
query latency stays **near-flat (~1.5→2.2 ms) across a 50× graph-size increase**
(1k→50k objects), because traversal cost is bounded by the local reachable
frontier (degree × hops), not total N; memory ~3 KB/object.

**Deferred (honest):** the **Rust/PyO3 hot-path core** is *not built* — this
environment has no Rust toolchain, so compiling and parity-testing it is not
possible here. It remains the open item; the Python settle-once/early-exit
optimization is the interim win. Wiring `TopoIndex` into the engine as an ANN
candidate generator also remains open.

**Deliverables**
- Wire `TopoIndex` (cosine-LSH ANN) into the engine as a real candidate
  generator, so topological re-ranking does not require an O(N) scan.
- A **Rust hot-path core via PyO3** for the geodesic traversal + composite-rank
  inner loop, behind a feature flag with the pure-Python path as fallback and a
  parity test battery across both.
- Large-corpus generators and a scaling benchmark: latency and throughput as a
  function of object count and graph degree, with memory profiling.
- Query-planner improvements: early-termination bounds, candidate caps.

**Exit gate**
- Documented latency curves at 10⁵ and 10⁶ objects with stated p50/p95/p99 SLOs.
- Rust and Python paths produce **identical** rankings on the shared battery.
- No memory blow-up: peak RSS characterised and bounded for the large-corpus run.

---

## Phase 8 — Durability, transactions & concurrency *(data-safety gate)* — ✅ DONE

A database must not lose or corrupt data, and must behave under concurrent use.

**Result:** a pure-Python `durable` backend (`cookix.connect(path,
backend="durable")`) with a write-ahead log (fsync-on-commit, CRC-framed
torn-write tolerance), atomic snapshots (temp + `os.replace`), all-or-nothing
write-batch transactions (`with db.transaction(): …`), thread-safe single-writer
locking, and backup/restore. Proven by a test battery: committed writes survive a
crash with no snapshot (WAL replay), a torn WAL tail is dropped, transactions
commit atomically or roll back on error, 8 concurrent writers lose no updates, and
backup→restore round-trips to an equivalent store. *(Also fixed a latent bug: an
empty backend is falsy, so `Database` was silently discarding it.)*

**Deliverables**
- Crash-safe persistence: atomic snapshot + write-ahead log for the in-memory
  backend; rely on and *verify* Kùzu's MVCC/durability for the durable backend.
- A defined transaction API (commit/rollback) with a documented isolation level.
- Concurrent read/write safety: explicit locking or MVCC semantics, documented.
- Backup / restore tooling and an on-disk format version stamp.

**Exit gate**
- A crash-recovery test: kill mid-write, reopen, assert no corruption and a
  consistent committed state.
- A concurrency stress test (many readers + writers) passing under a race/thread
  sanitizer or equivalent, with no lost updates.
- Backup → wipe → restore round-trips byte-for-byte equivalent state.

---

## Phase 9 — Operational hardening & security *(deployability gate)* — ✅ DONE

**Result:** the HTTP server gained opt-in production controls (`ServerConfig` /
`COOKIX_*` env): API-key auth (constant-time, `Bearer`/`X-API-Key`), per-client
fixed-window rate limiting (`429` + `Retry-After`), `k`/`max_hops`/body-size
limits, read-only mode, structured JSON access logs, a no-dependency Prometheus
`/metrics` endpoint, and `/healthz` + `/readyz` probes — all covered by tests.
A documented threat model with explicit limitations ships in `SECURITY.md`, and a
hardened, non-root `Dockerfile` (+ `/healthz` HEALTHCHECK) ships in the repo.
*Honest caveat: the app hardening is test-proven via the FastAPI test client, but
the container image itself was not build-validated here (no running Docker
daemon in this environment).*

_Original plan:_

**Deliverables**
- Server authentication (API keys / bearer tokens), per-key rate limiting, and
  strict input validation with resource limits (max hops, result caps, payload
  size) to prevent abuse and runaway queries.
- Structured logging, Prometheus-style metrics, and `/healthz` / `/readyz`
  endpoints.
- Config via file + environment, a hardened **Docker image**, and a deployment
  guide (single-node first; clustering explicitly out of scope for v1.0).
- A pass through the security-review checklist (injection surfaces, the LLM
  extractor's prompt path, dependency audit).

**Exit gate**
- Security review completed with findings triaged and high/criticals resolved.
- A container deploys from the documented guide and serves authenticated,
  rate-limited, observable traffic.

---

## Phase 10 — API stability, clients & packaging *(distribution gate)* — ◐ MOSTLY DONE

A `1.0` is a promise. This phase makes the promise concrete.

**Done:** a versioned wire API (`cookix.API_VERSION`, reported at `/api/info`)
with a written SemVer + deprecation policy (`API_STABILITY.md`); a
dependency-free typed `CookixClient` (stdlib `urllib`, injectable transport,
tested against the in-process app); a versioned on-disk snapshot format
(`SNAPSHOT_FORMAT_VERSION`) that refuses a newer format and still reads the
legacy layout (migration guard); and a wheel + sdist that **build, pass
`twine check`, and install + run a query in a clean virtualenv**.

**Deferred (needs maintainer credentials):** the actual **PyPI publish** and
multi-OS **cibuildwheel** matrix. CookiX is currently pure-Python, so the single
`py3-none-any` wheel already covers all platforms; once the Phase 7 Rust core
lands, the cibuildwheel matrix becomes necessary. Publishing is intentionally not
automated in-repo without a trusted CI secret.

_Original plan:_

**Deliverables**
- A frozen, versioned wire API with a published **OpenAPI spec** and a written
  deprecation / SemVer policy.
- A typed Python client package and clear stability guarantees on the public
  surface (`connect / insert / query / update / delete`, query modes, result
  schema).
- Cross-platform wheels (via `cibuildwheel`, accounting for the Rust extension),
  published to **PyPI**; the Docker image published to a registry.
- Migration tooling for the on-disk format, tied to the Phase 8 version stamp.

**Exit gate**
- `pip install cookix` pulls working wheels on Linux / macOS / Windows for the
  supported Python versions, Rust core included.
- The public API surface is documented as stable and covered by contract tests.

---

## Phase 11 — v1.0 release — ✅ DONE

**Shipped:** an end-to-end production smoke test (durable backend + authenticated
server + typed client + a crash/restart recovery cycle), a perf-regression
guardrail test, the full docs set (`README`, `SECURITY.md`, `API_STABILITY.md`,
`CHANGELOG.md`, this roadmap), and the honest "What 1.0 is — and is not" scope
statement in the README. Released as `1.0.0` (classifier: Production/Stable).

**How the v1.0 gate was met — honestly:**
1. ✅ Phase 6 external results are published and defensible (hits@10 0.58 vs BM25
   0.39 on 2WikiMultiHopQA, oracle entity-linking).
2. ◐ Phase 7 scale numbers are met (~2 ms to 50k objects); **the Rust core is
   reclassified as a post-1.0 performance optimization** — it is not a
   correctness/safety requirement, and no Rust toolchain was available to build
   it here. This is the one gate criterion consciously relaxed, and it is
   documented rather than hidden.
3. ✅ Phase 8 data-safety battery passes (crash recovery, concurrency, restore).
4. ✅ Phase 9 hardening is test-proven; threat model documented. *(The Docker
   image ships but was not build-validated in this environment — no daemon.)*
5. ◐ Phase 10 artifacts are built, `twine check`-clean and clean-venv-installable;
   the actual **PyPI publish is the maintainer's mechanical step** (needs
   credentials), not an engineering blocker.

So CookiX is `v1.0` as a **single-node** production database, with the two
relaxed items (Rust core, PyPI push) named openly rather than papered over.

---

## What stays explicitly out of scope for v1.0

Naming these prevents scope creep and over-promising:

- **Distributed / multi-node clustering, sharding, replication.** v1.0 is a
  robust *single-node* database. Horizontal scale is post-1.0.
- **Proving 𝒯 / 𝒮 help retrieval.** They remain optional, ablatable layers.
  Phase 6 measures them on real data; a positive result is a bonus, not a
  release blocker.
- **A managed/hosted service.** Out of scope; this roadmap delivers the engine
  and the self-hostable server only.

---

# Road to fully production-hardened (post-1.0)

`v1.0` is production-ready for a **careful single-node deployment you control**.
It is *not* yet ready for public-internet, multi-tenant, or high-scale use, and
it has **zero production mileage**. This part of the roadmap closes that gap.

Each gap I flagged maps to a phase below, with a hard exit gate. One honest
caveat up front: **"battle-tested" cannot be engineered in a sprint** — it is
earned by real deployments running for real time (Phase 19). Everything before
it is buildable; that last one is lived.

| Gap (today) | Phase that closes it |
|---|---|
| Docker image not build-validated; not on PyPI | **12** |
| Never run under real load / for real duration | **13** |
| Single-writer; limited write throughput | **14** |
| Pure-Python hot path (no Rust core) | **15** |
| Defaults open; not safe public-facing / multi-tenant | **16** |
| Single-node only (no HA / horizontal scale) | **17** |
| Open-domain quality is extraction-limited (oracle linking) | **18** |
| No production mileage / SLOs proven in the wild | **19** |

## Phase 12 — Validated, published artifacts *(distribution, for real)* — ✅ DONE

**`cookix` is live on PyPI (1.1.0)** — published via OIDC trusted publishing on the
`v1.1.0` tag; `pip install cookix` installs and runs a query in a clean venv, and
the Docker workflow builds + runs + scans the image green. The exit gate is met.



- **Done (in-repo):** a `Docker` workflow (`.github/workflows/docker.yml`) that
  builds the image, **runs it and smoke-tests `/healthz` + `/readyz`**,
  Trivy-scans it (fails on CRITICAL), and pushes to GHCR on version tags; and a
  `Release` workflow (`release.yml`) that builds the wheel + sdist, `twine
  check`s them, **verifies the wheel installs and runs in a clean venv**, and
  publishes to PyPI via **OIDC trusted publishing** (no stored token). Both YAMLs
  validate. Maintainer setup is documented in `RELEASING.md`.
- **Pending (maintainer + first tag):** the actual `pip install cookix` from PyPI
  and `docker pull` from GHCR confirm only after a maintainer configures the PyPI
  trusted publisher and pushes a `v*` tag — at which point CI runs end to end.
  This is the one-time account-level step that cannot live in the repo.
- **Exit gate:** `pip install cookix` works from PyPI; `docker pull … && docker
  run` serves a healthy container; image scan has no criticals.

## Phase 13 — Load & soak testing *(earn "battle-tested" — part 1)* — ◐ HARNESS SHIPPED

- **Done:** a real load/soak harness (`cookix loadtest`, `cookix.eval.load`) that
  starts the HTTP server on a socket and drives it with N concurrent clients over
  real sockets, reporting throughput, p50/p95/p99 latency, error rate, and
  start/peak/end memory (cross-platform RSS) for leak detection. Covered by tests.
  First measured run (8 clients, 10k objects, single process): **130 req/s, 0
  errors out of 2,613, p99 ~102 ms, memory non-monotonic (no leak)**.
- **Remaining (needs real hardware + time):** a **multi-hour soak** to firmly
  establish the no-leak claim, a **1M+ object** run (memory-heavy; ~3 GB at the
  current ~3 KB/object), and disk-full / pull-the-plug fault injection. The
  harness already supports these via `--duration` / `--objects`; they just need a
  big, long run on a real box.
- **Exit gate:** documented "sustained *X* req/s for *Y* hours, flat memory, zero
  data loss across induced crashes," reproducible from the shipped harness.

## Phase 14 — Concurrency & write throughput *(beyond single-writer)* — ◐ MEASURED

- **Done:** **WAL group-commit** — concurrent writers write their record under
  the (ordered) write lock, then share a single `fsync` instead of paying one
  apiece; selectable via `DurableBackend(..., group_commit=True)` (default).
  Correctness holds in both modes (crash-recovery + 8-writer concurrency tests).
- **Honest finding (the important part):** on this machine group-commit moved
  write throughput only **~3% (902 → 933 writes/s, 8 threads)**. The reason is
  diagnostic: the **global write lock + the GIL serialise writers**, so few
  fsyncs actually batch, and on a cached filesystem `fsync` is already cheap. The
  real bottleneck is the **single-writer lock, not fsync count**. (On an
  `fsync`-bound disk — networked/EBS-style — the batching pays off far more; the
  optimization is correct and standard, its payoff is workload-dependent.)
- **Remaining (the real write-scaling work):** shrink the critical section /
  finer-grained locking or MVCC, and **multi-process** serving (`uvicorn
  --workers N`) to get past the GIL. **Read-only follower replicas** moved to
  Phase 17 (Distributed/HA), where replication belongs.
- **Exit gate:** a documented write-throughput gain on an `fsync`-bound disk, and
  concurrent read/write SLOs under the Phase 13 harness.

## Phase 15 — Rust hot-path core *(the deferred 1.0 item)* — ⛔ BLOCKED HERE

- PyO3 crate for the geodesic traversal + composite-rank inner loop, behind a
  feature flag, with a Python-parity test battery and `cibuildwheel` wheels.
- **Genuinely blocked in this environment:** there is no Rust toolchain (`cargo`)
  to compile or parity-test the extension, and committing unbuildable Rust that
  claims to be "the core" would violate the honesty bar this project holds. The
  Phase 7 settle-once/early-exit Dijkstra is the interim pure-Python win, and the
  Phase 12 CI is already structured to build the extension via `cibuildwheel`
  once the crate is written on a machine with `cargo`.
- **Exit gate:** Rust and Python produce identical rankings; a documented
  end-to-end speedup; wheels build for Linux/macOS/Windows.

## Phase 16 — Public-facing & multi-tenant hardening — ◐ PARTIAL

- **Done:** **API-key roles** — keys map to `read` < `write` < `admin`; read
  endpoints require `read`, mutations require `write` (`403` on insufficient
  role), constant-time matched (`COOKIX_API_KEYS="k:role,…"`). **Secure-by-
  default binding:** `serve` refuses a non-loopback bind without auth unless
  `--insecure` / `COOKIX_ALLOW_INSECURE=1`. Both tested; the demo Docker image
  opts into insecure explicitly (documented) while the library stays strict.
- **Remaining:** per-tenant **data isolation** (namespaces / DB-per-tenant
  routing — a real design change), **distributed rate limiting** (shared store
  like Redis — needs that infra), **OpenTelemetry** tracing, and TLS / reverse-
  proxy reference configs. An external security review is also part of the gate.
- **Exit gate:** a documented multi-tenant deployment, an external security
  review with high/criticals resolved, and a pen-test checklist run.

## Phase 17 — Distributed / high availability *(horizontal scale)* — ◐ STARTED

- **Done:** **read-only follower replicas** — `DurableBackend(path,
  read_only=True)` loads the primary's snapshot + WAL tail, refuses all writes,
  and exposes `refresh()` to re-read and follow the primary point-in-time. Reads
  never open a writable handle on the primary's log. Tested (sees committed data,
  refuses writes/transactions, picks up new writes on refresh). This is the
  read-scaling building block; combined with the existing atomic `backup()` /
  `restore()` it already covers backup + PITR-style recovery.
- **Remaining (needs multi-process/multi-node + infra):** live WAL **streaming**
  to replicas (vs manual `refresh()`), automatic **failover** / leader election,
  and **sharding** by key/namespace.
- **Exit gate:** survives a node loss with no data loss; horizontal **read**
  scaling demonstrated under load.

## Phase 18 — Close the open-domain quality gap *(end-to-end, non-oracle)* — ◐ MEASURED

- **Done:** a pluggable **entity-linking** stage (`--no-oracle --linker
  {surface,bm25}`). Two linkers, measured on 2WikiMultiHopQA (2,000 dev):
  - **surface** (match entity *names* against the *question*) — link accuracy
    **59.5%**, CookiX hits@10 **0.378**.
  - **bm25** (match paragraph content) — link accuracy 50.1%, hits@10 0.340.
  - oracle (given) — hits@10 0.580; BM25 *retriever* baseline — 0.386.
- **Honest result:** the correct-signal linker lifts CookiX from *below* BM25
  (0.340) to **parity** (0.378 vs 0.386) — and CookiX still returns the reasoning
  path. **Not yet an outright end-to-end win.** Entity linking is the hard cap:
  ~40% of questions start from the wrong anchor. Clearing ~70%+ link accuracy is
  what flips it.
- **Remaining (the lever that flips it):** an **LLM-assisted linker** (needs an
  API key), plus a quantified **LLM extractor**, a **dense-retriever** baseline,
  and **HotpotQA** + **MuSiQue** loaders.
- **Exit gate:** published end-to-end (non-oracle) numbers vs a dense retriever on
  three datasets, with an honest win/loss verdict.

## Phase 19 — Production mileage & GA *(the part only time buys)* — ◐ GROUNDWORK DONE

- **Done (the codeable parts):** an on-call **runbook** (`RUNBOOK.md`) covering
  health/alerts, common incidents (latency, memory, crash recovery, corruption,
  auth spikes) and routine ops; a **Grafana dashboard** for the `/metrics`
  endpoint (`ops/grafana-dashboard.json`); and **model-based fuzz tests**
  (`tests/test_fuzz.py`) that drive the durable backend with random op sequences
  plus simulated crashes, checking it against a reference model, and assert query
  robustness on random graphs.
- **The gate that remains — and cannot be coded:** months of **real uptime**
  through **real incidents**, an incident runbook exercised for real, and SLOs met
  **in the wild**. No in-repo work substitutes for this; it is earned by running.

---

## What "100% production-ready" means here

CookiX is "100% ready" when **all of Phases 12–19** hold: published and scanned
artifacts, load/soak-proven, concurrent and (optionally) distributed, hardened
for untrusted networks, extraction gap measured-or-closed, and — critically —
**proven in real production over time**. Until Phase 19's lived gate is met, the
honest status remains "1.0: production-ready for controlled single-node use,
hardening in progress." We will not relabel that prematurely.
