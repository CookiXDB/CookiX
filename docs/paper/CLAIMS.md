# Claim discipline (internal note)

What this project may and may not claim, and the measurement behind each. Internal
working note, not a publication. Its purpose is to stop overclaims being reintroduced —
an earlier draft of the paper contained several, and every one of them was the kind that
sounds reasonable while you are writing it.

## The rule

**No number appears in the paper that a command in this repository cannot produce.**
Each figure in the paper names its command. If a comparison has not been run, the paper
says so in its own words rather than leaving a gap a reader will fill in generously.

## Claims we can make

| Claim | Evidence |
|---|---|
| Typed traversal beats strong lexical retrieval on multi-hop questions **under oracle entity linking** | 2Wiki, hits@10 0.580 vs BM25 0.386, `path_match` 0.579 — `cookix eval --dataset 2wiki` |
| Retrieval returns the justifying path; passage retrieval structurally cannot | `path_acc` 1.000 vs 0.000 (synthetic); `path_match` 0.579 vs n/a (2Wiki) |
| Relation *typing* is reliable; free-text *coverage* is not | extraction relation accuracy 1.000, recall 0.444 — `cookix eval --extraction` |
| Query latency is near-flat in graph size | 1.5 → 2.2 ms across 1k → 50k objects — `cookix eval --scale` |
| The durable backend survives crashes, torn writes and concurrent writers | crash-recovery, rollback, concurrency-stress and fuzz test batteries |
| A symmetric distance cannot represent an asymmetric relation | proved, for *metric-ranked* retrieval (see scope limits below) |

## Claims we cannot make

| Tempting claim | Why not |
|---|---|
| "Beats vector databases" | **No dense retriever has ever been benchmarked.** Baselines are random, TF-IDF, BM25. TF-IDF standing in for the dense family is an argument, not a measurement. |
| "Beats BM25 end-to-end" | It does not. 0.378 vs 0.386 — parity, and only with the better linker. Say parity. |
| "Strictly dominates vector retrieval for relational queries" | The advantage is conditional: `Prec ≲ ℓ · pʰ`. At measured p=0.444, ℓ=0.595 the condition **fails** (two-hop ≈ 0.117). State the condition or state nothing. |
| "The topological layer improves retrieval" | It has never changed a metric outside noise on any benchmark. |
| "Learned sheaf maps improve retrieval" | Negative result: 9/9 configurations below the noise floor against an identity control. See `--sheaf-probe`. |
| "Learned maps cut residual by 48–62%, so the layer works" | That measurement fitted maps on data *generated to be sheaf-consistent*. It shows Procrustes recovers a linear map when a linear map made the data. It is not evidence of retrieval signal. |
| "Any embedding exhibits a semantic gap for directed relations" | False. Holds for **metric-ranked** retrieval only. Asymmetric scorers — TransE, ComplEx, RotatE — are not metrics and escape it. Cite them. |
| "Precision collapse makes vector retrieval fail" | Concentration of measure applies to **isotropic** data. Learned embeddings are anisotropic and concentrate near low-dimensional manifolds, which is why cosine works at n=3072. Asymptotic caution, not observed failure mode. |
| "Handles 10⁵ objects" | 5×10⁴ measured. |
| "Rust core, Python bindings" | No Rust exists. Pure Python over NetworkX. A Rust hot-path core is unstarted. |
| "HNSW over persistence diagrams" | It is cosine LSH. |
| "Uses a small local LLM for extraction" | Rule-based keyword extractor, or an API-backed extractor. No local model. |
| "Every finite-diagram query has a well-defined answer" (category theory) | The supporting claim — that the knowledge category has all finite limits and colimits when the graph is finite and connected — is false. A free category on a finite graph generally has neither. Dropped; it carried no operational content. |

## Scope limits worth restating

- **Oracle linking is a real setting but not an end-to-end one.** Never quote 0.580
  without saying "under oracle entity linking" in the same breath.
- **A returned path is a claim, not a proof.** Traversal from a wrong anchor fails
  confidently and emits a clean typed path. The interpretability benefit inverts into a
  liability when the graph or anchor is wrong.
- **Multiplicative fragility is structural.** Traversal accuracy is multiplicative in
  extraction and linking accuracy; lexical and dense retrieval degrade gracefully. This
  is a property of the architecture, not a bug awaiting a fix.

## Open experiments, in value order

1. **Dense-retrieval baseline.** The largest hole. Everything comparative rests on it.
2. **LLM linker, keyed run.** Implemented and unit-tested, never measured. ~70% link
   accuracy is the threshold that would flip end-to-end parity into a win.
3. **LLM extractor, quantified.** How much of the 0.444 recall ceiling it recovers.
4. **Neural stalks for the sheaf probe.** The one substantive untried variable in the
   negative result; the harness takes them as a drop-in.
5. **HotpotQA and MuSiQue loaders.** One external dataset is not enough to generalise.

## Reproducing every number in the paper

```bash
cookix eval --seed 0 --worlds 40 --k 5                          # synthetic corpus
cookix eval --dataset 2wiki --path dev.json --k 10              # oracle-linked
cookix eval --dataset 2wiki --path dev.json --no-oracle --linker surface
cookix eval --extraction                                        # extraction ceiling
cookix eval --sheaf-probe --path dev.json --dim 32              # the negative result
cookix eval --perf ; cookix eval --scale ; cookix loadtest      # performance
```

`dev.json` is the 2WikiMultiHopQA dev split in its original schema, not vendored here
(~56 MB).
