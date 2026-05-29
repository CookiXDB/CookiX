from __future__ import annotations

from cookix.eval.datasets import normalise_entity
from cookix.eval.linking import SurfaceFormLinker, make_linker


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
