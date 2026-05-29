# Changelog

All notable changes to CookiX are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
