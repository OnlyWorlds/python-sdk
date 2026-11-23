"""``name_finder``: a world's element names found in prose. The shared cases (``tests/fixtures/name-finder.cases.json``,
the same bytes as the npm SDK's ``test/fixtures/name-finder.cases.json``; both suites hold its sha256, every want
written by hand in the SDK's generator), their timed recipes, then what the cases cannot hold: the object answered,
purity and the refusals."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import NameFound, name_finder

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "name-finder.cases.json"
FIXTURE_SHA256 = "4c4d7d3b4480e4c20bab799972faf90c542b5b570c1b43f7882291444c31007a"
DATA: dict[str, Any] = json.loads(FIXTURE.read_bytes())
PYTHON_FACTOR = 5
"""The cases' ``underMs`` is the npm SDK's line, where the slowest recipe takes about a tenth of a second. Here the
slowest recipe's whole test took 0.76 s when this was written, so the line is five times ``underMs``: far above a
slow machine's run, and far below a search that is not linear, which takes minutes on these texts."""


def _names_of(element: dict[str, Any]) -> list[Any]:
    names = element.get("names")
    return names if isinstance(names, list) else [element.get("name")]


def _answer(case: dict[str, Any]) -> list[dict[str, Any]]:
    find = name_finder(case["elements"], case=case["case"], names=_names_of)
    return [{"at": f.start, "length": f.end - f.start, "id": f.element["id"]} for f in find(case["text"])]


def test_the_cases_file_is_the_pinned_bytes_the_ones_the_npm_sdk_runs() -> None:
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA256
    assert DATA["version"] == 1
    assert len(DATA["cases"]) >= 47


def test_every_shared_case() -> None:
    wrong = [
        f"{case['name']}\n    want {case['want']}\n    got  {got}"
        for case in DATA["cases"]
        if (got := _answer(case)) != case["want"]
    ]
    assert not wrong, f"{len(wrong)} case(s) disagree:\n  " + "\n  ".join(wrong)


def test_the_shared_cases_hold_answers_of_both_kinds() -> None:
    assert any(case["want"] for case in DATA["cases"])
    assert any(not case["want"] for case in DATA["cases"])
    for fold in ("exact", "folded"):
        assert any(case["case"] == fold and case["want"] for case in DATA["cases"]), fold


def _build(recipe: dict[str, Any]) -> tuple[list[dict[str, str]], str]:
    made = recipe["elements"]
    elements = [{"id": f"e{i}", "name": made["pattern"].replace("{i}", str(i))} for i in range(made["count"])]
    text = recipe["text"]
    if "repeat" in text:
        return elements, text["repeat"] * text["times"]
    return elements, "".join(text["cycle"].replace("{i}", str(i % text["count"])) for i in range(text["times"]))


@pytest.mark.parametrize("recipe", DATA["timed"], ids=lambda r: r["name"])
def test_linear_in_the_text_on_the_timed_recipes(recipe: dict[str, Any]) -> None:
    elements, text = _build(recipe)
    find = name_finder(elements, case="exact")
    start = time.perf_counter()
    found = find(text)
    ms = (time.perf_counter() - start) * 1000
    assert len(found) == recipe["count"]
    assert ms < DATA["underMs"] * PYTHON_FACTOR, f"{round(ms)} ms"


def test_the_timed_recipes_are_the_seven() -> None:
    assert len(DATA["timed"]) >= 7


def test_start_and_end_count_code_points_and_the_slice_is_the_name_as_written() -> None:
    dragon = chr(0x1F409)
    text = f"{dragon} Kira met {dragon}{dragon} KIRA."
    find = name_finder([{"id": "k", "name": "Kira"}], case="folded")
    assert [(f.start, f.end, text[f.start : f.end]) for f in find(text)] == [(2, 6, "Kira"), (14, 18, "KIRA")]


def test_element_is_the_object_passed_in_and_the_default_name_is_its_name() -> None:
    kira = {"id": "k", "name": "Kira", "type": "character", "description": "A watchman."}
    (found,) = name_finder([kira], case="exact")("Kira.")
    assert found == NameFound(0, 4, kira)
    assert found.element is kira
    assert name_finder(iter([kira]), case="exact")("Kira.")[0].element is kira


def test_nothing_given_is_changed_and_the_names_are_read_once() -> None:
    elements: list[dict[str, Any]] = [
        {"id": "k", "name": "  Kira  ", "aliases": ["The Watch"]},
        {"id": "g", "name": "Iron Gate"},
    ]
    before = json.dumps(elements, sort_keys=True)
    find = name_finder(elements, case="folded", names=lambda e: [e["name"], *e.get("aliases", [])])
    text = "the watch saw Kira at the IRON GATE"
    first = find(text)
    assert json.dumps(elements, sort_keys=True) == before
    assert [f.element["id"] for f in first] == ["k", "k", "g"]
    first.clear()
    assert len(find(text)) == 3
    elements.append({"id": "x", "name": "saw"})
    assert len(find(text)) == 3


def test_refusals_each_by_name() -> None:
    els = [{"id": "k", "name": "Kira"}]
    with pytest.raises(TypeError, match="case"):
        name_finder(els)  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="fold"):
        name_finder(els, case="exact", fold=True)  # type: ignore[call-arg]
    for bad in ("Exact", None, True, ""):
        with pytest.raises(TypeError, match="case is 'exact' or 'folded'"):
            name_finder(els, case=bad)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="names is a function"):
        name_finder(els, case="exact", names=["Kira"])  # type: ignore[arg-type]
    not_lists: list[Any] = [None, "Kira", {"id": "k", "name": "Kira"}, 7]
    for not_elements in not_lists:
        with pytest.raises(TypeError, match="elements is an iterable"):
            name_finder(not_elements, case="exact")
    for not_element in ({"name": "Kira"}, {"id": 7, "name": "Kira"}, {"id": "", "name": "Kira"}, None, "Kira"):
        with pytest.raises(TypeError, match="every element is a mapping with a string id"):
            name_finder([not_element], case="exact")  # type: ignore[type-var]
    for not_text in (None, 7, ["Kira"], b"Kira"):
        with pytest.raises(TypeError, match="text must be a string"):
            name_finder(els, case="exact")(not_text)  # type: ignore[arg-type]
