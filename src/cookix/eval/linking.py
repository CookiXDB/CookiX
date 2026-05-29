"""Entity linking: pick the question's head entity (drop the oracle anchor).

The 2Wiki engine result is strong *given* the right anchor. End-to-end, something
must choose that anchor from the raw question — that is **entity linking**, and it
is the open-domain bottleneck. This module provides two linkers so the cost of
linking can be measured honestly:

* :class:`ContextBM25Linker` — the naive baseline: rank entities by BM25 over
  their *paragraph text* and take the top one. It conflates "mentioned in the
  question" with "topically similar", so it links the gold head entity only about
  half the time.
* :class:`SurfaceFormLinker` — the right signal: match entity **names** against
  the **question string**. An entity whose name tokens all appear in the question
  (a literal mention) wins, weighted by token rarity (IDF) and a contiguous-
  substring bonus, with ties broken toward the most specific (longest) name.

Both expose ``link(question) -> entity_key | None`` over a fixed node set.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable

from .datasets import BM25Retriever, normalise_entity

_TOKEN = re.compile(r"[a-z0-9]+")


class ContextBM25Linker:
    """Baseline linker: BM25 over entity paragraph text, take the top hit."""

    name = "bm25-context"

    def __init__(self, nodes: Iterable[str], entity_text: dict[str, str]) -> None:
        self._nodes = set(nodes)
        self._bm25 = BM25Retriever({n: entity_text.get(n, n) for n in self._nodes})

    def link(self, question: str) -> str | None:
        hits = self._bm25.retrieve_ids(question, k=1)
        return hits[0].object_id if hits and hits[0].object_id in self._nodes else None


class SurfaceFormLinker:
    """Match entity *names* against the *question* — the signal linking needs.

    Scores each entity by the IDF-weighted overlap between its name tokens and the
    question's tokens; a full mention (every name token present) and a contiguous
    substring match are boosted, and more-specific (longer) names win ties. This
    is a deliberately simple, dependency-free linker — the point is to show how
    much of the oracle gap a *correct signal* recovers before reaching for an LLM.
    """

    name = "surface"

    def __init__(self, nodes: Iterable[str]) -> None:
        self._nodes = [n for n in dict.fromkeys(nodes)]  # de-dup, keep order
        self._toks = {n: set(_TOKEN.findall(n)) for n in self._nodes}
        df: Counter[str] = Counter()
        for toks in self._toks.values():
            df.update(toks)
        total = max(len(self._nodes), 1)
        self._idf = {w: math.log(total / (1 + d)) + 1.0 for w, d in df.items()}

    def link(self, question: str) -> str | None:
        qnorm = normalise_entity(question)
        qtoks = set(_TOKEN.findall(qnorm))
        if not qtoks:
            return None
        padded_q = f" {qnorm} "
        best: str | None = None
        best_score = 0.0
        for node in self._nodes:
            name_toks = self._toks[node]
            present = name_toks & qtoks
            if not present:
                continue
            score = sum(self._idf.get(w, 1.0) for w in present)
            if present == name_toks:               # every name token is in the question
                score *= 2.0
            if f" {node} " in padded_q:             # contiguous literal mention
                score *= 1.5
            score += 0.01 * len(present)            # nudge toward more-specific names
            if score > best_score:
                best_score, best = score, node
        return best


def make_linker(strategy: str, nodes: Iterable[str], entity_text: dict[str, str]):
    """Factory: ``"surface"`` (default, name-vs-question) or ``"bm25"`` (baseline)."""
    nodes = list(nodes)
    if strategy in ("bm25", "bm25-context"):
        return ContextBM25Linker(nodes, entity_text)
    return SurfaceFormLinker(nodes)
