from __future__ import annotations

import numpy as np

from cookix import sheaf
from cookix.eval.sheaf_study import run_sheaf_ablation, to_markdown_sheaf
from cookix.sheaf.composition import restriction_map, set_learned_maps
from cookix.sheaf.learning import (
    learn_restriction_maps,
    orthogonal_procrustes,
)


def test_procrustes_recovers_known_orthogonal_map():
    rng = np.random.default_rng(0)
    dim, n = 8, 50
    q, _ = np.linalg.qr(rng.standard_normal((dim, dim)))
    source = rng.standard_normal((dim, n))
    target = q @ source
    recovered = orthogonal_procrustes(source, target)
    assert np.allclose(recovered, q, atol=1e-6)


def test_procrustes_empty_evidence_is_identity():
    f = orthogonal_procrustes(np.zeros((4, 0)), np.zeros((4, 0)))
    assert np.allclose(f, np.eye(4))


def test_learn_recovers_maps_and_ties_inverse():
    rng = np.random.default_rng(1)
    dim = 6
    g, _ = np.linalg.qr(rng.standard_normal((dim, dim)))
    stalks: dict[str, np.ndarray] = {}
    edges = []
    for i in range(40):
        a, b = f"a{i}", f"b{i}"
        xa = rng.standard_normal(dim)
        stalks[a] = xa
        stalks[b] = g @ xa  # perfectly consistent "causes" edge
        edges.append((a, "causes", b))
    maps = learn_restriction_maps(edges, stalks, dim)
    assert np.allclose(maps["causes"], g, atol=1e-6)
    # inverse relation must be the transpose so traversal reverses cleanly.
    assert np.allclose(maps["caused_by"], g.T, atol=1e-6)


def test_learned_beats_placeholder_on_ablation():
    ab = run_sheaf_ablation(seed=0)
    assert ab.residual_1hop_learned < ab.residual_1hop_placeholder
    assert ab.residual_2hop_learned < ab.residual_2hop_placeholder
    # placeholder is uninformed: residual sits near the random-orthogonal floor.
    assert ab.residual_1hop_placeholder > 1.0
    md = to_markdown_sheaf(ab)
    assert "residual drop" in md


def test_ablation_is_deterministic():
    a = run_sheaf_ablation(seed=3)
    b = run_sheaf_ablation(seed=3)
    assert a == b


def test_set_learned_maps_overrides_placeholder():
    dim = 5
    fake = np.eye(dim) * 1.0  # identity is a valid orthogonal map
    placeholder = restriction_map("causes", dim)
    try:
        set_learned_maps({"causes": fake})
        assert np.allclose(restriction_map("causes", dim), fake)
        # dimension mismatch falls back to the placeholder
        assert restriction_map("causes", 7).shape == (7, 7)
        # uncovered relations still use the placeholder
        assert np.allclose(restriction_map("prevents", dim),
                           sheaf.restriction_map("prevents", dim))
    finally:
        set_learned_maps(None)
    assert np.allclose(restriction_map("causes", dim), placeholder)
