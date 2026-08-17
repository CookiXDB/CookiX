# Paper sources

| File | What it is |
|---|---|
| [`novectdb.tex`](novectdb.tex) | **Current** paper source, corrected edition (August 2026) |
| [`CHANGES.md`](CHANGES.md) | Itemised corrections against the February 2026 preprint |
| [`../paper.pdf`](../paper.pdf) | The February 2026 preprint — **superseded**, retained for the correction trail |

## Build

Needs a LaTeX distribution (TeX Live, MiKTeX) with `amsmath`, `amsthm`, `booktabs`,
`algorithm`, `hyperref`, `geometry`, `xcolor`.

```bash
cd docs/paper && pdflatex novectdb && pdflatex novectdb
```

Two passes resolve cross-references. The bibliography is inlined as a `thebibliography`
environment, so BibTeX is not required.

> Not yet compiled: no TeX toolchain was available on the machine where this source was
> written. It passes a structural check (balanced environments and braces, all
> `\ref`/`\cite` targets resolving, tabular column counts matching) but has not been
> through a real build.

## The rule this source follows

Every quantitative claim names the command that produces it, and no number appears that
this repository cannot reproduce. When a measurement contradicts a hypothesis the paper
would prefer, the measurement is reported — see §"A negative result for the sheaf layer"
and §"Corrections relative to the February 2026 preprint".

Reproducing the numbers:

```bash
cookix eval --seed 0 --worlds 40 --k 5                          # synthetic corpus
cookix eval --dataset 2wiki --path dev.json --k 10              # oracle-linked
cookix eval --dataset 2wiki --path dev.json --no-oracle --linker surface
cookix eval --extraction                                        # extraction ceiling
cookix eval --sheaf-probe --path dev.json --dim 32              # the negative result
cookix eval --perf ; cookix eval --scale ; cookix loadtest      # performance
```

`dev.json` is the 2WikiMultiHopQA dev split in its original schema. It is not vendored
here (~56 MB).
