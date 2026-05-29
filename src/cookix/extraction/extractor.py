"""Relation extraction and query intent parsing.

Ingestion quality is the *ceiling* on every multi-hop result: with per-edge
error rate delta, an h-hop answer is correct with probability ~(1-delta)^h, so
errors compound. This module therefore treats extraction as a first-class,
swappable component.

Two implementations are provided:

* :class:`RuleBasedExtractor` — dependency-free, deterministic, keyword-driven.
  Good for tests, demos and structured corpora; weak on free text.
* :class:`LLMExtractor` — uses an LLM for relation extraction and intent
  parsing. Far stronger on natural language; requires ``cookix[llm]`` and an
  API key.

Both produce :class:`Triple` objects (subject, relation, object) for ingestion
and :class:`Intent` for query parsing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from .. import relations


@dataclass
class Triple:
    subject: str
    relation: str
    object: str
    weight: float = 1.0


@dataclass
class Intent:
    """Parsed query intent: where to start, which relation(s), optional target."""

    anchor: str | None = None
    relation: str | None = None
    target: str | None = None
    relation_chain: list[str] = field(default_factory=list)


# Verb/keyword -> relation type. Order matters: earlier, more specific first.
_KEYWORD_MAP: list[tuple[str, str]] = [
    ("compatible", "compatible_with"),
    ("conflict", "contradicts"),
    ("contradict", "contradicts"),
    ("prevent", "prevents"),
    ("block", "prevents"),
    ("cause", "causes"),
    ("require", "requires"),
    ("depend", "requires"),
    ("part of", "part_of"),
    ("contains", "has_part"),
    ("kind of", "is_a"),
    ("type of", "is_a"),
    ("is a", "is_a"),
    ("conform", "conforms_to"),
    ("similar", "similar_to"),
    ("used in", "used_in"),
]


class Extractor(Protocol):
    def extract(self, text: str) -> list[Triple]: ...
    def parse_intent(self, query: str, known_ids: list[str]) -> Intent: ...


class RuleBasedExtractor:
    """Deterministic keyword extractor. No external dependencies."""

    def extract(self, text: str) -> list[Triple]:
        """Naive subject-verb-object extraction over sentences.

        Splits on relation keywords; treats the text before/after the keyword as
        subject/object. This is intentionally simple — for serious free-text
        ingestion use :class:`LLMExtractor`.
        """
        triples: list[Triple] = []
        for sentence in re.split(r"[.\n;]", text):
            lowered = sentence.lower()
            for keyword, relation in _KEYWORD_MAP:
                idx = lowered.find(keyword)
                if idx == -1:
                    continue
                end = idx + len(keyword)
                # Consume the rest of the matched word (so the stem "prevent"
                # also eats the trailing "s" in "prevents").
                while end < len(sentence) and sentence[end].isalpha():
                    end += 1
                subject = sentence[:idx].strip(" ,")
                obj = sentence[end:].strip(" ,")
                if subject and obj:
                    triples.append(Triple(subject=subject, relation=relation, object=obj))
                break
        return triples

    def parse_intent(self, query: str, known_ids: list[str]) -> Intent:
        """Best-effort mapping of a natural-language query to an Intent.

        Detects a relation keyword and matches known object ids that appear in
        the query (longest match first, so multi-word ids win). The first match
        becomes the anchor, the second (if any) the target.
        """
        lowered = query.lower()
        relation = None
        keyword_idx = -1
        for keyword, rel_name in _KEYWORD_MAP:
            idx = lowered.find(keyword)
            if idx != -1:
                relation = rel_name
                keyword_idx = idx
                break

        # Match known ids and remember where each appears, so we can order
        # anchor/target by their position in the query.
        positioned: list[tuple[int, str]] = []
        for obj_id in sorted(known_ids, key=len, reverse=True):
            pos = lowered.find(obj_id.lower())
            if pos != -1 and all(obj_id != m[1] for m in positioned):
                positioned.append((pos, obj_id))
        positioned.sort(key=lambda m: m[0])
        matches = [obj_id for _, obj_id in positioned]

        intent = Intent(relation=relation)
        if matches:
            intent.anchor = matches[0]
        if len(matches) > 1:
            intent.target = matches[1]

        # Single-entity query where the entity follows the relation verb means
        # the entity is the grammatical *object* ("what prevents rain?" -> rain
        # is what gets prevented). Resolve via the inverse relation so traversal
        # walks the stored edge backwards to find the subject.
        if relation and len(matches) == 1 and keyword_idx != -1 and positioned[0][0] > keyword_idx:
            inverse = relations.inverse_of(relation)
            if inverse is not None:
                relation = inverse
                intent.relation = inverse

        if relation:
            intent.relation_chain = [relation]
        return intent


class LLMExtractor:
    """LLM-backed extractor using the Anthropic API.

    Requires ``pip install "cookix[llm]"`` and an ``ANTHROPIC_API_KEY``. Falls
    back to a :class:`RuleBasedExtractor` for intent parsing structure so the
    output shape is identical regardless of backend.
    """

    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str | None = None) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - optional dep
            raise ImportError(
                'LLMExtractor requires the Anthropic SDK. Install with: pip install "cookix[llm]"'
            ) from exc
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self._model = model
        self._fallback = RuleBasedExtractor()

    def _vocabulary_prompt(self) -> str:
        return ", ".join(relations.vocabulary())

    def extract(self, text: str) -> list[Triple]:  # pragma: no cover - needs network
        prompt = (
            "Extract typed relational triples from the text. Use ONLY these "
            f"relation types: {self._vocabulary_prompt()}. Return a JSON array of "
            '{"subject","relation","object"} objects. Text:\n\n' + text
        )
        message = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        import json

        raw = message.content[0].text  # type: ignore[union-attr]
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return []
        return [
            Triple(subject=t["subject"], relation=t["relation"], object=t["object"])
            for t in json.loads(match.group(0))
            if relations.is_registered(t.get("relation", ""))
        ]

    def parse_intent(self, query: str, known_ids: list[str]) -> Intent:  # pragma: no cover
        # For structured anchor/target resolution we reuse the rule-based matcher
        # against known ids, which is reliable; the LLM mainly helps free text.
        return self._fallback.parse_intent(query, known_ids)
