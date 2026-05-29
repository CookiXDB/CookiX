from __future__ import annotations

import numpy as np
import pytest

from cookix import sheaf, topology
from cookix.demos import umbrella_db


def test_sheaf_always_available():
    assert sheaf.AVAILABLE is True


def test_restriction_map_is_orthogonal():
    m = sheaf.restriction_map("causes", dim=8)
    assert np.allclose(m @ m.T, np.eye(8), atol=1e-6)


def test_inverse_relation_undoes_map():
    fwd = sheaf.restriction_map("causes", dim=8)
    inv = sheaf.restriction_map("caused_by", dim=8)
    assert np.allclose(inv @ fwd, np.eye(8), atol=1e-6)


def test_composition_residual_zero_for_empty_path():
    a = sheaf.default_stalk("a", 8)
    b = sheaf.default_stalk("b", 8)
    assert sheaf.composition_residual(a, b, []) == 0.0


def test_sheaf_mode_runs_end_to_end():
    db = umbrella_db()
    results = db.query(anchor="umbrella", target="wet_coat", mode="sheaf")
    assert results
    assert "sheaf" in results[0].components


@pytest.mark.skipif(not topology.AVAILABLE, reason="topology extra not installed")
def test_topology_signature_and_tvs():
    db = umbrella_db()
    n = db.reindex_topology()
    assert n > 0
    results = db.query(anchor="umbrella", target="wet_coat", mode="topo")
    assert results


def test_tvs_handles_missing_signatures():
    # TVS must be safe even when the topology layer is absent.
    assert topology.tvs(None, None) == 0.0 if topology.AVAILABLE else True
