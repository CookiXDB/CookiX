from __future__ import annotations

from cookix.demos import DEMOS, supply_chain_db


def test_all_demos_build():
    for name, builder in DEMOS.items():
        db = builder()
        assert len(db) > 0, f"demo {name} is empty"


def test_supply_chain_impact_paths():
    """The supply-chain example's core claim: typed traversal finds the exact
    multi-hop chain from a service to a transitive CVE."""
    db = supply_chain_db()

    # checkout_api reaches the CVE via fast_json -> tinyparse (3 hops).
    hits = db.query(anchor="checkout_api", target="CVE_2024_5001", mode="graph")
    assert hits, "checkout_api should be reachable to the CVE"
    chain = [s.relation for s in hits[0].path]
    assert chain == ["depends_on", "depends_on", "affected_by"]
    assert hits[0].object_id == "CVE_2024_5001"

    # docs_portal depends only on a clean lib — no path to the CVE.
    assert db.query(anchor="docs_portal", target="CVE_2024_5001",
                    mode="graph", max_hops=5) == []

    # Blast radius: exactly the three wired services are affected.
    impacted = [s for s in ("checkout_api", "auth_service", "billing_worker", "docs_portal")
                if db.query(anchor=s, target="CVE_2024_5001", mode="graph", max_hops=5)]
    assert set(impacted) == {"checkout_api", "auth_service", "billing_worker"}
