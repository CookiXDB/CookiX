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
- 📊 **Benchmarks are being reproduced.** The numbers in the paper come from a curated synthetic corpus. A public, reproducible evaluation harness (HotpotQA, 2WikiMultiHopQA, MuSiQue + fair GraphRAG/KG baselines + ablations) is the current priority — see the roadmap.

If the exotic layers don't earn their keep in honest ablations, we'll say so. That's the point.

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
- [ ] **Phase 1** — Public reproducible benchmark harness (vector / GraphRAG / KG baselines + ablations)
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
