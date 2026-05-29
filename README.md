<p align="center">
  <img src="assets/logo.png" alt="CookiX Logo" width="180" />
</p>

<h1 align="center">CookiX</h1>

<p align="center">
  <strong>The open-source topological-relational memory database</strong><br>
  <em>Stop measuring distances. Start understanding adjacency.</em>
</p>

<p align="center">
  <a href="#installation">Installation</a> •
  <a href="#quickstart">Quickstart</a> •
  <a href="#how-it-works">How it works</a> •
  <a href="#the-honest-status">Honest status</a> •
  <a href="#benchmarks">Benchmarks</a> •
  <a href="#roadmap">Roadmap</a> •
  <a href="#contributing">Contributing</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License" />
  <img src="https://img.shields.io/badge/python-3.10%2B-green.svg" alt="Python" />
  <img src="https://img.shields.io/badge/paradigm-NoVectDB-blueviolet.svg" alt="NoVectDB" />
  <img src="https://img.shields.io/badge/built%20in-Morocco%20%F0%9F%87%B2%F0%9F%87%A6-red.svg" alt="Built in Morocco" />
</p>

---

## What is CookiX?

**CookiX** is the reference implementation of the **NoVectDB** (*Not Only Vector Database*) paradigm: the idea that knowledge has **shape**, **direction**, and **composition**, and our databases should too.

Vector databases embed everything into flat ℝⁿ and retrieve by cosine distance. That works for fuzzy lookups but breaks down when you need:

- **Relational reasoning** — "What *prevents* rain from reaching the coat?" (a typed, directed edge — not proximity)
- **Multi-hop queries** — "Is pipe A compatible with fitting B *via* adapter C?" (path traversal)
- **Contradiction detection** — "Do specs X and Y *conflict*?" (directed semantics)
- **Interpretable retrieval** — "*Why* was this result returned?" (a reasoning path, not a float)

CookiX stores knowledge as **Knowledge Objects** in a typed, directed graph and retrieves by traversing relations — returning the *path* that justifies each answer.

> **MongoDB is to NoSQL** what **CookiX is to NoVectDB.**

---

## Installation

```bash
pip install cookix                 # core (graph traversal, zero heavy deps)
pip install "cookix[topology]"     # + persistent-homology re-ranking
pip install "cookix[kuzu]"         # + durable embedded graph storage
pip install "cookix[llm]"          # + LLM relation extraction
pip install "cookix[server]"       # + HTTP server & reasoning-path explorer UI
pip install "cookix[all]"          # everything
```

Requires Python 3.10+.

---

## Quickstart

```python
import cookix

db = cookix.connect("demo")

db.insert({"_id": "umbrella", "content": "blocks rain", "edges": [("prevents", "rain")]})
db.insert({"_id": "rain",     "content": "falling water", "edges": [("causes", "wet_coat")]})
db.insert({"_id": "wet_coat", "content": "a soaked coat"})

# Multi-hop reasoning — returns the path, not a distance
for r in db.query(anchor="umbrella", target="wet_coat", mode="reasoning"):
    print(r.explain())
# umbrella --[prevents]--> rain --[causes]--> wet_coat  (score=..., hops=2)
```

Try the built-in demos:

```bash
cookix demo umbrella
cookix demo pipe
cookix info          # shows which optional layers are active
```

---

## The reasoning-path explorer

A vector database can only show you a blob and a distance. CookiX can show you **why** — the typed path that justifies each answer, as an interactive graph.

<p align="center">
  <img src="assets/demo-reasoning.png" alt="CookiX reasoning-path explorer — the query 'what prevents rain?' lights up the umbrella —[prevents]→ rain path" width="800" />
</p>

```bash
pip install "cookix[server]"
cookix serve                 # opens an HTTP API + UI at http://127.0.0.1:8000
cookix serve --demo pipe     # start from the pipe-compatibility demo
```

Open the browser UI, type a natural-language query (e.g. *"what prevents rain?"*), and the matching reasoning path lights up on the graph. Switch the **ablation mode** in the UI to see exactly what the topology and sheaf layers add on top of pure graph traversal.

