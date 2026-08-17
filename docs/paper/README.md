# Paper sources

| File | What it is |
|---|---|
| [`novectdb.tex`](novectdb.tex) | Paper source |
| [`CLAIMS.md`](CLAIMS.md) | Internal note: what this project may and may not claim, and the measurement behind each |

## Build

Needs a LaTeX distribution (TeX Live, MiKTeX) with `amsmath`, `amsthm`, `booktabs`,
`algorithm`, `hyperref`, `geometry`.

```bash
cd docs/paper && pdflatex novectdb && pdflatex novectdb
```

Two passes resolve cross-references. The bibliography is inlined as a `thebibliography`
environment, so BibTeX is not required.

> **Not yet compiled.** No TeX toolchain was available on the machine where this source
> was written. It passes a structural check (balanced environments and braces, all
> `\ref`/`\cite` targets resolving, tabular column counts matching) but has not been
> through a real build.

## The rule this source follows

Every quantitative claim names the command that produces it, and no number appears that
this repository cannot reproduce. Where a measurement contradicts a hypothesis the paper
would prefer, the measurement is reported — see §"A negative result for the sheaf layer"
and §"No dense-retrieval baseline has been run". See [`CLAIMS.md`](CLAIMS.md) for the
full discipline.

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
