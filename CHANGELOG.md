# Changelog

All notable changes to CookiX are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Release automation (Phase 12)** — a `Docker` CI workflow that builds, runs,
  smoke-tests (`/healthz` + `/readyz`), Trivy-scans, and (on tags) pushes the
  image to GHCR; and a `Release` workflow that builds + `twine check`s +
  clean-venv-verifies the wheel and publishes to PyPI via OIDC trusted publishing.
  Maintainer setup documented in `RELEASING.md`.

## [1.0.0] - 2026-05-29

First production release: a single-node topological-relational database that is
validated on external data, durable, secured, and distributed as stable
artifacts. See the "What 1.0 is — and is not" section of the README for the
honest scope. Highlights folded in from the development line below: external
2WikiMultiHopQA validation (typed traversal beats BM25 hits@10 0.58 vs 0.39),
the crash-safe `durable` backend, production server hardening, the typed client,
API + on-disk-format versioning, and an end-to-end production smoke test.

Out of scope for 1.0 (documented, not hidden): distributed/multi-node operation,
a proven retrieval benefit from the topological/sheaf layers (they stay optional
and ablatable), and the Rust hot-path core (a post-1.0 performance optimization —
the pure-Python engine already holds ~2 ms query latency to 50k objects).

### Added
- **Typed Python client** (`cookix.CookixClient`) — a dependency-free
  (stdlib-`urllib`) client over the stable HTTP wire API, with an injectable
  transport for testing. Plus `cookix.API_VERSION` (reported at `/api/info`), a
  documented SemVer/deprecation policy (`API_STABILITY.md`), and a **versioned,
  migration-guarded on-disk snapshot format** (`SNAPSHOT_FORMAT_VERSION`) that
  refuses a newer format and still reads the legacy layout.
- **Production server hardening** (`cookix.server.ServerConfig`, `COOKIX_*` env,
  `cookix serve --api-key/--rate-limit/--read-only`) — opt-in API-key auth
  (constant-time), per-client rate limiting, `k`/`max_hops`/body-size limits,
  read-only mode, structured JSON access logs, a dependency-free Prometheus
  `/metrics` endpoint, and `/healthz` + `/readyz` probes. Documented threat model
  in `SECURITY.md`; a hardened non-root `Dockerfile` ships in the repo.
- **Crash-safe `durable` storage backend** (`cookix.connect(path,
  backend="durable")`) — a write-ahead log (fsync-on-commit, CRC-framed
  torn-write tolerance), atomic snapshots (temp file + `os.replace`),
  all-or-nothing write-batch transactions (`with db.transaction(): …`),
  thread-safe single-writer locking, and backup/restore. Three backends now
  share the behavioural-parity contract (memory, durable, Kùzu).
- **Scaling benchmark** (`cookix eval --scale`, `cookix.eval.run_scale_benchmark`)
  — build cost, query latency and peak memory as the graph grows from 1k to 50k+
  objects. Query latency stays near-flat (~1.5→2.2 ms across a 50× size increase).
- **External multi-hop QA evaluation** (`cookix eval --dataset 2wiki --path …`,
  `cookix.eval.datasets`) — a real 2WikiMultiHopQA loader, an in-repo Okapi BM25
  baseline, a global knowledge graph built from gold evidence triples, and
  multi-hop answer/path metrics under the oracle entity-linking setting. On the
  first 2,000 dev examples, typed traversal beats BM25 hits@10 0.580 vs 0.386
  (+50% relative) with `path_match` 0.579. Ships with an offline fixture so the
  pipeline is exercised in CI without the dataset download.

### Changed
- **Geodesic search is now settle-once Dijkstra** with early-exit on a requested
  target: a node is never re-expanded once its minimum-cost path is fixed. Same
  results, far less work on large/dense graphs.
- **In-memory `save()` is now atomic** (temp file + `os.replace`), so a crash
  mid-write can no longer leave a corrupt snapshot.

### Fixed
- `Database` no longer discards a non-default backend when it happens to be empty
  (an empty backend is falsy via `__len__`; the constructor now tests `is None`).

