"""Ablation: do *learned* sheaf restriction maps lower composition residual?

The sheaf layer's whole premise is that the composition residual
``||S_π(x_a) - x_b||`` should be *low* for a coherent reasoning chain. With the
placeholder (random, relation-seeded) maps it is not — the maps are uninformed,
so residual is essentially arbitrary. This study quantifies what learning the
maps buys, on held-out edges and paths.

Methodology (deterministic, synthetic, honest):

* draw a ground-truth orthogonal map ``G_r`` per relation;
* build edges by sending a random source stalk through ``G_r`` plus Gaussian
  noise of scale ``noise`` — so the data is *approximately* sheaf-consistent,
  not perfectly so (real graphs never are);
* split edges into train / test, learn maps from train only, and compare the
  mean composition residual of placeholder vs learned maps on held-out edges
  (1-hop) and held-out 2-hop chains.

Learned residual approaching ``noise`` while placeholder residual stays near the
random baseline (~√2) is the evidence that the maps carry recoverable structure.
The synthetic setup is a *necessary* demonstration, not a sufficient one: it
shows learning works when relations act near-linearly on stalks; whether real
semantic frames satisfy that is the open empirical question.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..sheaf import composition
from ..sheaf.learning import learn_restriction_maps, mean_composition_residual

# Mix of asymmetric (causes/prevents/requires) and symmetric (contradicts) types.
_RELATIONS = ("causes", "prevents", "requires", "contradicts")


def _random_orthogonal(dim: int, rng: np.random.Generator) -> np.ndarray:
    q, r = np.linalg.qr(rng.standard_normal((dim, dim)))
    return q * np.sign(np.diag(r))


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n else v


@dataclass
class SheafAblation:
    dim: int
    noise: float
    n_train_edges: int
    n_test_edges: int
    n_test_paths: int
    residual_1hop_placeholder: float
    residual_1hop_learned: float
    residual_2hop_placeholder: float
    residual_2hop_learned: float


def run_sheaf_ablation(
    dim: int = 16,
    noise: float = 0.1,
    n_per_relation: int = 60,
    test_fraction: float = 0.3,
    n_paths: int = 120,
    seed: int = 0,
) -> SheafAblation:
    rng = np.random.default_rng(seed)
    truth = {r: _random_orthogonal(dim, rng) for r in _RELATIONS}

    stalks: dict[str, np.ndarray] = {}
    train_edges: list[tuple[str, str, str]] = []
    test_edges: list[tuple[str, str, str]] = []
    n_test = int(n_per_relation * test_fraction)

    counter = 0
    for rel in _RELATIONS:
        for i in range(n_per_relation):
            a, b = f"n{counter}", f"n{counter + 1}"
            counter += 2
            xa = _unit(rng.standard_normal(dim))
            xb = _unit(truth[rel] @ xa + noise * rng.standard_normal(dim))
            stalks[a] = xa
            stalks[b] = xb
            (test_edges if i < n_test else train_edges).append((a, rel, b))

    # Held-out 2-hop chains a --r1--> b --r2--> c, noisily consistent end to end.
    test_paths: list[tuple[str, tuple[str, ...], str]] = []
    for _ in range(n_paths):
        r1, r2 = rng.choice(_RELATIONS, size=2)
        a, b, c = f"p{counter}", f"p{counter + 1}", f"p{counter + 2}"
        counter += 3
        xa = _unit(rng.standard_normal(dim))
        xb = _unit(truth[r1] @ xa + noise * rng.standard_normal(dim))
        xc = _unit(truth[r2] @ xb + noise * rng.standard_normal(dim))
        stalks[a], stalks[b], stalks[c] = xa, xb, xc
        test_paths.append((a, (str(r1), str(r2)), c))

    learned = learn_restriction_maps(train_edges, stalks, dim)

    def placeholder_fn(rel: str) -> np.ndarray:
        return composition.restriction_map(rel, dim)

    def learned_fn(rel: str) -> np.ndarray:
        return learned[rel]

    edge_paths = [(a, (rel,), b) for a, rel, b in test_edges]
    return SheafAblation(
        dim=dim,
        noise=noise,
        n_train_edges=len(train_edges),
        n_test_edges=len(test_edges),
        n_test_paths=len(test_paths),
        residual_1hop_placeholder=mean_composition_residual(edge_paths, stalks, placeholder_fn),
        residual_1hop_learned=mean_composition_residual(edge_paths, stalks, learned_fn),
        residual_2hop_placeholder=mean_composition_residual(test_paths, stalks, placeholder_fn),
        residual_2hop_learned=mean_composition_residual(test_paths, stalks, learned_fn),
    )


def to_markdown_sheaf(ab: SheafAblation) -> str:
    def drop(p: float, ln: float) -> str:
        return f"{(1 - ln / p) * 100:.0f}%" if p else "n/a"

    return "\n".join([
        "### Learned sheaf restriction maps: residual ablation",
        "",
        f"dim={ab.dim}, noise={ab.noise}, {ab.n_train_edges} train / "
        f"{ab.n_test_edges} test edges, {ab.n_test_paths} held-out 2-hop paths. "
        "Lower residual is better.",
        "",
        "| maps | 1-hop residual | 2-hop residual |",
        "|---|---|---|",
        f"| placeholder (random) | {ab.residual_1hop_placeholder:.3f} | "
        f"{ab.residual_2hop_placeholder:.3f} |",
        f"| learned (Procrustes) | {ab.residual_1hop_learned:.3f} | "
        f"{ab.residual_2hop_learned:.3f} |",
        f"| **residual drop** | **{drop(ab.residual_1hop_placeholder, ab.residual_1hop_learned)}** "
        f"| **{drop(ab.residual_2hop_placeholder, ab.residual_2hop_learned)}** |",
        "",
        "Learned maps are evaluated on edges/paths held out of training; the "
        "remaining residual reflects the injected noise floor, not memorisation.",
    ])
