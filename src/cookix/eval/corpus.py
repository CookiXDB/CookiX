"""Reproducible synthetic relational corpus for benchmarking.

The point of NoVectDB is that *typed, directed edges* carry information that flat
content similarity does not. To test that claim fairly we need a corpus where:

* every entity has natural-language ``content`` describing **itself** (never its
  relations), so a content/vector retriever has something real to match on;
* the relational answers live **only** in typed edges, so recovering them
  requires traversal, not proximity;
* entities within a world share a topical adjective, so a lexical/vector
  baseline genuinely retrieves the right *neighbourhood* — it just cannot pick
  the relationally-correct entity out of it. That makes the comparison a
  steelman, not a strawman.

Each generated *world* has six entities wired with a fixed relational skeleton::

    shield --prevents--> storm        (agent blocks the hazard)
    cure   --prevents--> ruin         (a different agent blocks the damage)
    storm  --causes-->   ruin         (hazard leads to damage)
    spark  --causes-->   storm        (source leads to hazard)
    calm   --contradicts storm        (foil conflicts with the hazard)

From that skeleton we emit four query kinds with known gold answers: single-hop
relational (forward and inverse), multi-hop path, and contradiction.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

# Role nouns shared across every world (the relational skeleton is fixed); the
# per-world adjective makes each entity id unique and topically cohesive.
ROLES = ("shield", "storm", "ruin", "spark", "cure", "calm")

# 80 distinct adjectives -> supports up to 80 worlds with unique ids.
ADJECTIVES = (
    "amber", "azure", "basalt", "bronze", "cedar", "cobalt", "copper", "coral",
    "crimson", "cyan", "dusty", "ebony", "emerald", "flax", "frost", "garnet",
    "golden", "granite", "hazel", "indigo", "ivory", "jade", "khaki", "lilac",
    "linen", "maroon", "mauve", "mint", "ochre", "olive", "onyx", "opal",
    "pearl", "pewter", "plum", "quartz", "raven", "russet", "saffron", "sage",
    "sand", "scarlet", "sepia", "sienna", "silver", "slate", "steel", "tan",
    "teal", "topaz", "umber", "velvet", "verdant", "violet", "walnut", "willow",
    "amethyst", "beige", "blush", "brass", "carmine", "chartreuse", "denim",
    "fuchsia", "gilded", "glacier", "heather", "ice", "lemon", "magenta",
    "marble", "mocha", "navy", "peach", "rose", "ruby", "rust", "sky",
    "spruce", "tawny", "wheat",
)

# Descriptive, relation-free content templates (one per role). The shared
# ``{adj}`` gives a lexical retriever a real topical handle.
_CONTENT = {
    "shield": "the {adj} shield is a {adj} protective device people carry",
    "storm": "the {adj} storm is a {adj} hazardous condition in the region",
    "ruin": "the {adj} ruin is {adj} structural harm left behind",
    "spark": "the {adj} spark is a {adj} originating trigger event",
    "cure": "the {adj} cure is a {adj} remedy applied as a safeguard",
    "calm": "the {adj} calm is a {adj} tranquil opposite state of affairs",
}


@dataclass(frozen=True)
class EvalQuery:
    """A benchmark query with gold answers (and a gold path for multi-hop)."""

    qid: str
    text: str
    kind: str  # "single_hop" | "single_hop_inverse" | "multi_hop" | "contradiction"
    answers: tuple[str, ...]
    anchor: str
    target: str | None = None
    gold_path: tuple[str, ...] = ()


@dataclass
class Corpus:
    """A set of documents plus a labelled query set."""

    documents: list[dict] = field(default_factory=list)
    queries: list[EvalQuery] = field(default_factory=list)
    name: str = "synthetic"

    @property
    def n_docs(self) -> int:
        return len(self.documents)

    def query_kinds(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for q in self.queries:
            counts[q.kind] = counts.get(q.kind, 0) + 1
        return counts


def _world(adj: str) -> tuple[list[dict], list[EvalQuery]]:
    e = {role: f"{adj}_{role}" for role in ROLES}
    docs: list[dict] = [
        {"_id": e["shield"], "content": _CONTENT["shield"].format(adj=adj),
         "edges": [("prevents", e["storm"])]},
        {"_id": e["storm"], "content": _CONTENT["storm"].format(adj=adj),
         "edges": [("causes", e["ruin"])]},
        {"_id": e["ruin"], "content": _CONTENT["ruin"].format(adj=adj)},
        {"_id": e["spark"], "content": _CONTENT["spark"].format(adj=adj),
         "edges": [("causes", e["storm"])]},
        {"_id": e["cure"], "content": _CONTENT["cure"].format(adj=adj),
         "edges": [("prevents", e["ruin"])]},
        {"_id": e["calm"], "content": _CONTENT["calm"].format(adj=adj),
         "edges": [("contradicts", e["storm"])]},
    ]
    queries = [
        EvalQuery(
            qid=f"{adj}-sh", kind="single_hop_inverse",
            text=f"what prevents {e['storm']}?",
            answers=(e["shield"],), anchor=e["storm"],
        ),
        EvalQuery(
            qid=f"{adj}-fw", kind="single_hop",
            text=f"what does {e['shield']} prevent?",
            answers=(e["storm"],), anchor=e["shield"],
        ),
        EvalQuery(
            qid=f"{adj}-mh", kind="multi_hop",
            text=f"is {e['shield']} connected to {e['ruin']}?",
            answers=(e["ruin"],), anchor=e["shield"], target=e["ruin"],
            gold_path=("prevents", "causes"),
        ),
        EvalQuery(
            qid=f"{adj}-ct", kind="contradiction",
            text=f"what contradicts {e['storm']}?",
            answers=(e["calm"],), anchor=e["storm"],
        ),
    ]
    return docs, queries


def synthetic_corpus(seed: int = 0, n_worlds: int = 40) -> Corpus:
    """Build a deterministic synthetic relational corpus.

    Args:
        seed: RNG seed; controls which adjectives are used and query order.
        n_worlds: number of independent worlds (<= 80). Each world contributes
            6 documents and 4 queries.
    """
    if n_worlds > len(ADJECTIVES):
        raise ValueError(f"n_worlds must be <= {len(ADJECTIVES)}")
    rng = random.Random(seed)
    adjs = rng.sample(ADJECTIVES, n_worlds)
    corpus = Corpus(name=f"synthetic-s{seed}-w{n_worlds}")
    for adj in adjs:
        docs, queries = _world(adj)
        corpus.documents.extend(docs)
        corpus.queries.extend(queries)
    rng.shuffle(corpus.queries)
    return corpus
