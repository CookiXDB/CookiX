"""Does the sheaf residual actually recognise a coherent reasoning chain?

This is the falsification test the existing sheaf study (:mod:`cookix.eval.sheaf_study`)
cannot perform. That study learns restriction maps on synthetic data *generated to be
sheaf-consistent* and shows the residual drops — which only confirms that Procrustes
recovers a linear map when a linear map is what produced the data. It is circular by
construction, and it says nothing about whether the residual carries retrieval signal.

The question that matters is discriminative, not absolute:

    given a real chain and a broken one, does the residual rank the real one lower?

So this module scores **gold evidence chains against deliberately corrupted chains**
on **held-out** data, with stalks derived from entity **text** rather than from a hash
of the entity id (the default placeholder stalk carries no semantics at all, so no
result computed against it means anything).

Three map families are scored, and the third is the point:

* ``placeholder`` — the shipped random orthogonal maps. The null hypothesis.
* ``identity`` — every map is ``I``, so the residual collapses to ``||x_a - x_b||``:
  pure endpoint-embedding distance that ignores the relation chain entirely. **This is
  the control that decides whether the sheaf layer earns its existence.**
* ``learned`` — orthogonal Procrustes maps fitted on training-split edges only.

The verdict rule is stated up front so it cannot be moved afterwards: ``learned`` must
beat **both** ``placeholder`` **and** ``identity``. Beating ``placeholder`` alone proves
only that fitting beats not fitting. If ``learned`` merely ties ``identity``, the sheaf
machinery is an expensive re-derivation of embedding cosine and should be cut.

A structural limitation this test exposes, worth stating plainly: the residual
``||S_π(x_a) - x_b||`` reads only the *source stalk*, the *relation sequence*, and the
*target stalk*. Intermediate entities never enter the computation, so the residual is
mathematically incapable of distinguishing two paths that share endpoints and relation
sequence but pass through different middles. Corruptions are therefore chosen to vary
only what the residual can actually see.
"""

from __future__ import annotations

import random
import re
from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from ..sheaf import composition
from ..sheaf.learning import learn_restriction_maps
from .datasets import RelationalDataset, normalise_entity

_TOKEN = re.compile(r"[a-z0-9]+")

# Corruption families. ``shuffle`` needs >=2 hops; the rest apply to any chain.
CORRUPTIONS = ("relation_swap", "tail_swap", "source_swap", "shuffle", "detour")


# --------------------------------------------------------------------------- #
# Stalks from entity text (not from an id hash)
# --------------------------------------------------------------------------- #
def text_stalks(
    entity_text: dict[str, str], dim: int = 64, seed: int = 0
) -> dict[str, np.ndarray]:
    """Content-derived stalks: TF-IDF over entity text, randomly projected to ``dim``.

    A deterministic signed random projection (Johnson-Lindenstrauss sketch) of the
    TF-IDF vector, L2-normalised. Each token's projection column is drawn from an RNG
    seeded by the token itself, so the sketch is reproducible without materialising a
    ``dim x |vocab|`` matrix.

    This is the offline rung of "real embeddings": the stalk is a function of what the
    entity's text *says*, which is the property the experiment needs. It is a lexical
    sketch, not a neural sentence embedding — a neural encoder would be the stronger
    version of the same test and is the obvious follow-up if the signal is there.
    """
    docs = {key: _TOKEN.findall(text.lower()) for key, text in entity_text.items()}
    df: dict[str, int] = defaultdict(int)
    for tokens in docs.values():
        for tok in set(tokens):
            df[tok] += 1
    n_docs = max(len(docs), 1)

    # Cache one projection vector per token, derived deterministically from the token.
    proj: dict[str, np.ndarray] = {}

    def column(token: str) -> np.ndarray:
        vec = proj.get(token)
        if vec is None:
            token_seed = (hash((seed, token)) & 0xFFFFFFFF) ^ seed
            vec = np.random.default_rng(token_seed).normal(size=dim)
            proj[token] = vec
        return vec

    stalks: dict[str, np.ndarray] = {}
    for key, tokens in docs.items():
        if not tokens:
            continue
        tf: dict[str, int] = defaultdict(int)
        for tok in tokens:
            tf[tok] += 1
        acc = np.zeros(dim)
        for tok, count in tf.items():
            idf = np.log(n_docs / (1.0 + df[tok])) + 1.0
            acc += (1.0 + np.log(count)) * idf * column(tok)
        norm = float(np.linalg.norm(acc))
        if norm > 0:
            stalks[key] = acc / norm
    return stalks


