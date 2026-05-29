"""Randomised, model-based fuzz tests (Phase 19 hardening).

No `hypothesis` dependency: we drive the backend with seeded random operation
sequences and check it against a trivial reference model (a plain dict). This is
how subtle state bugs — the kind unit tests miss — surface. Two properties:

1. **Model equivalence under random ops + crashes** — a random mix of
   put/delete, with periodic simulated crashes (drop the WAL handle, reopen),
   must always recover to exactly the set of committed objects the model holds.
2. **Query robustness** — random anchor queries on a random graph never raise and
   always return well-formed, finite-scored results that point at real nodes.
"""

from __future__ import annotations

import random

from cookix import connect
from cookix.model import Edge, KnowledgeObject
from cookix.storage.durable import DurableBackend


def _obj(oid: str, edges=None) -> KnowledgeObject:
    return KnowledgeObject(id=oid, content=oid,
                           edges=[Edge(r, t) for r, t in (edges or [])])


def test_model_equivalence_under_random_ops_and_crashes(tmp_path):
    for seed in range(8):
        rng = random.Random(seed)
        db_dir = tmp_path / f"fuzz_{seed}"
        backend = DurableBackend(db_dir, autosnapshot_ops=rng.choice([5, 50, 10_000]))
        model: set[str] = set()
        universe = [f"k{i}" for i in range(15)]

        for _step in range(120):
            if rng.random() < 0.7:
                oid = rng.choice(universe)
                backend.put(_obj(oid))
                model.add(oid)
            else:
                oid = rng.choice(universe)
                existed = backend.delete(oid)
                assert existed == (oid in model)
                model.discard(oid)

            # Backend and model must agree at every step.
            assert len(backend) == len(model)
            assert all((k in backend) == (k in model) for k in universe)

            # Occasionally "crash" and reopen; committed state must persist.
            if rng.random() < 0.1:
                backend._wal.close()
                backend = DurableBackend(db_dir)
                assert set(backend.all_ids()) == model

        backend._wal.close()
        recovered = DurableBackend(db_dir)
        assert set(recovered.all_ids()) == model


def test_random_queries_are_robust():
    import math

    for seed in range(5):
        rng = random.Random(seed)
        db = connect(f"fuzz-q-{seed}")
        rels = ["causes", "prevents", "part_of", "similar_to"]
        n = 60
        for i in range(n):
            edges = [(rng.choice(rels), f"n{rng.randrange(n)}")
                     for _ in range(rng.randint(0, 4))]
            db.insert({"_id": f"n{i}", "content": f"node {i}", "edges": edges})

        ids = {f"n{i}" for i in range(n)}
        for _ in range(50):
            anchor = f"n{rng.randrange(n)}"
            mode = rng.choice(["graph", "reasoning"])
            results = db.query(anchor=anchor, k=rng.randint(1, 10), mode=mode)
            for r in results:
                assert r.object_id in ids            # never invents a node
                assert math.isfinite(r.score)        # score is always finite
                for step in r.path:                  # path is well-formed
                    assert step.source and step.relation and step.target
