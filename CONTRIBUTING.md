# Contributing to CookiX

Thanks for your interest in CookiX. The project is young and the most valuable
contributions right now are **evidence** — benchmarks, ablations, and honest
results — not just features.

## Development setup

```bash
git clone https://github.com/cookix-db/cookix.git
cd cookix
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"        # core + dev tools
pip install -e ".[dev,all]"    # also installs topology/kuzu/llm extras
```

## Before you open a PR

```bash
pytest            # all tests must pass
ruff check .      # lint
ruff format .     # format
mypy src/cookix   # type-check (best effort)
```

## Project layout

```
src/cookix/
├── model.py          # Knowledge Object K=(V,E,T,S), QueryResult
├── relations.py      # controlled relation vocabulary
├── storage/          # backends: memory (default), kuzu (durable)
├── topology/         # persistent-homology signatures + TVS  (optional layer)
├── sheaf/            # sheaf composition residual            (experimental)
├── extraction/       # relation extraction + intent parsing
├── engine.py         # the NoVectDB query pipeline + ablation modes
├── database.py       # the Mongo-style public API
└── demos.py          # built-in demo scenarios
```

## Design principles

1. **The graph core has zero heavy dependencies.** Topology and sheaf layers are
   optional extras and must degrade gracefully when not installed.
2. **Every research layer is ablatable.** New retrieval signal goes behind a
   `RetrievalMode` so its contribution can be measured, never assumed.
3. **Be honest in docs and results.** If a layer doesn't help in an ablation,
   we report that. Negative results are welcome.

## Where we need help

- **Evaluation** — public-benchmark harness (HotpotQA, 2WikiMultiHopQA, MuSiQue),
  fair GraphRAG/KG baselines, ablation studies.
- **Relation extraction** — extraction quality is the ceiling on multi-hop accuracy.
- **Topological data analysis** — better, cheaper signatures; grounding their meaning.
- **Learned sheaves** — neural sheaf diffusion for the restriction maps.
- **Storage** — hardening the Kùzu backend; eventually a Rust hot path.

## Code style

- Python 3.10+, type hints throughout, `ruff` for lint/format (line length 100).
- Comments explain *why*, not *what*. Keep them rare and load-bearing.

By contributing you agree your contributions are licensed under Apache-2.0.