# --------------------------------------------------------------------------- #
# Chains
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Chain:
    """A reasoning chain reduced to what the residual can see.

    ``triples`` keeps the original ``(subject, relation, object)`` hops so a test
    chain's own edges can be withheld from map learning. The residual itself never
    reads them — see the module docstring on intermediate-entity blindness.
    """

    source: str
    relations: tuple[str, ...]
    target: str
    triples: tuple[tuple[str, str, str], ...] = ()

    @property
    def hops(self) -> int:
        return len(self.relations)


def extract_chains(dataset: RelationalDataset) -> tuple[list[Chain], list[tuple[str, str, str]]]:
    """Gold chains and the full edge list from a dataset's evidence triples.

    Only *connected* evidence chains are kept — those where each triple's object is the
    next triple's subject, so the chain is a genuine path. Disconnected evidence sets
    describe comparison questions rather than a traversal and are excluded (counted in
    the report).
    """
    chains: list[Chain] = []
    edges: list[tuple[str, str, str]] = []
    for ex in dataset.examples:
        triples = [(normalise_entity(s), r, normalise_entity(o)) for s, r, o in ex.evidences]
        edges.extend(triples)
        if not triples:
            continue
        connected = all(triples[i][2] == triples[i + 1][0] for i in range(len(triples) - 1))
        if not connected:
            continue
        chains.append(
            Chain(
                source=triples[0][0],
                relations=tuple(r for _, r, _ in triples),
                target=triples[-1][2],
                triples=tuple(triples),
            )
        )
    return chains, edges


# --------------------------------------------------------------------------- #
# Corruptions
# --------------------------------------------------------------------------- #
def _detour(
    chain: Chain,
    adjacency: dict[str, list[tuple[str, str]]],
    max_hops: int,
) -> Chain | None:
    """A real alternative path between the same endpoints with a different relation chain.

    The hardest negative available: both chains exist in the graph and share endpoints,
    so nothing but the relation sequence distinguishes them. Found by bounded DFS.
    """
    stack: list[tuple[str, tuple[str, ...]]] = [(chain.source, ())]
    while stack:
        node, rels = stack.pop()
        if len(rels) >= max_hops:
            continue
        for relation, nxt in adjacency.get(node, ()):
            path = rels + (relation,)
            if nxt == chain.target and path != chain.relations:
                return Chain(chain.source, path, chain.target)
            if len(path) < max_hops:
                stack.append((nxt, path))
    return None


def corrupt(
    chain: Chain,
    vocabulary: list[str],
    entities: list[str],
    adjacency: dict[str, list[tuple[str, str]]],
    rng: random.Random,
    max_hops: int,
) -> dict[str, Chain]:
    """Build one negative per applicable corruption family for ``chain``."""
    out: dict[str, Chain] = {}

    # Swap one relation for a different one drawn from the observed vocabulary.
    alternatives = [r for r in vocabulary if r not in chain.relations]
    if alternatives:
        idx = rng.randrange(chain.hops)
        rels = list(chain.relations)
        rels[idx] = rng.choice(alternatives)
        out["relation_swap"] = Chain(chain.source, tuple(rels), chain.target)

    # Point the chain at the wrong destination / start it from the wrong place.
    others = [e for e in entities if e != chain.target and e != chain.source]
    if others:
        out["tail_swap"] = Chain(chain.source, chain.relations, rng.choice(others))
        out["source_swap"] = Chain(rng.choice(others), chain.relations, chain.target)

    # Same relations, wrong order: tests whether composition is order-sensitive at all.
    if chain.hops >= 2:
        for _ in range(8):
            shuffled = list(chain.relations)
            rng.shuffle(shuffled)
            if tuple(shuffled) != chain.relations:
                out["shuffle"] = Chain(chain.source, tuple(shuffled), chain.target)
                break

    detour = _detour(chain, adjacency, max_hops)
    if detour is not None:
        out["detour"] = detour
    return out


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def residual(chain: Chain, stalks: dict[str, np.ndarray], map_fn) -> float | None:
    """Normalised composition residual ``||S_π(x_a) - x_b|| / ||x_b||``."""
    xa, xb = stalks.get(chain.source), stalks.get(chain.target)
    if xa is None or xb is None:
        return None
    composed = xa
    for relation in chain.relations:
        composed = map_fn(relation) @ composed
    denom = float(np.linalg.norm(xb)) or 1.0
    return float(np.linalg.norm(composed - xb) / denom)