### 3D sheaf explorer

The UI also includes a **3D sheaf explorer** (linked from the top bar, or `/sheaf`). At `dim=3`, every object's sheaf stalk is a unit vector on the sphere and every relation is a rotation of it. Pick an anchor and a target, and watch the anchor's "meaning" get *carried* through each relation on the reasoning path — the gap between where it lands and the target's stalk **is** the composition residual. A coherent chain lands near the target; an incoherent one drifts away.

<p align="center">
  <img src="assets/demo-sheaf.gif" alt="3D sheaf explorer — the anchor stalk is carried along prevents→causes; the dashed line is the composition residual to the target stalk" width="420" />
  &nbsp;&nbsp;
  <img src="assets/demo-sheaf.png" alt="Static view of the carry: green anchor stalk, orange carried meaning, blue target stalk, dashed residual gap" width="420" />
</p>

> Honest note: the restriction maps are currently random placeholders, so residuals are large by design (the trace above lands far from the target). The explorer is built to make that visible — when learned maps arrive, you'll *see* meaning start to compose.

The server also exposes the database over HTTP for non-Python clients:

```bash
curl -X POST http://127.0.0.1:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "what prevents rain?", "mode": "reasoning"}'
```

---

## How it works

Each piece of knowledge is a **Knowledge Object** `K = (V, E, 𝒯, 𝒮)`:

| Component | What it is | Status |
|---|---|---|
| **V** | Optional embedding vector (legacy compatibility) | stable |
| **E** | Typed, directed, weighted edges (`causes`, `prevents`, `is_a`, …) | **stable — the proven core** |
| **𝒯** | Topological signature from persistent homology | experimental |
| **𝒮** | Sheaf section — how meaning transforms across a relation | experimental |

Retrieval runs a multi-stage pipeline (paper Algorithm 1):

1. **Deterministic lookup** — exact typed-edge match (precision 1.0 for single-hop).
2. **Geodesic BFS** — type-filtered, weighted shortest-path traversal for multi-hop.
3. **Topological re-ranking** — by similarity of persistent-homology signatures *(optional)*.
4. **Sheaf composition** — by how consistently meaning composes along each path *(optional)*.

The composite distance:

```
d(Kₐ, Kᵦ) = α · geodesic(a,b) + β · (1 − TVS(𝒯ₐ, 𝒯ᵦ)) + γ · ‖sheaf_residual‖
```

Every layer is **ablatable** via `mode=`:

```python
db.query(anchor="a", target="b", mode="graph")     # traversal only (baseline)
db.query(anchor="a", target="b", mode="topo")      # + topology
db.query(anchor="a", target="b", mode="sheaf")     # + sheaf
db.query(anchor="a", target="b", mode="reasoning") # full pipeline
```

### Durable storage and topological indexing

The engine depends only on a small `StorageBackend` contract, so the store is
swappable. Two backends ship with **behavioural parity** (a shared test battery
runs against both): the default in-memory NetworkX store, and a durable embedded
**Kùzu** property-graph store.

```python
db = cookix.connect("graph.kuzu", backend="kuzu")   # durable, on-disk
```

For shape-based retrieval at scale, `TopoIndex` provides approximate
nearest-neighbour search over persistence signatures via cosine LSH — sublinear
TVS lookup, deterministic, with an exact fallback and a built-in recall measure.

---

## The honest status

CookiX is built to **test** the NoVectDB paradigm, not to oversell it. Being straight about what's proven and what isn't:

