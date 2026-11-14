"""The landing profile (schema-dist ``profiles/landing.md``): every conformance case in
``codegen/schema-dist/profiles/landing.fixture.json``, vendored with the distribution, each its own test, through
``landing_of``, and the profile's invariants on every answer. The npm SDK's ``landingOf`` runs the same cases.
``OW_LANDING_FIXTURE`` points it at another copy of the fixture (a staged branch before the serial)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import landing_of, world_graph

REPO = Path(__file__).resolve().parent.parent
FIXTURE = Path(
    os.environ.get("OW_LANDING_FIXTURE") or REPO / "codegen" / "schema-dist" / "profiles" / "landing.fixture.json"
)


def load_cases() -> list[dict[str, Any]]:
    assert FIXTURE.is_file(), f"no landing fixture at {FIXTURE}"
    doc: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = doc["cases"]
    return cases


CASES = load_cases()


def test_the_fixture_holds_serial_104s_33_cases() -> None:
    assert len(CASES) == 33, f"the fixture holds {len(CASES)} cases, serial 104 has 33"


def _dump(v: Any) -> str:
    # The npm side compares JSON.stringify's bytes; compact separators and no ASCII escaping match them.
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_fixture_case(case: dict[str, Any]) -> None:
    opts = case.get("options") or {}
    want = case["want"]
    if "refused" in want:
        with pytest.raises((TypeError, ValueError)) as err:
            landing_of(case["graph"], **opts)
        assert f"'{want['refused']}'" in str(err.value) or str(err.value).startswith(
            f"landing_of: {want['refused']} is"
        )
        return
    answer: dict[str, Any] = dict(landing_of(case["graph"], **opts))
    got = answer if case.get("whole") else {k: answer[k] for k in want}
    assert _dump(got) == _dump(want)


def test_every_answer_holds_five_keys_in_order_and_is_stable() -> None:
    for c in CASES:
        if "refused" in c["want"]:
            continue
        a = landing_of(c["graph"], **(c.get("options") or {}))
        assert list(a) == ["mode", "size", "clusters", "unclustered", "gaps"]
        assert _dump(landing_of(c["graph"], **(c.get("options") or {}))) == _dump(a)


def test_every_node_has_one_home_and_each_cluster_starts_at_its_head() -> None:
    for c in CASES:
        if "refused" in c["want"]:
            continue
        a = landing_of(c["graph"], **(c.get("options") or {}))
        ids = [m["id"] for k in a["clusters"] for m in k["members"]] + [u["id"] for u in a["unclustered"]]
        assert sorted(ids) == sorted(n["id"] for n in c["graph"]["nodes"]), c["name"]
        for k in a["clusters"]:
            assert k["members"][0]["id"] == k["head"] and k["members"][0]["hops"] == 0, c["name"]


def test_refused_before_reading() -> None:
    with pytest.raises(TypeError):
        landing_of(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        landing_of({"nodes": []})
    with pytest.raises(ValueError):
        landing_of({"nodes": [], "edges": []}, heads=True)


def test_a_list_naming_one_target_twice_reads_degree_1_and_two_near_orphans() -> None:
    """(since serial 128) Each element once: the landing reader folds nothing itself; the graph ``world_graph``
    answers holds one edge for the repeat, so both ends read degree 1 and are near orphans. A graph handed in with
    two edges still reads them as two."""
    world = {
        "elements": [
            {"id": "ev", "type": "event", "name": "Feast", "characters": ["mara", "mara"]},
            {"id": "mara", "type": "character", "name": "Mara"},
        ]
    }
    a = landing_of(world_graph(world, {"rung": "owner"}))
    assert a["clusters"] == [
        {"head": "mara", "members": [{"id": "mara", "hops": 0, "degree": 1}, {"id": "ev", "hops": 1, "degree": 1}]}
    ]
    assert a["gaps"] == [
        {"kind": "near_orphan", "id": "ev"},
        {"kind": "near_orphan", "id": "mara"},
        {"kind": "no_place", "id": "mara"},
    ]
    two = {
        "nodes": [{"id": "ev", "type": "event"}, {"id": "mara", "type": "character"}],
        "edges": [
            {"source": "ev", "field": "characters", "target": "mara", "index": 0},
            {"source": "ev", "field": "characters", "target": "mara", "index": 1},
        ],
    }
    assert [m["degree"] for m in landing_of(two)["clusters"][0]["members"]] == [2, 2]
