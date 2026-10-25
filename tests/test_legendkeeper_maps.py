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
import uuid
from pathlib import Path
from typing import Any

from onlyworlds import read_folder
from onlyworlds.legendkeeper import LEGENDKEEPER_NAMESPACE, RecordedSource, import_legendkeeper

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
    # the six preset calendars every project carries (no timeline here: none is made)
    out[f"{P}/calendars"] = json.loads((FIX / "api-calendars.json").read_text(encoding="utf-8"))["answer"]
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


def test_a_feature_of_another_type_is_named_not_dropped(tmp_path: Path) -> None:
    rec = recorded()
    extra = copy.deepcopy(rec["maps"][MAIN]["features"]["data"][0])
    extra.update(id="label001", type="label")
    rec["maps"][MAIN]["features"]["data"].append(extra)
    report = import_legendkeeper(RecordedSource(answers(rec)), PID, tmp_path / "w", plan_only=True)
    assert "1 map feature of type 'label' on 'Main': not read (only pins, regions and paths are)" in report.notes
    assert [(m.pins, m.zones) for m in report.maps if m.name.endswith("Main")] == [(16, 0)]


# --- regions and paths: Zones of Markers ---------------------------------------------------------
#
# The features below are made up in the shape LegendKeeper's API gave for the 344 regions and paths
# of a pushed map, read live on 2026-10-25: {id, name, uri, type, polygon | polyline, linkedResourceId,
# isSynced, inherited}, each point [y, x] in zoom-0 units, a polygon not closed (its last point is not
# its first). The Zone resource is what a push from OnlyWorlds writes: a page tagged Zone.

ZONE_RID, WIKI_RID, REALM_RID = "zone0001", "x9c50azb", "xc0y9nz3"
WIKI_POS = [-24.289565058479525, 55.5190058479532]  # the Wiki City pin's pos on Main


def feature(fid: str, kind: str, points: list[list[float]], uri: str | None = None, name: str = "") -> dict[str, Any]:
    key = "polygon" if kind == "region" else "polyline"
    f: dict[str, Any] = {"id": fid, "name": name, "type": kind, key: points, "isSynced": True}
    if uri is not None:
        f.update(uri=f"lk://resources/{uri}", linkedResourceId=uri, inherited={"name": name, "iconShape": "none"})
    return f


def with_zone_resource(rec: dict[str, Any], hidden: bool = False) -> dict[str, Any]:
    row: dict[str, Any] = {"id": ZONE_RID, "name": "The Ward", "parentId": REALM_RID, "tags": ["Zone"]}
    row.update(aliases=[], isHidden=hidden, documents=[])
    rec["resources"][ZONE_RID] = {"row": row, "full": {**row, "properties": []}}
    return rec


REGION = feature("reg1", "region", [WIKI_POS, [-30.0, 60.0], [-35.0, 50.0], [-28.0, 45.0]], ZONE_RID, "The Ward")
ROAD = feature("road1", "path", [[-10.0, 10.0], [-20.0, 20.0], [-30.0, 25.0]], WIKI_RID, "The Wiki road")
TRACK = feature("track1", "path", [[-1.0, 1.0], [-2.0, 2.0]])  # no name, no uri
SLIVER = feature("sliver", "region", [[-1.0, 1.0], [-2.0, 2.0]], name="Too thin")


def drawn(features: list[dict[str, Any]], hidden_zone: bool = False) -> dict[str, Any]:
    rec = with_zone_resource(recorded(), hidden=hidden_zone)
    rec["maps"][MAIN]["features"]["data"] += copy.deepcopy(features)
    return rec


def zid(*parts: str) -> str:
    return str(uuid.uuid5(LEGENDKEEPER_NAMESPACE, ":".join(("legendkeeper", PID, *parts))))


def of(out: Path, etype: str) -> list[dict[str, Any]]:
    return [e.body for e in read_folder(out).elements.values() if e.body["type"] == etype]


