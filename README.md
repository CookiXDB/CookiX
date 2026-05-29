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

---

## The honest status

CookiX is built to **test** the NoVectDB paradigm, not to oversell it. Being straight about what's proven and what isn't:

- ✅ **The typed-graph core works and is well-founded.** Typed relational retrieval beating flat vector similarity on relational/multi-hop/contradiction queries is established across the knowledge-graph and GraphRAG literature.
- 🧪 **Persistent homology (𝒯) and sheaf composition (𝒮) are open research bets.** They are implemented as *optional, ablatable* layers precisely so their contribution can be **measured** against the graph-only baseline — not assumed. The sheaf restriction maps are currently a deterministic placeholder; *learning* them is future work.
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
  why they remain *ablatable* and why honest external benchmarks are the next
  roadmap item. We are not claiming 𝒯/𝒮 help yet.

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
- [ ] **Phase 2** — LLM relation extraction quality study (extraction error is the multi-hop ceiling)
- [ ] **Phase 3** — Learned sheaf restriction maps (neural sheaf diffusion)
- [ ] **Phase 4** — Durable Kùzu backend hardening + TopoIndex (ANN over persistence diagrams)
- [ ] **Phase 5** — Rust hot-path core via PyO3; optional server mode
- [ ] **v1.0** — Production release

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
