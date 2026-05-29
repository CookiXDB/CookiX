"""Pipe compatibility — multi-hop relational reasoning (paper Task B).

Engineering knowledge bases need answers like "is pipe A compatible with fitting
B, and via what?". CookiX traverses typed edges to return the chain, and detects
standards conflicts that vector similarity would never surface.

Run:  python examples/pipe_compatibility.py
"""

from __future__ import annotations

from cookix.demos import pipe_db


def main() -> None:
    db = pipe_db()
    print(f"Loaded pipe scenario: {len(db)} Knowledge Objects\n")

    print("Q: How does pipe_120mm connect to a steel pipe? (multi-hop chain)")
    for r in db.query(anchor="pipe_120mm", target="steel_pipe", mode="reasoning"):
        print("  " + r.explain())

    print("\nQ: What does fitting_B require?")
    for r in db.query(anchor="fitting_B", relation="requires"):
        print("  " + r.explain())

    print("\nContradiction check: does steel_pipe conflict with a standard?")
    for r in db.contradictions("steel_pipe"):
        print("  " + r.explain())


if __name__ == "__main__":
    main()
