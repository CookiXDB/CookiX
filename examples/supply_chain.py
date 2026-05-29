"""Software supply-chain impact analysis — a real CookiX project.

The question every security team asks when a CVE drops: **"which of our services
are actually affected, and through which dependency path?"** That is a directed,
multi-hop question — a service ``depends_on`` a library that ``depends_on``
another that is ``affected_by`` the CVE. A keyword or vector search over package
names cannot connect a service to a vulnerability three transitive hops away.
CookiX traverses the typed edges and returns the **exact chain that proves it**.

This example builds a small dependency graph, then answers three real questions:

    1. What does a service directly depend on?
    2. Is a given service reachable by a CVE — and via what path?
    3. Blast radius: which services does a CVE impact (with the shortest path each)?

Run:  python examples/supply_chain.py
Explore visually:  cookix serve --demo deps   (then open http://127.0.0.1:8000)
"""

from __future__ import annotations

from cookix.demos import supply_chain_db

SERVICES = ["checkout_api", "auth_service", "billing_worker", "docs_portal"]


def main() -> None:
    db = supply_chain_db()
    print(f"Loaded supply-chain graph: {len(db)} objects "
          f"(services, libraries, CVEs)\n")

    # 1. Direct dependencies (single-hop typed lookup).
    print("1) Direct dependencies of checkout_api:")
    for r in db.query(anchor="checkout_api", relation="depends_on", mode="graph"):
        print(f"     - {r.object_id}")

    # 2. Is a specific service reachable by a specific CVE, and how?
    print("\n2) Is checkout_api affected by CVE_2024_5001 — and via what chain?")
    hits = db.query(anchor="checkout_api", target="CVE_2024_5001", mode="reasoning")
    if hits:
        print("     " + hits[0].explain())
    else:
        print("     not reachable")

    # 3. Blast radius: which services can reach this CVE? Show the shortest chain.
    cve = "CVE_2024_5001"
    print(f"\n3) Blast radius of {cve} (critical RCE in tinyparse):")
    impacted = []
    for svc in SERVICES:
        paths = db.query(anchor=svc, target=cve, mode="graph", max_hops=5)
        if paths:
            impacted.append(svc)
            chain = " -> ".join([paths[0].path[0].source]
                                + [s.target for s in paths[0].path])
            print(f"     [AFFECTED] {svc}: {chain}  ({paths[0].hops} hops)")
        else:
            print(f"     [clear]    {svc}")
    print(f"\n   => {len(impacted)}/{len(SERVICES)} services impacted: "
          f"{', '.join(impacted)}")

    print("\nWhy this is hard for a vector DB: 'checkout_api' and 'CVE_2024_5001' "
          "share no words and sit far apart in any embedding space. The link only "
          "exists in the *typed, directed* dependency edges — which is exactly "
          "what CookiX traverses.")


if __name__ == "__main__":
    main()
