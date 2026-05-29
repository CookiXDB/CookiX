# Changelog

All notable changes to CookiX are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **HTTP server** (`cookix serve`, `cookix[server]` extra) — FastAPI app
  exposing `/api/info`, `/api/graph`, `/api/insert`, `/api/query`.
- **Reasoning-path explorer UI** — a browser graph view that highlights the
  typed path justifying each answer, with live ablation-mode switching.

### Changed
- **Inverse relations are now virtual in single-hop lookup.** Querying a
  relation's inverse (e.g. `prevented_by`) resolves against incoming forward
  edges, so natural-language object-position queries like *"what prevents
  rain?"* return the subject without reverse edges being stored.

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
