"""The Umbrella Problem — NoVectDB's motivating example.

A vector database maps {rain, coat, umbrella, storm, ...} to nearby points and
returns them all with similar scores for "what prevents rain from reaching the
coat?". The correct answer requires a *directed* causal path, which cosine
distance cannot express:

    umbrella --[prevents]--> rain --[causes]--> wet_coat

Run:  python examples/umbrella.py
"""

from __future__ import annotations

from cookix.demos import umbrella_db


def main() -> None:
    db = umbrella_db()
    print(f"Loaded umbrella scenario: {len(db)} Knowledge Objects\n")

    print("Q: How does the umbrella relate to a wet coat?")
    for r in db.query(anchor="umbrella", target="wet_coat", mode="reasoning"):
        print("  " + r.explain())

    print("\nQ: What directly prevents things? (deterministic single-hop)")
    for r in db.query(anchor="umbrella", relation="prevents"):
        print("  " + r.explain())

    print("\nQ: What contradicts rain?")
    for r in db.contradictions("rain"):
        print("  " + r.explain())


if __name__ == "__main__":
    main()