def auc(positive: list[float], negative: list[float]) -> float:
    """P(positive scores lower than negative), ties counted as half. Lower = coherent.

    0.5 is chance. Rank-based (Mann-Whitney U), so it is threshold-free.
    """
    if not positive or not negative:
        return float("nan")
    ordered = sorted(negative)
    total = 0.0
    for p in positive:
        greater = len(ordered) - bisect_right(ordered, p)
        equal = bisect_right(ordered, p) - bisect_left(ordered, p)
        total += greater + 0.5 * equal
    return total / (len(positive) * len(ordered))


@dataclass
class FamilyScore:
    """Discrimination achieved by one map family."""

    name: str
    pooled_auc: float
    by_corruption: dict[str, float] = field(default_factory=dict)
    paired_win_rate: dict[str, float] = field(default_factory=dict)
    mean_gold_residual: float = 0.0


@dataclass
class SheafProbeReport:
    dataset: str
    dim: int
    n_examples: int
    n_chains: int
    n_disconnected: int
    n_train_chains: int
    n_test_chains: int
    n_train_edges: int
    n_relations: int
    hop_counts: dict[int, int]
    corruption_counts: dict[str, int]
    scores: list[FamilyScore]
    median_edges_per_relation: float = 0.0
    underdetermined_relations: int = 0

    @property
    def degenerate(self) -> bool:
        """True when there is too little evidence to fit the maps honestly.

        An orthogonal ``dim x dim`` map has ``dim(dim-1)/2`` free parameters, so
        fitting one from fewer than ``dim`` matched pairs is underdetermined: Procrustes
        can rotate a handful of source vectors exactly onto their targets and drive the
        training residual to zero while learning nothing generalisable. Any verdict
        computed in that regime is overfitting, not signal.
        """
        return self.median_edges_per_relation < self.dim or self.n_test_chains < 30

    @property
    def verdict(self) -> str:
        """The pre-registered decision rule, applied."""
        table = {s.name: s.pooled_auc for s in self.scores}
        learned = table.get("learned", float("nan"))
        identity = table.get("identity", float("nan"))
        placeholder = table.get("placeholder", float("nan"))
        if not np.isfinite(learned):
            return "INCONCLUSIVE - no learned score"
        if self.degenerate:
            return (
                f"UNRELIABLE - insufficient evidence (median {self.median_edges_per_relation:.0f} "
                f"training edges/relation vs dim {self.dim}; {self.n_test_chains} test chains). "
                "Procrustes is underdetermined here, so any separation is overfitting. "
                "Re-run on the full 2Wiki dev split, or lower --dim."
            )
        if learned <= placeholder + 0.01:
            return "NEGATIVE - learned maps do not beat random placeholder maps"
        if learned <= identity + 0.01:
            return (
                "NEGATIVE - learned maps do not beat the identity control; the residual "
                "is reproducing endpoint embedding distance, not composition"
            )
        return "POSITIVE - learned maps beat both the placeholder and the identity control"


