"""Maps through LegendKeeper's API, against the same maps from its export file.

``fixtures/legendkeeper/api-maps.json`` holds real answers of the LegendKeeper API v3, read on
2026-10-25 on a Pro project seeded with LegendKeeper's tutorial (no key; account ids replaced,
permissions emptied): two map documents (the tutorial's "Main" map, 10000 x 7000 with 16 pins, and
an empty "Map") with each one's document and features answers, the resources they sit on, and every
resource a pin links. Only the map documents are kept on each resource (the pages were not
recorded), so the walk below reads maps and nothing else.

``the-quay-world-3.json`` (the export file fixture) carries the same tutorial map, with the same
16 pin ids at the same positions, in another project: the resource ids differ, the pixels must not.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from onlyworlds import read_folder
from onlyworlds.legendkeeper import RecordedSource, import_legendkeeper

FIX = Path(__file__).resolve().parent / "fixtures" / "legendkeeper"
PID = "tutorial0"
P = f"/projects/{PID}"
MAIN, EMPTY = "zt44sv1p", "e8z1h19f"


def recorded() -> dict[str, Any]:
    rec: dict[str, Any] = json.loads((FIX / "api-maps.json").read_text(encoding="utf-8"))
    return rec


def answers(rec: dict[str, Any] | None = None) -> dict[str, Any]:
    rec = rec or recorded()
    rows = []
    out: dict[str, Any] = {P: {"id": PID, "name": "The Realm of Tutoria"}}
    for rid, r in rec["resources"].items():
        docs = [d for d in r["full"]["documents"] if d.get("type") == "map"]
        rows.append({**r["row"], "documents": [{k: d[k] for k in ("id", "name", "type")} for d in docs]})
        out[f"{P}/resources/{rid}"] = {**r["full"], "documents": docs}
    out[f"{P}/resources"] = {"data": rows, "hasMore": False, "nextCursor": None}
    for did, m in rec["maps"].items():
        base = f"{P}/resources/{m['resource']}/docs/{did}"
        out[base] = m["doc"]
        out[f"{base}/features"] = m["features"]
    return out


def pins_by_lk_id(out: Path) -> dict[str, dict[str, Any]]:
    els = read_folder(out).elements.values()
    return {e.body["x_legendkeeper_id"]: e.body for e in els if e.body["type"] == "pin"}


def maps_by_name(out: Path) -> dict[str, dict[str, Any]]:
    return {e.body["name"]: e.body for e in read_folder(out).elements.values() if e.body["type"] == "map"}


def test_the_api_makes_the_tutorial_map_and_its_pins(tmp_path: Path) -> None:
    report = import_legendkeeper(RecordedSource(answers()), PID, tmp_path / "w")
    assert report.unread == [] and report.not_imported == []
    made = {m.name: (m.width, m.height, m.pins, m.mapless, m.max_zoom) for m in report.maps}
    assert made == {
        "The Realm of Tutoria: Main": (10000, 7000, 16, False, 6),
        "Location: Map": (None, None, 0, True, None),
    }
    maps = maps_by_name(tmp_path / "w")
    main = maps["The Realm of Tutoria: Main"]
    assert (main["width"], main["height"]) == (10000, 7000)
    assert main["x_legendkeeper_bounds"] == {"min_x": 0, "max_x": 10000, "min_y": -7000, "max_y": 0}
    assert main["x_legendkeeper_map"]["tiles"].startswith("https://tiles.legendkeeper.com/")
    assert "image_url" not in main  # no url and no asset id on the tutorial's tiled map
    pins = pins_by_lk_id(tmp_path / "w")
    assert len(pins) == 16
    wiki = pins["daeydntx"]
    assert wiki["name"] == "Wiki City" and wiki["map"] == main["id"] and wiki["element_id"]
    assert all(p.get("element_id") for p in pins.values())  # every pin links a resource in the walk


def test_both_roads_put_the_same_pins_on_the_same_pixels(tmp_path: Path) -> None:
    a_report = import_legendkeeper(RecordedSource(answers()), PID, tmp_path / "api")
    f_report = import_legendkeeper(FIX / "the-quay-world-3.json", out_dir=tmp_path / "file")
    assert a_report.unread == [] and f_report.unread == []  # the file's maps carry their pins: no API read
    api, file = pins_by_lk_id(tmp_path / "api"), pins_by_lk_id(tmp_path / "file")
    shared = sorted(set(api) & set(file))
    assert len(shared) == 16
    assert [(api[i]["x"], api[i]["y"]) for i in shared] == [(file[i]["x"], file[i]["y"]) for i in shared]
    a_map = maps_by_name(tmp_path / "api")["The Realm of Tutoria: Main"]
    f_map = maps_by_name(tmp_path / "file")["The Realm of Tutoria: Main"]
    assert (a_map["width"], a_map["height"], a_map["x_legendkeeper_bounds"]) == (
        f_map["width"],
        f_map["height"],
        f_map["x_legendkeeper_bounds"],
    )


def test_a_feature_that_is_not_a_pin_is_named_not_dropped(tmp_path: Path) -> None:
    rec = recorded()
    extra = copy.deepcopy(rec["maps"][MAIN]["features"]["data"][0])
    extra.update(id="region01", type="region")
    rec["maps"][MAIN]["features"]["data"].append(extra)
    report = import_legendkeeper(RecordedSource(answers(rec)), PID, tmp_path / "w", plan_only=True)
    assert "1 map feature of type 'region' on 'Main': not read (only pins are)" in report.notes
    assert [m.pins for m in report.maps if m.name.endswith("Main")] == [16]


def test_a_map_whose_features_do_not_answer_is_unread_and_named(tmp_path: Path) -> None:
    ans = answers()
    del ans[f"{P}/resources/xc0y9nz3/docs/{MAIN}/features"]
    report = import_legendkeeper(RecordedSource(ans), PID, tmp_path / "w", plan_only=True)
    assert any("'Main'" in u and "features" in u for u in report.unread)
    assert [(n.kind, n.document) for n in report.not_imported] == [("map", "Main")]
    assert any(n.startswith("1 map document whose map and pins could not be read") for n in report.notes)
