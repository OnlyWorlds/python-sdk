"""most_linked_of: the most linked elements of each type, a draft reading beside the landing profile. Every case
of tests/fixtures/most-linked.fixture.json, the same file byte for byte as the npm SDK's
test/fixtures/most-linked.fixture.json (both suites hold its sha256), answers written by hand."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import most_linked_of, world_graph

REPO = Path(__file__).resolve().parent.parent
FILE = REPO / "tests" / "fixtures" / "most-linked.fixture.json"
SHA256 = "9a7b27d849cd1c268d86b754bcdb7954cb23b3ede85178023332d61e497489c4"
RAW = FILE.read_bytes()
DOC = json.loads(RAW.decode("utf-8"))


def _dump(value: object) -> str:
    # The SDK's JSON.stringify: no spaces, non-ASCII as written.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def test_the_fixture_is_the_shared_file() -> None:
    assert hashlib.sha256(RAW).hexdigest() == SHA256
    assert DOC["profile"] == "most-linked"
    assert len(DOC["cases"]) == 18


@pytest.mark.parametrize("case", DOC["cases"], ids=[c["name"] for c in DOC["cases"]])
def test_fixture_case(case: dict[str, Any]) -> None:
    if "refused" in case["want"]:
        with pytest.raises((TypeError, ValueError)) as err:
            most_linked_of(case["graph"], **case["options"])
        assert case["want"]["refused"] in str(err.value)
        return
    # Byte for byte, key order included.
    assert _dump(most_linked_of(case["graph"], **case["options"])) == _dump(case["want"])


def test_no_options_is_the_default() -> None:
    c = DOC["cases"][0]
    assert _dump(most_linked_of(c["graph"])) == _dump(c["want"])


def test_a_graph_that_is_not_one_is_refused() -> None:
    bads: list[Any] = [None, {"nodes": []}, {"nodes": [], "edges": None}]
    for bad in bads:
        with pytest.raises(TypeError):
            most_linked_of(bad)


def test_it_changes_nothing_in_the_graph() -> None:
    g = DOC["cases"][6]["graph"]
    before = copy.deepcopy(g)
    most_linked_of(g)
    assert g == before


def test_through_world_graph_a_hidden_element_and_map_space_are_not_counted() -> None:
    elements = [
        {"id": "c1", "type": "character", "name": "Ada", "friends": ["c2"]},
        {"id": "c2", "type": "character", "name": "Brin"},
        {"id": "sec", "type": "event", "name": "The Secret", "characters": ["c1", "c2"], "hidden": True},
        {"id": "m1", "type": "map", "name": "Chart"},
        {"id": "p1", "type": "pin", "name": "Pin", "map": "m1", "element_type": "character", "element_id": "c1"},
    ]
    got = most_linked_of(world_graph({"elements": elements}, {"rung": "owner"}))
    assert got == {
        "per_type": 3,
        "by_type": {"character": [{"id": "c1", "name": "Ada", "degree": 1}, {"id": "c2", "name": "Brin", "degree": 1}]},
    }
    # The control: a graph that brings the hidden element in counts it, so the case above can see it.
    shown = most_linked_of(world_graph({"elements": elements}, {"rung": "owner"}, hidden=True))
    assert shown["by_type"]["event"] == [{"id": "sec", "name": "The Secret", "degree": 2}]
    assert shown["by_type"]["character"][0]["degree"] == 2
