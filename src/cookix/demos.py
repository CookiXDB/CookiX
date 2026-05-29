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


def supply_chain_db() -> Database:
    """Software supply-chain impact analysis — a real developer use case.

    "Which of my services are reachable by this CVE, and through *which*
    dependency chain?" is a multi-hop, directed question: a service depends_on a
    library that depends_on another that is affected_by a CVE. A keyword/vector
    search over package names can't connect a service to a vulnerability three
    transitive deps away — but typed-edge traversal returns the exact chain.

    Edges: ``depends_on`` (service→lib, lib→lib) and ``affected_by`` (lib→CVE).
    """
    db = connect("supply-chain-demo")
    rows = [
        # services
        ("checkout_api", "payment checkout HTTP service", [("depends_on", "web_framework"), ("depends_on", "fast_json")]),
        ("auth_service", "authentication service", [("depends_on", "web_framework"), ("depends_on", "crypto_utils")]),
        ("billing_worker", "async billing job runner", [("depends_on", "fast_json"), ("depends_on", "pdf_gen")]),
        ("docs_portal", "static documentation site", [("depends_on", "markdown_lib")]),
        # libraries (transitive)
        ("web_framework", "HTTP web framework", [("depends_on", "http_core")]),
        ("http_core", "low-level HTTP engine", [("depends_on", "tinyparse")]),
        ("fast_json", "fast JSON (de)serialiser", [("depends_on", "tinyparse")]),
        ("crypto_utils", "crypto helpers", [("depends_on", "bignum")]),
        ("pdf_gen", "PDF generation library", [("depends_on", "image_lib")]),
        ("tinyparse", "tiny tokeniser/parser", [("affected_by", "CVE_2024_5001")]),
        ("image_lib", "image decoding library", [("affected_by", "CVE_2023_9002")]),
        ("markdown_lib", "markdown renderer (no known CVE)", []),
        ("bignum", "big-integer arithmetic (no known CVE)", []),
        # vulnerabilities
        ("CVE_2024_5001", "critical RCE in tinyparse parser", []),
        ("CVE_2023_9002", "high-severity heap overflow in image_lib", []),
    ]
    for oid, content, edges in rows:
        db.insert({"_id": oid, "content": content, "edges": edges})
    return db


DEMOS = {"umbrella": umbrella_db, "pipe": pipe_db, "deps": supply_chain_db}
