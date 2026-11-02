"""The graph's fifth flag, ``reading_aids`` (schema-dist serial 104, staged before the serial: these cases are
written from the profile owner's sentence and give way to the fixture's own cases at the repin). The reading aids
(the charter, its guide, its domains, by the pair and the mark ``x_charter_of``) are out of an unlensed graph by
default, counted ``reading_aid``; the flag brings back exactly those, each marked ``reading_aid``, for any signed
reader; a public reader is refused by name, last in the refusal order; a flag never widens a lens. The npm SDK's
``test/graph-reading-aids.test.mjs`` holds the same cases."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from onlyworlds.graph import world_graph

W = "00000000-0000-4000-8000-000000000000"
WORLD: dict[str, Any] = {
    "elements": [
        {"id": "c1", "type": "title", "name": "Keeper", "laws": ["l1", "l2"]},
        {"id": "l1", "type": "law", "name": "The Charter", "supertype": "Charter", "x_charter_of": W},
        {"id": "l2", "type": "law", "name": "An old charter", "supertype": "Charter"},
    ]
}


class _Unread(list[Any]):
    """An elements list that fails the moment anything iterates it."""

    def __iter__(self) -> Iterator[Any]:
        raise AssertionError("read")


def test_without_the_flag_a_charter_is_out_counted_reading_aid() -> None:
    g = world_graph(WORLD, {"rung": "owner"})
    assert [n["id"] for n in g["nodes"]] == ["c1", "l2"]
    assert g["cut"] == {"reading_aid": 1}
    assert g["edges_cut"] == {"reading_aid": 1}


@pytest.mark.parametrize(
    "reader",
    [{"rung": "owner"}, {"rung": "contributor"}, {"rung": "guest", "character": "g1", "whole": ["c1", "l1", "l2"]}],
)
def test_reading_aids_brings_the_charter_back_marked(reader: dict[str, Any]) -> None:
    g = world_graph(WORLD, reader, reading_aids=True)
    by_id = {n["id"]: n for n in g["nodes"]}
    assert "l1" in by_id
    assert by_id["l1"].get("marks") == ["reading_aid"]
    assert by_id["l2"].get("marks") is None
    assert "reading_aid" not in g["cut"]
    assert "reading_aid" not in g["edges_cut"]
    if "c1" in by_id:
        assert any(e["source"] == "c1" and e["target"] == "l1" for e in g["edges"])


def test_reading_aids_false_reads_as_no_flag() -> None:
    assert world_graph(WORLD, {"rung": "owner"}, reading_aids=False) == world_graph(WORLD, {"rung": "owner"})


def test_a_public_reader_asking_reading_aids_is_refused_by_name_and_last_in_the_order() -> None:
    trap = {"elements": _Unread([{"id": "c1", "type": "character"}])}
    with pytest.raises(ValueError, match="public reader takes no flag; it asked reading_aids"):
        world_graph(trap, {"rung": "public"}, reading_aids=True)
    with pytest.raises(ValueError, match="it asked reading_aids"):
        world_graph(trap, {"rung": "owner", "as": {"rung": "public"}}, reading_aids=True)
    with pytest.raises(ValueError, match="it asked map_space"):
        world_graph(trap, {"rung": "public"}, map_space=True, reading_aids=True)
    with pytest.raises(ValueError, match="hidden is the owner's alone"):
        world_graph(trap, {"rung": "public"}, hidden=True, reading_aids=True)
    with pytest.raises(TypeError, match="reading_aids is a boolean"):
        world_graph({"elements": []}, {"rung": "owner"}, reading_aids="yes")  # type: ignore[arg-type]
    assert world_graph({"elements": []}, {"rung": "public"}, reading_aids=False)["nodes"] == []


def test_a_lens_that_names_the_pair_keeps_the_charter_marked_flag_or_none() -> None:
    lens = {
        "id": "n1",
        "type": "construct",
        "supertype": "Lens",
        "name": "Laws",
        "x_lens": {"types": ["title", "law/charter", "law"]},
    }
    w = {"elements": [*WORLD["elements"], lens]}
    for flag in (False, True):
        g = world_graph(w, {"rung": "owner"}, lens="n1", reading_aids=flag)
        assert [(n["id"], n.get("marks")) for n in g["nodes"]] == [("c1", None), ("l1", ["reading_aid"]), ("l2", None)]


def test_a_flag_never_widens_a_lens() -> None:
    lens = {"id": "n1", "type": "construct", "supertype": "Lens", "name": "Titles", "x_lens": {"types": ["title"]}}
    w = {"elements": [*WORLD["elements"], lens]}
    plain = world_graph(w, {"rung": "owner"}, lens="n1")
    flagged = world_graph(w, {"rung": "owner"}, lens="n1", reading_aids=True)
    assert flagged == plain
    assert not any(n["id"] == "l1" for n in flagged["nodes"])