## [0.2.0] - 2026-05-29

The evidence release: every research claim now has a reproducible study behind
it, the durable backend reaches in-memory parity, and the query path is measured.

### Added
- **HTTP server** (`cookix serve`, `cookix[server]` extra) — FastAPI app
  exposing `/api/info`, `/api/graph`, `/api/insert`, `/api/query`.
- **Reasoning-path explorer UI** — a browser graph view that highlights the
  typed path justifying each answer, with live ablation-mode switching.
- **3D sheaf explorer** (`/sheaf`, `/api/sheaf`, `/api/sheaf/trace`) — a Three.js
  view where each object's stalk is a unit vector on the sphere and each
  relation is a rotation; animates an anchor's meaning being carried along a
  reasoning path and shows the composition residual as the gap to the target.
- **Reproducible benchmark harness** (`cookix eval`) — synthetic relational
  corpus, fair vector-family (TF-IDF) and no-skill baselines, all ablations,
  deterministic from a single seed.
- **Extraction-quality study** (`cookix eval --extraction`) — gold-triple
  corpus with precision/recall/F1, relation-typing accuracy, and the measured
  per-edge `pʰ` multi-hop accuracy ceiling.
- **Learned sheaf restriction maps** (`cookix eval --sheaf`,
  `cookix.sheaf.set_learned_maps`) — per-relation orthogonal-Procrustes maps
  learned from edge evidence, with inverses tied to transposes; ~50–60%
  held-out composition-residual drop vs the random placeholder.
- **`TopoIndex`** — cosine-LSH approximate nearest-neighbour search over
  persistence signatures, with an exact fallback and a `recall_at_k` measure.
- **Performance benchmark** (`cookix eval --perf`) — per-ablation-mode
  end-to-end query latency (median/mean/p95) and throughput on the synthetic
  corpus; deterministic workload, honest about machine-dependent timings.

### Changed
- **Inverse relations are now virtual in single-hop lookup.** Querying a
  relation's inverse (e.g. `prevented_by`) resolves against incoming forward
  edges, so natural-language object-position queries like *"what prevents
  rain?"* return the subject without reverse edges being stored.
- **Kùzu backend hardened to in-memory parity** — a shared test battery pins
  identical dangling-target and incoming-edge semantics across both backends;
  edge targets are materialised lazily and traversable before insertion.
- **Ranking memoises per-query object lookups**, so adding the topology/sheaf
  layers no longer re-fetches the anchor once per candidate.

## [0.1.0] - 2026-05-29

First public release: a working Python-first reference implementation of the
NoVectDB paradigm.

### Added
- **Core data model** — Knowledge Object `K = (V, E, 𝒯, 𝒮)`, typed/directed/
  weighted edges, interpretable `QueryResult` with reasoning paths.
- **Controlled relation vocabulary** with algebraic properties (symmetry,
  transitivity, inverses) and user extensibility.
- **Storage backends** — in-memory (NetworkX, default, zero heavy deps) and an
  optional durable Kùzu backend, behind a common interface.
- **Query engine** implementing the NoVectDB pipeline (paper Algorithm 1):
  deterministic typed lookup, type-filtered geodesic BFS, and a composite
  distance over geodesic / topological / sheaf terms.
- **Ablation modes** (`graph`, `topo`, `sheaf`, `reasoning`) so each research
  layer's contribution can be measured against the graph-only baseline.
- **Topological layer** — persistent-homology signatures + TVS (optional,
  graceful degradation when `ripser`/`persim` are absent).
- **Sheaf layer** — composition residual with deterministic relation-typed
  restriction maps (experimental; learned maps are future work).
- **Relation extraction** — rule-based (dependency-free) and LLM-backed extractors.
- **MongoDB-style API** — `connect / insert / query / update / delete`,
  natural-language and structured queries, contradiction detection.
- **CLI** (`cookix info`, `cookix demo`), worked examples, and a pytest suite.

### Notes
- Paper benchmarks are not yet reproduced on public datasets; a reproducible
  evaluation harness with fair GraphRAG/KG baselines is the next priority.