def test_regions_and_paths_become_zones_of_markers(tmp_path: Path) -> None:
    report = import_legendkeeper(RecordedSource(answers(drawn([REGION, ROAD, TRACK, SLIVER]))), PID, tmp_path / "w")
    zones = {z["name"]: z for z in of(tmp_path / "w", "zone")}
    markers = of(tmp_path / "w", "marker")
    main = maps_by_name(tmp_path / "w")["The Realm of Tutoria: Main"]
    # the region links a Zone of the project: its Markers attach to it, and it takes shape polygon
    ward = zones["The Ward"]
    assert ward["id"] == zid(ZONE_RID) and ward["shape"] == "polygon" and ward["x_legendkeeper_id"] == ZONE_RID
    on_ward = sorted((m for m in markers if m["zone"] == ward["id"]), key=lambda m: m["order"])
    assert [m["order"] for m in on_ward] == [0, 1, 2, 3] and all(m["map"] == main["id"] for m in on_ward)
    assert [m["x_legendkeeper_pos"] for m in on_ward] == REGION["polygon"]
    assert [m["name"] for m in on_ward] == [f"The Ward: point {k}" for k in (1, 2, 3, 4)]
    assert on_ward[0]["id"] == zid("marker", REALM_RID, MAIN, "reg1", "0")
    # one conversion: the region's first point is Wiki City's pin pos, and lands on the pin's pixel
    wiki_pin = pins_by_lk_id(tmp_path / "w")["daeydntx"]
    assert (on_ward[0]["x"], on_ward[0]["y"]) == (wiki_pin["x"], wiki_pin["y"]) == (3553, 5445)
    assert (on_ward[1]["x"], on_ward[1]["y"]) == (3840, 5080)  # 60 * 64, -30 * 64 + 7000
    # the path links an ordinary page: a new Zone, shape line, the page in x_legendkeeper_page
    road = zones["The Wiki road"]
    wiki = next(e.body for e in read_folder(tmp_path / "w").elements.values() if e.body["name"] == "Wiki City")
    assert road["id"] == zid("zone", REALM_RID, MAIN, "road1") and road["shape"] == "line"
    assert road["x_legendkeeper_page"] == wiki["id"] and road["x_legendkeeper_id"] == "road1"
    assert road["x_legendkeeper_feature"]["isSynced"] is True
    assert "zone" not in wiki and "zones" not in wiki  # the page's own links are left alone
    assert sorted(m["order"] for m in markers if m["zone"] == road["id"]) == [0, 1, 2]
    # no name and no uri: the placeholder; too few points: no Zone, a note
    track = zones["Untitled path (track1)"]
    assert track["shape"] == "line" and "x_legendkeeper_page" not in track
    assert "Too thin" not in zones
    thin = "region 'Too thin' (sliver) on 'The Realm of Tutoria: Main': 2 points, fewer than a region's 3"
    assert f"{thin}; no Zone, no Markers" in report.notes
    assert len(markers) == 4 + 3 + 2 and report.counts["marker"] == 9 and report.counts["zone"] == 3
    made = next(m for m in report.maps if m.name.endswith("Main"))
    assert (made.zones, made.zones_own, made.markers) == (3, 1, 9)
    text = report.render()
    assert "3 regions and paths read as Zones (1 on Zones of the project, 2 new) with 9 Markers" in text
    assert any(n.startswith("3 map regions and paths read as Zones (1 on Zones of the project") for n in report.notes)
    # the same project read again: the same ids
    import_legendkeeper(RecordedSource(answers(drawn([REGION, ROAD, TRACK, SLIVER]))), PID, tmp_path / "again")
    assert {e for e in read_folder(tmp_path / "w").elements} == {e for e in read_folder(tmp_path / "again").elements}


def test_a_second_feature_on_one_zone_and_map_makes_its_own_zone(tmp_path: Path) -> None:
    second = feature("reg2", "path", [[-5.0, 5.0], [-6.0, 6.0]], ZONE_RID, "The Ward's edge")
    report = import_legendkeeper(RecordedSource(answers(drawn([REGION, second]))), PID, tmp_path / "w")
    zones = {z["name"]: z for z in of(tmp_path / "w", "zone")}
    assert zones["The Ward"]["shape"] == "polygon"  # the first feature's; the second does not reshape it
    assert zones["The Ward's edge"]["x_legendkeeper_page"] == zones["The Ward"]["id"]
    assert any("another region or path already holds: a new Zone" in n for n in report.notes)


def test_hidden_regions_and_paths_follow_the_pins(tmp_path: Path) -> None:
    hidden_road = {**ROAD, "isHidden": True}
    report = import_legendkeeper(
        RecordedSource(answers(drawn([REGION, hidden_road], hidden_zone=True))), PID, tmp_path / "w"
    )
    zones = {z["name"]: z for z in of(tmp_path / "w", "zone")}
    markers = of(tmp_path / "w", "marker")
    road = zones["The Wiki road"]
    assert road.get("hidden") is True
    assert all(m.get("hidden") is True for m in markers if m["zone"] == road["id"])
    # a visible region on a hidden Zone: visible Markers and a note, as a visible pin on a hidden page
    ward = zones["The Ward"]
    assert ward.get("hidden") is True
    assert not any(m.get("hidden") for m in markers if m["zone"] == ward["id"])
    assert "'The Ward': a visible region on 'The Realm of Tutoria: Main' places the hidden 'The Ward'" in report.notes
    assert report.hidden.map_zones == 1
    # a hidden map hides every Zone it makes new and every Marker on it
    rec = drawn([REGION, ROAD])
    next(d for d in rec["resources"][REALM_RID]["full"]["documents"] if d["id"] == MAIN)["isHidden"] = True
    import_legendkeeper(RecordedSource(answers(rec)), PID, tmp_path / "h")
    assert all(m.get("hidden") is True for m in of(tmp_path / "h", "marker"))
    assert {z["name"]: z.get("hidden") for z in of(tmp_path / "h", "zone")} == {"The Ward": None, "The Wiki road": True}


def test_the_file_road_reads_regions_and_paths_beside_pins(tmp_path: Path) -> None:
    """The export file's shape for regions and paths is unwitnessed; this holds the door's choice,
    ``content.regions`` and ``content.paths`` beside ``content.pins``."""
    data = json.loads((FIX / "the-quay-world-3.json").read_text(encoding="utf-8"))
    doc = next(
        d
        for r in data["resources"]
        for d in r.get("documents") or []
        if d.get("type") == "map" and d.get("name") == "Main"
    )
    doc["content"]["paths"] = [{k: v for k, v in TRACK.items() if k != "type"}]
    path = tmp_path / "export.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    report = import_legendkeeper(path, out_dir=tmp_path / "w")
    assert [z["name"] for z in of(tmp_path / "w", "zone") if z.get("shape") == "line"] == ["Untitled path (track1)"]
    assert report.counts["marker"] == 56 + 2  # the board's frames' and the path's


def test_a_map_whose_features_do_not_answer_is_unread_and_named(tmp_path: Path) -> None:
    ans = answers()
    del ans[f"{P}/resources/xc0y9nz3/docs/{MAIN}/features"]
    report = import_legendkeeper(RecordedSource(ans), PID, tmp_path / "w", plan_only=True)
    assert any("'Main'" in u and "features" in u for u in report.unread)
    assert [(n.kind, n.document) for n in report.not_imported] == [("map", "Main")]
    assert any(n.startswith("1 map document whose map and pins could not be read") for n in report.notes)
