"""trail-by-place, a layout method: the npm SDK's shared fixture (``tests/fixtures/layout/trail-by-place.json``, the
same bytes, sha256 held here and there), its parity case and every small case compared as serialised text, then the
method's own rules on its own answer, a re-run from the recipe, and the refusals."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import TRAIL_TIERS, map_space, trail_by_place

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "layout" / "trail-by-place.json"
FIXTURE_SHA = "da0c565f6a12debd"
BYTES = FIXTURE.read_bytes()
FX: dict[str, Any] = json.loads(BYTES.decode("utf-8"))


def dumps(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def test_the_fixture_is_the_one_both_packages_hold() -> None:
    assert hashlib.sha256(BYTES).hexdigest()[:16] == FIXTURE_SHA


def test_blood_meridian_pin_for_pin_every_key() -> None:
    got = trail_by_place(copy.deepcopy(FX["input"]))
    assert got["map"] == FX["want"]["map"]
    assert dumps(got["pins"]) == dumps(FX["want"]["pins"])
    assert got["route"] == FX["want"]["route"]


@pytest.mark.parametrize("case", FX["cases"], ids=[c["name"] for c in FX["cases"]])
def test_case(case: dict[str, Any]) -> None:
    if "refuse" in case:
        with pytest.raises(TypeError) as e:
            trail_by_place(copy.deepcopy(case["input"]))
        assert str(e.value) == f"trail_by_place: {case['refuse']}"
        return
    got: dict[str, Any] = dict(trail_by_place(copy.deepcopy(case["input"])))
    del got["recipe"]
    assert dumps(got) == dumps(case["want"])


def test_the_default_floors_are_the_ones_the_fixture_names() -> None:
    assert [dict(t) for t in TRAIL_TIERS] == FX["input"]["tiers"]
    rest = {k: v for k, v in copy.deepcopy(FX["input"]).items() if k != "tiers"}
    assert dumps(trail_by_place(rest)["pins"]) == dumps(FX["want"]["pins"])


def test_the_recipe_runs_the_layout_again() -> None:
    first = trail_by_place(copy.deepcopy(FX["input"]))
    inp = copy.deepcopy(FX["input"])
    again = trail_by_place(
        {
            **copy.deepcopy(first["recipe"]["settings"]),
            "places": inp["places"],
            "hangers": inp["hangers"],
            "hero": inp["hero"],
        }
    )
    assert first["recipe"]["method"] == "trail-by-place"
    assert dumps(again) == dumps(first)


def test_the_order_hangers_come_in_does_not_move_a_point() -> None:
    inp = copy.deepcopy(FX["input"])
    inp["hangers"].reverse()
    assert dumps(trail_by_place(inp)["pins"]) == dumps(FX["want"]["pins"])


def test_the_methods_rules_hold_on_its_answer() -> None:
    got = trail_by_place(copy.deepcopy(FX["input"]))
    m = got["map"]
    points: set[tuple[int, int, int]] = set()
    for p in got["pins"]:
        for k, hi in (("x", m["width"]), ("y", m["height"]), ("z", m["depth"])):
            v = p[k]  # type: ignore[literal-required]
            assert isinstance(v, int) and 0 <= v <= hi, (p["name"], k, v)
        key = (p["x"], p["y"], p["z"])
        assert key not in points, p["name"]
        points.add(key)
    place_ids = {q["id"] for q in FX["input"]["places"]}
    place_xy = {(p["x"], p["y"]) for p in got["pins"] if p["element_id"] in place_ids}
    for p in got["pins"]:
        if p["element_id"] not in place_ids:
            assert (p["x"], p["y"]) not in place_xy, p["name"]
    hero = next(p for p in got["pins"] if p["element_id"] == FX["input"]["hero"]["id"])
    assert "; 1 of " in hero["by"] and hero["by"].endswith(" on the spiral round it")
    map_id = "01a00000-0000-7000-8000-00000000000a"
    rows: list[dict[str, Any]] = [
        {"id": map_id, "type": "map", "name": "layout", "width": m["width"], "height": m["height"], "depth": m["depth"]}
    ]
    for i, p in enumerate(got["pins"]):
        rows.append(
            {
                "id": f"01a00000-0000-7000-8000-{i:012d}",
                "type": "pin",
                "name": p["name"],
                "map": map_id,
                "element_type": p["element_type"],
                "element_id": p["element_id"],
                "x": p["x"],
                "y": p["y"],
                "z": p["z"],
            }
        )
    read = {q["element_id"]: (q["x"], q["y"], q["z"]) for q in map_space(rows)["pins"]}
    for p in got["pins"]:
        assert read[p["element_id"]] == (p["x"], p["y"], p["z"]), p["name"]


def _places_with(d: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [q for q in d["places"] if key in q]


REFUSALS: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
    ("ground key", lambda i: i["ground"].update(widht=1), r"ground: unknown key 'widht'"),
    ("top key", lambda i: i.update(spirall={}), r"trail_by_place: unknown key 'spirall'"),
    ("place key", lambda i: i["places"][1].update(pinn=[0, 0]), r"place 1: unknown key 'pinn'"),
    ("hanger key", lambda i: i["hangers"][0].update(where="x"), r"hanger 0: unknown key 'where'"),
    ("two rules", lambda i: i["places"][1].update(parent=i["places"][0]["id"]), r"it has pin, parent"),
    ("no rule", lambda i: _places_with(i, "between")[0].pop("between"), r"it has none"),
    (
        "between an unpinned place",
        lambda i: _places_with(i, "between")[0].update(
            between=[_places_with(i, "between")[0]["between"][0], _places_with(i, "parent")[0]["id"]]
        ),
        r"which has no pin",
    ),
    (
        "at nowhere",
        lambda i: i["hangers"][0].update(at=["nowhere"]),
        r"at names nowhere, which is not one of the places",
    ),
    ("no floor", lambda i: i["hangers"][0].update(type="starship"), r"no tier holds the kind 'starship'"),
    ("id twice", lambda i: i["hangers"].append(copy.deepcopy(i["hangers"][0])), r"is given twice"),
    ("hero twice", lambda i: i["hangers"].append(copy.deepcopy(i["hero"])), r"is given twice"),
    ("depth", lambda i: i.update(depth=0), r"depth is a whole number above 0"),
    ("spiral", lambda i: i["spiral"].update(r0=0), r"spiral is"),
    ("pin", lambda i: i["places"][1].update(pin=[1, "x"]), r"pin is \[x, y\]"),
]


@pytest.mark.parametrize("label,mutate,pattern", REFUSALS, ids=[r[0] for r in REFUSALS])
def test_an_input_it_cannot_place_is_refused(
    label: str, mutate: Callable[[dict[str, Any]], None], pattern: str
) -> None:
    inp = copy.deepcopy(FX["input"])
    mutate(inp)
    with pytest.raises(TypeError, match=pattern):
        trail_by_place(inp)


def test_a_ring_of_parents_that_never_lands_is_refused() -> None:
    inp = copy.deepcopy(FX["input"])
    a, b = _places_with(inp, "parent")
    a["parent"], b["parent"] = b["id"], a["id"]
    with pytest.raises(TypeError, match="never reaches a placed place"):
        trail_by_place(inp)
