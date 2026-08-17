# Corrections to the NoVectDB preprint (February 2026)

The February 2026 preprint (`docs/paper.pdf`) contains claims this repository does not
support. This file is the itemised correction record. The corrected paper source is
[`novectdb.tex`](novectdb.tex).

Corrections are listed rather than silently applied because the preprint was
circulated. Every one of them moves a claim **down**.

## Withdrawn in full

| Preprint claim | Reality in this repository |
|---|---|
| "open-source reference engine (**Rust core**, Python bindings)"; ManifoldStore is a "memory-mapped adjacency list (inspired by sled/redb)" with "type-indexed edge lookups in O(1) amortised time"; Figure 1 labelled "Python + Rust" | No Rust exists. Pure Python over NetworkX, with pickle snapshots and a write-ahead log. A Rust hot-path core is unstarted future work. |
| §9.2 Table 2 — precision@5: Chroma 0.437, Pinecone 0.457, GraphRAG 0.583, CookiX 0.830; "**2.4× average precision improvement**" over vector-only baselines, 2.6× on contradiction detection | No dense-vector, Chroma, Pinecone or GraphRAG baseline exists anywhere in the evaluation suite. The suite contains a random floor, TF-IDF cosine, and Okapi BM25. **These numbers are not reproducible from this repository.** |
| §9.1 corpus — "500 relational queries over a technical document corpus (industrial pipe specifications, medical ontologies, legal case chains)" | No such corpus exists. Evaluation uses a seeded synthetic generator and 2WikiMultiHopQA. |
| §9.3 Table 3 — median/p99 latency at 100K objects vs Chroma and Pinecone | Not reproducible: no competitor system is installed or measured, and the largest graph benchmarked is 5×10⁴ objects. |
| §11 Theorem 11.3 (Completeness) — the knowledge category "has all finite limits and colimits (which holds when G is finite and connected)", so every finite-diagram query has a well-defined answer | False as stated: a free category on a finite graph generally has neither. The section carried no operational content and is removed. |
| Theorem 6.2 — NoVectDB "**strictly dominates**" vector-only retrieval for relational queries; abstract: "**prove** that retrieval … provides strictly stronger guarantees" | Restated as a *conditional* proposition. Traversal accuracy is bounded by `ℓ · pʰ` (linking accuracy × per-edge extraction accuracy ^ hops). At measured values (p ≈ 0.444, ℓ ≈ 0.595) the condition **fails** — two-hop survival ≈ 0.117 — which matches the observed end-to-end parity with BM25. A conditional inequality whose condition our own measurements violate is not a dominance result. |

## Scope-corrected

| Preprint claim | Correction |
|---|---|
| Proposition 2.4 — for **any** embedding φ and any non-symmetric, non-transitive relation, a semantic gap exists | Holds for **metric-ranked** retrieval only. Asymmetric scoring functions over embeddings — TransE, ComplEx, RotatE — are not metrics and are unaffected. Those works are now cited; the preprint cited none of them. The real gap is against *cosine similarity over text embeddings*, which is what production RAG deploys. |
| §2.1 — concentration of measure as a "fundamental limitation rooted in the geometry of flat Euclidean space", inducing precision collapse | Demoted to an asymptotic caution about **isotropic** data. Learned text embeddings are strongly anisotropic and concentrate near low-dimensional manifolds, which is why cosine retrieval stays discriminative at n = 768–3072. The paper's argument no longer rests on this. |
| §12 — "the current prototype handles 10⁵ Knowledge Objects" | 5×10⁴ measured. |

## Corrected implementation descriptions

| Preprint | Actual |
|---|---|
| TopoIndex "adapts the HNSW algorithm to operate on persistence diagram distances" | Cosine LSH over persistence signatures, with exact fallback and a recall measure. |
| Ingestor "uses a small LLM (e.g. a 3B-parameter instruction model) for relation extraction" | Rule-based keyword extractor (default) or an API-backed LLM extractor. No local model. |
| Topological signatures via "Landmark Vietoris–Rips complex for O(l³) cost" | Full neighbourhood shortest-path distance matrix passed to ripser. No landmark/witness construction. |

## Status changes for the two exploratory layers

- **Topological signatures (𝒯):** the preprint presented this as a pillar of the
  paradigm. Reported now as measured — it changes **no** retrieval metric outside noise
  on any benchmark in the suite.

- **Sheaf composition (𝒮):** the preprint deferred learning the restriction maps to
  future work and implied prospective benefit. A later in-repo study reported a 48–62%
  residual drop from learned maps, but that study fitted maps on synthetic data
  *generated to be sheaf-consistent* — it confirms Procrustes recovers a linear map when
  a linear map made the data, and says nothing about retrieval signal.

  Replaced by a discriminative test (`cookix eval --sheaf-probe`) with an
  identity-map control and a pre-registered decision rule. **Result: negative.** On
  1,938 held-out 2WikiMultiHopQA chains, learned maps reach pooled AUC 0.552 against an
  identity control's 0.530 — a gap of 0.022 against a 0.023 noise floor — and the gap
  is below the noise floor in **9 of 9** configurations (dim ∈ {8,16,32} × 3 seeds).

  Diagnosed mechanism: on *detours* (genuine alternative paths between the same
  endpoints) the residual is at chance, 0.481. Retrieval candidates are all real paths,
  so this is precisely the discrimination retrieval re-ranking needs. It follows from the
  definition — the residual reads only the source stalk, the relation sequence, and the
  target stalk, never the intermediate entities.

  Untested and therefore not claimed either way: neural sentence embeddings as stalks,
  and jointly-learned (neural sheaf diffusion) maps rather than closed-form linear ones.

## New disclosure

The corrected paper states explicitly, in its own section, that **no dense-retrieval
baseline has ever been run** against CookiX. Running one is the most important
outstanding experiment. The preprint instead reported comparisons that did not exist.

## What survives unchanged

Not everything was wrong, and the corrected paper keeps it:

- The Knowledge Object model, the graph substrate, and the composite distance.
- The retrieval pipeline and its complexity, which match the implementation.
- The core empirical result: under oracle entity linking on 2WikiMultiHopQA,
  hits@10 **0.580 vs BM25's 0.386** (+50% relative) with `path_match` 0.579. This is a
  real result in a recognised setting.
- Durability, security and operational engineering, which were never overclaimed.
- The central insight, in its corrected scope: a symmetric distance cannot represent a
  directed relation, and returning the justifying path is something distance-ranked
  retrieval structurally cannot do.

## Recommended handling

1. Compile `novectdb.tex` and publish it as the current version.
2. Mark `docs/paper.pdf` superseded rather than deleting it — the preprint was
   circulated, so the correction trail should stay visible.
3. If the preprint was posted to a preprint server or submitted anywhere, replace it
   there with a new version and cite this file in the revision note. A silent swap is
   not adequate for withdrawn benchmark tables.
