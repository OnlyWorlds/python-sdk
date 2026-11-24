"""``pins_known_to``: which of a map's Pins one reader knows. The shared cases
(``tests/fixtures/pins-known-to.cases.json``, the same bytes as the npm SDK's
``test/fixtures/pins-known-to.cases.json``; both suites hold its sha256, every want written by hand in the SDK's
generator): the whole answer of each case, key order included, and each refusal; then what the cases cannot hold:
the inputs left as they were, a tuple, and the answer beside ``map_space``'s."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import map_space, pins_known_to

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "pins-known-to.cases.json"
FIXTURE_SHA256 = "80f66dba8aa1a009770bdcffbf457ec84b78f7e4270a2fb9cf8614a4b76e39f6"


def _data() -> dict[str, Any]:
    """The file parsed afresh: a test that checks the inputs were not written to reads its own copy."""
    data: dict[str, Any] = json.loads(FIXTURE.read_bytes())
    return data


def _text(value: Any) -> str:
    """JSON text holds the key order and every value: two answers are the same exactly when their texts are."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def test_the_cases_file_is_the_pinned_bytes() -> None:
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA256
    data = _data()
    assert data["version"] == 1
    assert len(data["cases"]) == 31
    assert len(data["refusals"]) == 8


def test_every_shared_case_the_whole_answer_key_order_included() -> None:
    wrong = []
    for case in _data()["cases"]:
        got, want = _text(pins_known_to(case["pins"], case["served"])), _text(case["want"])
        if got != want:
            wrong.append(f"{case['name']}\n    want {want}\n    got  {got}")
    assert not wrong, f"{len(wrong)} case(s) disagree:\n  " + "\n  ".join(wrong)


def test_every_shared_refusal_a_type_error_that_names_the_argument_and_no_other() -> None:
    wrong = []
    for refusal in _data()["refusals"]:
        other = "served" if refusal["refuses"] == "pins" else "pins"
        try:
            pins_known_to(refusal["pins"], refusal["served"])
        except TypeError as error:
            # "is a list": the interpreter's own "object is not iterable" is not this refusal.
            if f"{refusal['refuses']} is a list" not in str(error) or f"{other} is a list" in str(error):
                wrong.append(f"{refusal['name']}: {error!s} does not name {refusal['refuses']} alone")
        except Exception as error:
            wrong.append(f"{refusal['name']}: raised {type(error).__name__}")
        else:
            wrong.append(f"{refusal['name']}: answered")
    assert not wrong, f"{len(wrong)} refusal(s) disagree:\n  " + "\n  ".join(wrong)


@pytest.mark.parametrize("value", [None, {"type": "pin"}, "pin", 7, iter([]), {"p1"}])
def test_only_a_list_or_a_tuple_is_taken(value: Any) -> None:
    with pytest.raises(TypeError, match="pins is a list"):
        pins_known_to(value, [])
    with pytest.raises(TypeError, match="served is a list"):
        pins_known_to([], value)


def test_a_tuple_reads_as_a_list() -> None:
    for case in _data()["cases"]:
        assert _text(pins_known_to(tuple(case["pins"]), tuple(case["served"]))) == _text(case["want"]), case["name"]


def test_the_inputs_are_left_as_they_were() -> None:
    before, run = _data()["cases"], _data()["cases"]
    for case in run:
        pins_known_to(case["pins"], case["served"])
    for was, now in zip(before, run, strict=True):
        assert _text(now["pins"]) == _text(was["pins"]), f"{was['name']}: pins"
        assert _text(now["served"]) == _text(was["served"]), f"{was['name']}: served"


def test_two_calls_answer_two_objects() -> None:
    pins = [{"type": "pin", "id": "p1", "map": "m1", "element_type": "location", "element_id": "l1"}]
    served = [{"type": "location", "id": "l1"}]
    a, b = pins_known_to(pins, served), pins_known_to(pins, served)
    assert a is not b
    assert a["known"] is not b["known"]
    assert a["known"][0] is not b["known"][0]
    assert a["out"] is not b["out"]


def test_known_of_is_a_stub_only_when_it_is_exactly_true() -> None:
    """Python's own trap, which the shared case's ``1`` holds only by identity: ``1 == True``."""
    pins = [{"type": "pin", "id": "p1", "element_type": "location", "element_id": "l1"}]
    assert pins_known_to(pins, [{"type": "location", "id": "l1", "known_of": 1}])["known"][0]["how"] == "whole"
    assert pins_known_to(pins, [{"type": "location", "id": "l1", "known_of": 1.0}])["known"][0]["how"] == "whole"
    assert pins_known_to(pins, [{"type": "location", "id": "l1", "known_of": True}])["known"][0]["how"] == "known_of"


def test_beside_map_space_a_drawing_keeps_the_pins_both_name() -> None:
    world: list[dict[str, Any]] = [
        {"type": "map", "id": "m1", "width": 100, "height": 100},
        {"type": "pin", "id": "p1", "map": "m1", "x": 1, "y": 2, "element_type": "location", "element_id": "l1"},
        {"type": "pin", "id": "p2", "map": "m1", "x": 3, "y": 4, "element_type": "location", "element_id": "l2"},
        {"type": "pin", "id": "p3", "map": "m1", "element_type": "location", "element_id": "l1"},  # no point
        {"type": "pin", "id": "p4", "map": "gone", "x": 5, "y": 6, "element_type": "location", "element_id": "l1"},
        {"type": "location", "id": "l1"},
        {"type": "location", "id": "l2"},
    ]
    served = [{"type": "location", "id": "l1", "known_of": True}]
    answer = pins_known_to(world, served)
    assert [k["pin"] for k in answer["known"]] == ["p1", "p3", "p4"]
    assert answer["unknown"] == 1
    how = {k["pin"]: k["how"] for k in answer["known"]}
    drawn = [p for p in map_space(world)["pins"] if p["pin"] in how]
    assert [(p["pin"], p["x"], p["y"], how[p["pin"]]) for p in drawn] == [("p1", 1, 2, "known_of")]
