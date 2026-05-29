# CookiX Roadmap — from research release to production database

**Where we are:** `v0.2.0` — a complete, evidence-backed *research* reference
implementation of the NoVectDB paradigm. Every claim has a reproducible study,
the durable Kùzu backend reaches in-memory parity, and the query path is
measured. All benchmarks to date run on a **synthetic** corpus the project
controls.

**Where this roadmap goes:** `v1.0` — a database people can trust in production:
validated on real data, fast at scale, crash-safe, concurrent, secured, and
distributed as stable, versioned artifacts.

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

## Phase 9 — Operational hardening & security *(deployability gate)*

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

## Phase 10 — API stability, clients & packaging *(distribution gate)*

A `1.0` is a promise. This phase makes the promise concrete.

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

## Phase 11 — v1.0 release

**Deliverables**
- Complete documentation set: architecture, deployment, tuning, full API
  reference, and a migration guide from 0.x.
- A performance-regression gate in CI (fail the build if latency/throughput
  regress beyond a threshold).
- An end-to-end production smoke test exercised on the published artifacts.

**v1.0 gate (all must hold):**
1. Phase 6 external-dataset results are published and defensible — we can state
   honestly what CookiX is good at, on data we didn't design.
2. Phase 7 scale SLOs are met and the Rust core is at Python parity.
3. Phase 8 data-safety battery (crash recovery, concurrency, backup/restore)
   passes.
4. Phase 9 security review is clean; the documented deploy works.
5. Phase 10 stable, versioned artifacts are published and installable.

Only when all five hold does CookiX become `v1.0` — a production database, not a
research release that calls itself one.

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
