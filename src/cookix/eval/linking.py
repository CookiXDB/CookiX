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

    def _scored(self, question: str) -> list[tuple[float, str]]:
        qnorm = normalise_entity(question)
        qtoks = set(_TOKEN.findall(qnorm))
        if not qtoks:
            return []
        padded_q = f" {qnorm} "
        scored: list[tuple[float, str]] = []
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
            scored.append((score, node))
        scored.sort(reverse=True)
        return scored

    def link(self, question: str) -> str | None:
        scored = self._scored(question)
        return scored[0][1] if scored else None

    def rank(self, question: str, k: int = 20) -> list[str]:
        """Top-``k`` candidate entity keys for the question (best first)."""
        return [n for _, n in self._scored(question)[:k]]


class LLMEntityLinker:
    """LLM-assisted linker: shortlist with the surface linker, let Claude pick.

    Requires ``pip install "cookix[llm]"`` and an ``ANTHROPIC_API_KEY`` (or an
    injected ``client`` for testing). The surface linker narrows thousands of
    entities to a small shortlist so token cost is bounded; the model then chooses
    the single head entity the question is *about*. This is the lever expected to
    push link accuracy past the ~70% needed to flip the end-to-end result.
    """

    name = "llm"

    def __init__(
        self,
        nodes: Iterable[str],
        model: str = "claude-sonnet-4-6",
        api_key: str | None = None,
        shortlist: int = 20,
        client: object | None = None,
    ) -> None:
        nodes = list(nodes)
        self._surface = SurfaceFormLinker(nodes)
        self._node_set = set(nodes)
        self._model = model
        self._shortlist = shortlist
        if client is not None:
            self._client = client            # injectable: tests pass a fake client
        else:  # pragma: no cover - needs the optional SDK + network
            try:
                import anthropic
            except ImportError as exc:
                raise ImportError(
                    'LLMEntityLinker requires the Anthropic SDK. '
                    'Install with: pip install "cookix[llm]"'
                ) from exc
            self._client = (
                anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
            )

    def link(self, question: str) -> str | None:
        candidates = self._surface.rank(question, self._shortlist)
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]            # no need to spend a call on a sure thing
        numbered = "\n".join(f"{i}. {c}" for i, c in enumerate(candidates))
        prompt = (
            "A question reasons from a head entity to an answer. From the candidate "
            "entity names below, return ONLY the single candidate the question is "
            "primarily ABOUT (its starting point) — copy it exactly, nothing else.\n\n"
            f"Question: {question}\n\nCandidates:\n{numbered}"
        )
        msg = self._client.messages.create(
            model=self._model, max_tokens=64,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()  # type: ignore[union-attr]
        return self._match(raw, candidates)

    def _match(self, raw: str, candidates: list[str]) -> str | None:
        norm = normalise_entity(raw)
        if norm in self._node_set:
            return norm
        for c in candidates:                # tolerate numbering / extra words
            if c == norm or c in norm or norm in c:
                return c
        return candidates[0]                # fall back to the top surface candidate


def make_linker(strategy: str, nodes: Iterable[str], entity_text: dict[str, str]):
    """Factory: ``"surface"`` (default), ``"bm25"`` (baseline), or ``"llm"``.

    ``"llm"`` needs the ``cookix[llm]`` extra and an ``ANTHROPIC_API_KEY``.
    """
    nodes = list(nodes)
    if strategy in ("bm25", "bm25-context"):
        return ContextBM25Linker(nodes, entity_text)
    if strategy == "llm":
        return LLMEntityLinker(nodes)
    return SurfaceFormLinker(nodes)
