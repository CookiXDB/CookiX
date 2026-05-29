"""Built-in demo scenarios from the NoVectDB paper.

These construct small, fully-typed Knowledge graphs that exercise the features
flat vector retrieval cannot handle: directed causal edges (umbrella) and
multi-hop compatibility chains (pipe).
"""

from __future__ import annotations

from .database import Database, connect


def umbrella_db() -> Database:
    """The motivating example (paper Sec. 1.1): ``umbrella prevents rain wets coat``.

    A vector database clusters {rain, coat, umbrella, ...} together and cannot
    answer "what prevents rain from reaching the coat?". CookiX answers it with
    the directed path umbrella --[prevents]--> rain --[wets]--> coat.
    """
    db = connect("umbrella-demo")
    db.insert({"_id": "umbrella", "content": "a device that blocks rain",
               "edges": [("prevents", "rain")]})
    db.insert({"_id": "rain", "content": "falling water from clouds",
               "edges": [("causes", "wet_coat")]})
    db.insert({"_id": "wet_coat", "content": "a coat soaked by water"})
    db.insert({"_id": "raincoat", "content": "waterproof coat",
               "edges": [("prevents", "wet_coat")]})
    db.insert({"_id": "storm", "content": "violent weather",
               "edges": [("causes", "rain")]})
    db.insert({"_id": "sunshine", "content": "clear bright weather",
               "edges": [("contradicts", "rain")]})
    return db


def pipe_db() -> Database:
    """Engineering compatibility chain (paper Sec. 9, Task B).

    Answers multi-hop questions like "is pipe A compatible with fitting B via an
    adapter?" by traversing typed edges, and detects spec conflicts.
    """
    db = connect("pipe-demo")
    db.insert({"_id": "pipe_120mm", "content": "120mm HDPE pipe",
               "edges": [("similar_to", "pipe_130mm"), ("conforms_to", "iso_4422")]})
    db.insert({"_id": "pipe_130mm", "content": "130mm HDPE pipe",
               "edges": [("compatible_with", "fitting_B")]})
    db.insert({"_id": "fitting_B", "content": "flanged fitting B",
               "edges": [("requires", "adapter_ring")]})
    db.insert({"_id": "adapter_ring", "content": "reducing adapter ring",
               "edges": [("used_in", "steel_pipe")]})
    db.insert({"_id": "steel_pipe", "content": "galvanised steel pipe",
               "edges": [("contradicts", "iso_4422")]})
    db.insert({"_id": "iso_4422", "content": "ISO 4422 PVC pressure-pipe standard"})
    return db


DEMOS = {"umbrella": umbrella_db, "pipe": pipe_db}