- ✅ **The typed-graph core works and is well-founded.** Typed relational retrieval beating flat vector similarity on relational/multi-hop/contradiction queries is established across the knowledge-graph and GraphRAG literature.
- 🧪 **Persistent homology (𝒯) and sheaf composition (𝒮) are open research bets.** They are implemented as *optional, ablatable* layers precisely so their contribution can be **measured** against the graph-only baseline — not assumed. The sheaf restriction maps are no longer only a placeholder: they can now be **learned** from edge evidence (`cookix.sheaf.set_learned_maps`), and the learned maps cut held-out composition residual substantially — see [Benchmarks](#benchmarks).
- 📊 **The benchmark harness now ships in-repo and is reproducible from a single seed** (`cookix eval`). It runs on a synthetic relational corpus against fair baselines and every ablation; see [Benchmarks](#benchmarks) below. Porting it to external multi-hop datasets (HotpotQA, 2WikiMultiHopQA, MuSiQue) is the next step.

If the exotic layers don't earn their keep in honest ablations, we'll say so. That's the point.

---

## Benchmarks

CookiX ships a **deterministic, reproducible** evaluation suite. One seed fixes the
corpus, the baselines, and every reported number:

```bash
cookix eval                       # Markdown table (defaults: seed=0, 40 worlds, k=5)
cookix eval --worlds 80 --json    # machine-readable
```

The corpus is a **steelman, not a strawman**: every entity's text describes the
entity *itself* (never its relations), and entities in a world share a topical
adjective — so a content/vector retriever genuinely retrieves the right
*neighbourhood*. The relational answer lives **only** in the typed edges, so
recovering it requires traversal, not proximity. All retrievers see the same
natural-language query and are scored identically.

Baselines: a **random** no-skill floor, and **`lexical-tfidf`** — TF-IDF cosine
over content, standing in for the vector-similarity family (a dense embedder
plugs into the same interface and behaves the same way with respect to
*relations*: it retrieves by topical proximity, not traversal).

`seed=0`, 40 worlds (240 documents, 160 queries spanning single-hop forward,
single-hop inverse, multi-hop, and contradiction), `k=5`:

| retriever | hits@1 | hits@5 | precision@5 | recall@5 | mrr | path_acc |
|---|---|---|---|---|---|---|
| random | 0.006 | 0.019 | 0.004 | 0.019 | 0.010 | 0.000 |
| lexical-tfidf | 0.250 | 0.750 | 0.150 | 0.750 | 0.375 | 0.000 |
| cookix-graph | 1.000 | 1.000 | 0.200 | 1.000 | 1.000 | 1.000 |
| cookix-topo | 1.000 | 1.000 | 0.200 | 1.000 | 1.000 | 1.000 |
| cookix-sheaf | 1.000 | 1.000 | 0.200 | 1.000 | 1.000 | 1.000 |
| cookix-reasoning | 1.000 | 1.000 | 0.200 | 1.000 | 1.000 | 1.000 |

Reading the numbers honestly:

- **The lexical baseline is real, not a punching bag.** It reaches `recall@5 = 0.75`
  because the shared adjective lets it pull the correct world's neighbourhood. But
  its `hits@1` is only `0.25` — it cannot pick the relationally-correct entity out
  of that neighbourhood, and its `path_acc` is **0** because content similarity
  structurally cannot produce a reasoning path.
- **CookiX recovers the exact relational target and the gold path** on this corpus,
  which is what the typed-graph core is built to do.
- **`topo`/`sheaf`/`reasoning` match `graph` here** — on a corpus this clean the
  graph core already saturates, so the exotic layers have no headroom to
  demonstrate. Their value has to be shown on harder, noisier data; that's exactly
  why they remain *ablatable*. We are not claiming 𝒯/𝒮 help yet.

### External validation: 2WikiMultiHopQA

The synthetic numbers prove the claim on a corpus CookiX designed. The harder
question — does it hold on data CookiX *didn't* design? — is now answered on
**2WikiMultiHopQA**, a standard multi-hop QA benchmark. It is uniquely suited
because each example ships **gold `(subject, relation, object)` evidence
triples**, which lets us measure the *relational engine* in isolation from the
known extraction bottleneck.

```bash
cookix eval --dataset 2wiki --path dev.json --k 10   # full reproducible run
```

We build one **global knowledge graph** from every example's gold triples (so
traversal faces real distractor edges from thousands of other questions), then
compare typed multi-hop traversal against **Okapi BM25** — the standard strong
lexical passage retriever — over the same paragraphs. Both are scored on whether
the gold **answer entity** lands in the top-`k`. Measured on the first **2,000
dev examples** (1,802 evaluable; `k=10`):

| retriever | hits@10 | MRR | path_match |
|---|---|---|---|
| BM25 (strong lexical) | 0.386 | 0.239 | n/a |
| **cookix-graph** | **0.580** | **0.282** | **0.579** |
| cookix-reasoning | 0.580 | 0.283 | 0.579 |

- **+50% relative hits@10 over BM25** on real multi-hop questions: typed
  traversal reaches answers that are not lexically adjacent to the question,
  which is exactly where passage retrieval breaks down.
- **`path_match = 0.58`** — CookiX recovers the *gold relation chain* on most
  answered questions. BM25 scores `n/a` here by construction: it returns
  passages, not reasoning paths.
- `reasoning` ties `graph` on answer recall (the re-ranking layers reorder
  candidates but don't change which answers are reachable) — reported honestly,
  not hidden.

**Honest scope, stated plainly:** this is the **oracle entity-linking** setting
standard in KG-QA — CookiX is given the question's head entity as the anchor, so
this measures the *reasoning engine* (the paper's Algorithm 1), not open-domain
extraction + linking. End-to-end open-domain QA additionally depends on triple
extraction from free text, measured separately below and currently the limiting
factor. A real win on the engine is real; we just don't dress it up as an
end-to-end number it isn't.

### Extraction quality is the multi-hop ceiling

The retrieval numbers above assume the graph is *already correct*. In practice the
graph is built by an extractor, and **extraction error is the true ceiling on
multi-hop reasoning**: if each edge is recovered with probability `p`, an `h`-hop
answer is correct with probability about `pʰ` — error compounds with depth. We
measure `p` directly against a hand-annotated gold corpus:

```bash
cookix eval --extraction           # deterministic rule-based study (offline)
cookix eval --extraction --llm     # also score the LLM extractor (needs an API key)
```

Rule-based extractor on 16 gold-annotated sentences (18 gold triples):

| extractor | precision | recall | f1 | relation_acc | gold | pred | exact |
|---|---|---|---|---|---|---|---|
| rule-based | 0.615 | 0.444 | 0.516 | 1.000 | 18 | 13 | 8 |

The decomposition is the interesting part: **relation typing is perfectly reliable**
(`relation_acc = 1.0` — whenever the extractor spans the right entities it labels the
relation correctly), but **free-text coverage is the bottleneck** (`recall = 0.44`).
The misses are exactly the realistic cases: out-of-vocabulary synonyms ("leads to",
"ward off"), two-relation sentences (a keyword splitter emits only the first), and
preposition boundaries. Projecting that per-edge recall through the compounding model:

| extractor | 1-hop | 2-hop | 3-hop | 4-hop |
|---|---|---|---|---|
| rule-based | 0.444 | 0.198 | 0.088 | 0.039 |

A 4-hop chain survives only ~4% of the time. That is **why extraction is a
first-class, swappable component** and why the `LLMExtractor` exists — and it sets up
Phase 2's open question: how much of that ceiling does an LLM extractor actually buy
back? (The LLM run needs an API key, so it is kept out of the deterministic suite.)

### Learned sheaf restriction maps

The sheaf layer scores a chain by its **composition residual**
`||S_π(x_a) − x_b||`: low residual = a coherent reasoning path. The maps `F_r` shipped
by default are random orthogonal placeholders, so that residual is uninformative. CookiX
can now **learn** them — the closed-form orthogonal Procrustes map per relation that best
transports source stalks onto targets, with inverses tied to transposes:

```bash
cookix eval --sheaf      # residual ablation: placeholder vs learned
```

On approximately sheaf-consistent synthetic data (per-component noise 0.1, `dim=16`),
evaluated on **held-out** edges and 2-hop paths:

| maps | 1-hop residual | 2-hop residual |
|---|---|---|
| placeholder (random) | 1.399 | 1.416 |
| learned (Procrustes) | 0.534 | 0.731 |
| **residual drop** | **62%** | **48%** |

The placeholder sits at ~√2 ≈ 1.41 — the expected distance between two unrelated unit
vectors, i.e. no information. Learning the maps cuts residual by roughly half on data the
maps never saw; the remaining residual tracks the injected noise floor, not memorisation.

Honest scope: this demonstrates that **when relations act near-linearly on semantic
frames, the maps are recoverable** — the linear, closed-form rung of "learned sheaves".
Whether real LLM-derived stalks satisfy that, and whether gradient-based neural sheaf
diffusion (jointly learning stalks and maps) does better, remains the open question. The
layer stays ablatable so the answer is measured, not assumed.

### Query performance

Correctness is necessary but not sufficient — the engine also has to be fast
enough to use. The same synthetic corpus doubles as a throughput benchmark:

```bash
cookix eval --perf       # time the end-to-end query path per ablation mode
```

End-to-end (natural language in, ranked reasoning paths out) over 240 documents,
160 queries × 3 repeats, single-threaded pure Python:

| mode | median latency | p95 | throughput |
|---|---|---|---|
| graph-only | 0.06 ms | 0.13 ms | ~13,000 q/s |
| + topology | 0.06 ms | 0.16 ms | ~13,000 q/s |
| + sheaf | 0.07 ms | 0.36 ms | ~7,000 q/s |
| full (all layers) | 0.07 ms | 0.38 ms | ~6,500 q/s |

Numbers are from one machine and move with hardware and load; only the *relative*
cost of each layer is portable, and the workload is fixed by `seed`. The graph
baseline is sub-0.1 ms median; the sheaf term roughly halves throughput, which is
the price of composition re-ranking and is itself a measured trade-off rather than
an assumption. Ranking memoises per-query object lookups so adding layers does not
re-fetch the anchor for every candidate.

Ranking memoises per-query object lookups, and the geodesic search is a
**settle-once Dijkstra** (a node is never re-expanded once its minimum-cost path
is fixed) with **early-exit** when a specific target is requested.

### Scaling

The micro-benchmark above is on 240 objects. How does it hold as the graph grows?
A structural stress workload — a random typed graph, out-degree 4, anchor-only
4-hop traversals — measured with `cookix eval --scale`:

| objects | ingest | peak mem | median query | p95 | throughput |
|---|---|---|---|---|---|
| 1,000 | 0.08 s | 3 MB | 1.5 ms | 2.8 ms | ~560 q/s |
| 10,000 | 0.9 s | 30 MB | 2.0 ms | 3.1 ms | ~460 q/s |
| 50,000 | 6.4 s | 155 MB | 2.2 ms | 6.1 ms | ~340 q/s |

The result that matters: **query latency stays near-flat (~1.5→2.2 ms) across a
50× increase in graph size.** Traversal cost is bounded by the *local reachable
frontier* (degree × hops), not the total object count — which is the whole point
of settle-once Dijkstra over a typed graph. Memory is ~3 KB/object and ingest is
roughly linear.

Honest scope: this is single-threaded **pure Python** on one machine. The planned
**Rust/PyO3 hot-path core** (Phase 7 of the [roadmap](ROADMAP.md)) targets exactly
this geodesic inner loop; it is not yet built (it needs a Rust toolchain), so the
algorithmic win shipped here is the settle-once/early-exit Dijkstra, in Python.

---

## Use cases

- **RAG pipelines** — relational retrieval with reasoning paths instead of opaque chunks
- **Engineering knowledge** — part compatibility, spec conflicts, standards conformance
- **Medical ontologies** — drug interactions, contraindication chains
- **Legal reasoning** — precedent chains, statute conflict detection

---

## Roadmap

- [x] **Phase 0** — Typed-graph core: Knowledge Objects, deterministic lookup, geodesic traversal, interpretable paths
- [x] **Phase 0** — Optional topology + sheaf layers behind ablation switches
- [x] **Phase 0** — HTTP server (`cookix serve`) + browser reasoning-path explorer UI
- [x] **Phase 1** — Reproducible benchmark harness (`cookix eval`): synthetic relational corpus, fair vector-family + no-skill baselines, all ablations, deterministic from one seed. *Next: port to external multi-hop datasets.*
- [x] **Phase 2** — Extraction-quality study (`cookix eval --extraction`): gold-triple corpus, precision/recall/F1 + relation-typing accuracy, and the measured per-edge `pʰ` multi-hop ceiling. *Next: quantify how much an LLM extractor buys back.*
- [x] **Phase 3** — Learned sheaf restriction maps (`cookix eval --sheaf`): orthogonal-Procrustes maps learned per relation, ~50–60% held-out residual drop vs the random placeholder. *Next: neural sheaf diffusion (jointly learn stalks + maps).*
- [x] **Phase 4** — Durable Kùzu backend hardened to in-memory parity (shared test battery: dangling-target and incoming-edge semantics) + `TopoIndex` (cosine-LSH ANN over persistence signatures, with exact fallback + recall measure).
- [x] **Phase 5** — Reproducible performance benchmark (`cookix eval --perf`): per-mode end-to-end latency/throughput on the synthetic corpus, plus per-query lookup memoisation in the ranking pass. *Next: the Rust hot-path core targeting this inner loop.*
**The road to a production `v1.0`** (full plan with exit gates in [ROADMAP.md](ROADMAP.md)):

- [x] **Phase 6** — *Credibility gate.* External validation on **2WikiMultiHopQA** (`cookix eval --dataset 2wiki`): gold-triple knowledge graph vs Okapi BM25 over the same paragraphs. **hits@10 0.58 vs 0.39** (+50% rel.) and `path_match` 0.58 on 2,000 dev examples, under oracle entity-linking. *Next: HotpotQA/MuSiQue loaders + a dense-retriever baseline.*
- [~] **Phase 7** — *Performance gate (partial).* Scaling benchmark (`cookix eval --scale`) + settle-once/early-exit Dijkstra: **query latency near-flat ~2 ms from 1k→50k objects**, ~3 KB/object. Rust/PyO3 hot-path core still **deferred** (needs a Rust toolchain not present in this environment).
- [ ] **Phase 8** — *Data-safety gate.* Crash-safe persistence (WAL + atomic snapshot), transactions, concurrent read/write, backup/restore — proven by crash-recovery and concurrency stress tests.
- [ ] **Phase 9** — *Deployability gate.* Auth + rate limiting + input/resource limits, structured logging + metrics + health checks, hardened Docker image, security review.
- [ ] **Phase 10** — *Distribution gate.* Frozen versioned API (OpenAPI) + SemVer policy, typed Python client, cross-platform wheels on PyPI, on-disk migration tooling.
- [ ] **Phase 11 / v1.0** — Full docs, perf-regression CI, end-to-end smoke test. Released only when gates 6–10 all hold.

Explicitly **out of scope for v1.0**: distributed clustering/sharding, a hosted service, and any claim that the 𝒯/𝒮 layers help retrieval before Phase 6 measures it.

---

## Contributing

CookiX is open source and welcomes contributors.

```bash
git clone https://github.com/cookix-db/cookix.git
cd cookix
pip install -e ".[dev,all]"
pytest
```

Areas we need help with: evaluation/benchmarking, topological data analysis, LLM relation extraction, storage performance, and docs.

---

## Citation

```bibtex
@article{hafdi2026novectdb,
  title   = {NoVectDB: A Topological-Relational Paradigm for Post-Vector Data Management},
  author  = {Hafdi, Ahmed},
  year    = {2026},
  note    = {CookiX Project}
}
```

## License

[Apache License 2.0](LICENSE).

---

<p align="center">
  <strong>Built in Morocco 🇲🇦 — Built for the world 🌍</strong><br>
  <em>Knowledge has shape, direction, and composition. Our databases should too.</em>
</p>