def run_sheaf_probe(
    dataset: RelationalDataset,
    *,
    dim: int = 64,
    seed: int = 0,
    test_fraction: float = 0.3,
    max_hops: int = 4,
) -> SheafProbeReport:
    """Score gold chains against corrupted chains on a held-out split."""
    rng = random.Random(seed)
    chains, all_edges = extract_chains(dataset)
    n_disconnected = len(dataset.examples) - len(chains)

    entity_text: dict[str, str] = {}
    for ex in dataset.examples:
        for title, text in ex.context:
            key = normalise_entity(title)
            if text and len(text) > len(entity_text.get(key, "")):
                entity_text[key] = text
    stalks = text_stalks(entity_text, dim=dim, seed=seed)

    # Keep only chains whose endpoints have stalks — otherwise there is nothing to score.
    chains = [c for c in chains if c.source in stalks and c.target in stalks]
    rng.shuffle(chains)
    split = max(1, int(len(chains) * (1.0 - test_fraction)))
    train_chains, test_chains = chains[:split], chains[split:]

    # Strict split: every triple belonging to a test chain is withheld from map
    # learning, even if the same triple also occurs in a training example. Without
    # this the maps could be fitted on the exact edges they are later scored on.
    held_out = {triple for chain in test_chains for triple in chain.triples}
    train_edges = [
        (a, r, b)
        for a, r, b in all_edges
        if a in stalks and b in stalks and (a, r, b) not in held_out
    ]

    adjacency: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for a, r, b in all_edges:
        adjacency[a].append((r, b))
    vocabulary = sorted({r for _, r, _ in all_edges})
    entities = sorted(stalks)

    learned = learn_restriction_maps(train_edges, stalks, dim)
    eye = np.eye(dim)
    families = {
        "placeholder": lambda r: composition.restriction_map(r, dim),
        "identity": lambda r: eye,
        "learned": lambda r: learned.get(r, eye),
    }

    # Build every (gold, negatives) pair once so all families score identical inputs.
    cases: list[tuple[Chain, dict[str, Chain]]] = []
    for chain in test_chains:
        negatives = corrupt(chain, vocabulary, entities, adjacency, rng, max_hops)
        negatives = {
            kind: c for kind, c in negatives.items()
            if c.source in stalks and c.target in stalks
        }
        if negatives:
            cases.append((chain, negatives))

    corruption_counts: dict[str, int] = defaultdict(int)
    for _, negatives in cases:
        for kind in negatives:
            corruption_counts[kind] += 1

    scores: list[FamilyScore] = []
    for name, map_fn in families.items():
        gold: list[float] = []
        neg_by_kind: dict[str, list[float]] = defaultdict(list)
        wins: dict[str, list[int]] = defaultdict(list)
        for chain, negatives in cases:
            g = residual(chain, stalks, map_fn)
            if g is None:
                continue
            gold.append(g)
            for kind, bad in negatives.items():
                n = residual(bad, stalks, map_fn)
                if n is None:
                    continue
                neg_by_kind[kind].append(n)
                wins[kind].append(1 if g < n else 0)
        pooled = [v for values in neg_by_kind.values() for v in values]
        scores.append(
            FamilyScore(
                name=name,
                pooled_auc=auc(gold, pooled),
                by_corruption={k: auc(gold, v) for k, v in sorted(neg_by_kind.items())},
                paired_win_rate={
                    k: (sum(v) / len(v) if v else float("nan"))
                    for k, v in sorted(wins.items())
                },
                mean_gold_residual=float(np.mean(gold)) if gold else float("nan"),
            )
        )

    hop_counts: dict[int, int] = defaultdict(int)
    for chain, _ in cases:
        hop_counts[chain.hops] += 1

    # Evidence density per relation drives whether the fit can be trusted at all.
    per_relation: dict[str, int] = defaultdict(int)
    for _, r, _ in train_edges:
        per_relation[r] += 1
    counts = sorted(per_relation.values())
    median_density = float(np.median(counts)) if counts else 0.0
    underdetermined = sum(1 for c in counts if c < dim)

    return SheafProbeReport(
        dataset=dataset.name,
        dim=dim,
        n_examples=len(dataset.examples),
        n_chains=len(chains),
        n_disconnected=n_disconnected,
        n_train_chains=len(train_chains),
        n_test_chains=len(cases),
        n_train_edges=len(train_edges),
        n_relations=len(vocabulary),
        hop_counts=dict(sorted(hop_counts.items())),
        corruption_counts=dict(sorted(corruption_counts.items())),
        scores=scores,
        median_edges_per_relation=median_density,
        underdetermined_relations=underdetermined,
    )


def to_markdown_sheaf_probe(report: SheafProbeReport) -> str:
    """Render the probe as a Markdown report, verdict included."""
    lines = [
        "## Sheaf residual discrimination probe",
        "",
        f"Dataset `{report.dataset}` | stalk dim {report.dim} | "
        f"{report.n_examples} examples -> {report.n_chains} connected chains "
        f"({report.n_disconnected} disconnected, excluded)",
        f"Split: {report.n_train_chains} train / {report.n_test_chains} test scored | "
        f"{report.n_train_edges} training edges | {report.n_relations} relations",
        f"Evidence density: median {report.median_edges_per_relation:.0f} training "
        f"edges/relation ({report.underdetermined_relations} relations below dim "
        f"{report.dim}, i.e. underdetermined)",
        "Test chains by hops: "
        + ", ".join(f"{h}-hop {n}" for h, n in report.hop_counts.items()),
        "Negatives built: "
        + ", ".join(f"{k} {n}" for k, n in report.corruption_counts.items()),
        "",
        "AUC = P(gold chain scores lower residual than corrupted chain). "
        "0.5 is chance.",
        "",
    ]
    kinds = sorted(report.corruption_counts)
    header = "| maps | pooled AUC | " + " | ".join(kinds) + " | mean gold residual |"
    lines.append(header)
    lines.append("|" + "---|" * (len(kinds) + 3))
    for score in report.scores:
        cells = [f"{score.by_corruption.get(k, float('nan')):.3f}" for k in kinds]
        lines.append(
            f"| {score.name} | **{score.pooled_auc:.3f}** | "
            + " | ".join(cells)
            + f" | {score.mean_gold_residual:.3f} |"
        )
    lines += ["", f"**Verdict: {report.verdict}**"]
    return "\n".join(lines)
