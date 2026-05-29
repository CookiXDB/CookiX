from __future__ import annotations

from cookix.eval.datasets import normalise_entity
from cookix.eval.linking import LLMEntityLinker, SurfaceFormLinker, make_linker


class _FakeClient:
    """Stand-in Anthropic client: returns whatever text we program, records the prompt."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompt = None
        self.messages = self

    def create(self, model, max_tokens, messages):  # noqa: D401, ANN001
        self.prompt = messages[0]["content"]
        text = self.reply
        return type("Msg", (), {"content": [type("C", (), {"text": text})()]})()


def test_surface_linker_finds_literal_mention():
    nodes = [
        normalise_entity("Polish-Russian War (film)"),
        normalise_entity("Xawery Zulawski"),
        normalise_entity("Andrzej Zulawski"),
        normalise_entity("Boraq Airlines"),
    ]
    linker = SurfaceFormLinker(nodes)
    q = "Who is the father of the director of film Polish-Russian War (Film)?"
    assert linker.link(q) == normalise_entity("Polish-Russian War (film)")


def test_surface_linker_prefers_more_specific_name():
    nodes = [normalise_entity("War"), normalise_entity("Polish-Russian War (film)")]
    linker = SurfaceFormLinker(nodes)
    # Both share "war", but the full multi-token mention should win.
    assert linker.link("about the Polish-Russian War film") \
        == normalise_entity("Polish-Russian War (film)")


def test_surface_linker_returns_none_when_no_overlap():
    linker = SurfaceFormLinker([normalise_entity("Boraq Airlines")])
    assert linker.link("an unrelated question about cooking") is None


def test_make_linker_dispatch():
    nodes = [normalise_entity("Kabul")]
    assert make_linker("surface", nodes, {}).name == "surface"
    assert make_linker("bm25", nodes, {"kabul": "Kabul is in Afghanistan"}).name \
        == "bm25-context"


def test_llm_linker_picks_from_shortlist_with_fake_client():
    # Two nodes share the token "russian", so both are shortlisted -> the LLM is
    # actually consulted (a single candidate would short-circuit without a call).
    nodes = [
        normalise_entity("Polish-Russian War (film)"),
        normalise_entity("Russian Cinema"),
        normalise_entity("Andrzej Zulawski"),
    ]
    fake = _FakeClient(reply=normalise_entity("Polish-Russian War (film)"))
    linker = LLMEntityLinker(nodes, client=fake)
    out = linker.link("Who is the father of the director of film Polish-Russian War?")
    assert out == normalise_entity("Polish-Russian War (film)")
    assert fake.prompt is not None and "polish russian war film" in fake.prompt


def test_llm_linker_tolerates_numbered_or_noisy_reply():
    nodes = [normalise_entity("Boraq Airlines"), normalise_entity("Kabul")]
    fake = _FakeClient(reply="The answer is: Boraq Airlines.")
    linker = LLMEntityLinker(nodes, client=fake)
    assert linker.link("Where is Boraq Airlines headquartered?") \
        == normalise_entity("Boraq Airlines")
