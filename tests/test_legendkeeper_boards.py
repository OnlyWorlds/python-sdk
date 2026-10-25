"""Boards: a LegendKeeper board document becomes a Map (supertype Board) with what its shapes make.

``the-quay-world-3.json`` (the export file fixture; its story is in ``test_legendkeeper_file.py``)
holds LegendKeeper's tutorial board, "Main" on the resource "Board Bastion": 243 tldraw records in
``content.shapesV2``, 154 shapes, 52 bindings, 35 assets, 1 page and 1 document. The shapes: text
36, arrow 26, geo 20, group 15, frame 14, image 13, element (page cards) 12, draw 11, note 4,
bookmark 3. No card in it sits at the top level or under a rotated parent, and none shows a board,
so those cases are built on a synthetic board below.

``fixtures/legendkeeper/api-board.json`` holds LegendKeeper API v3's answer for the same tutorial
board, read on 2026-10-25 on a Pro project seeded with the tutorial (``GET .../docs/{id}/board``,
key ``board``): the same 154 shapes and 52 bindings by id, equal record for record but for the 12
cards' ``resourceId``, which name that project's resources. The differential maps those ids to the
file's (through the same card shape; one bookmark asset's preview address names a resource too) and
finds the same elements.
"""

from __future__ import annotations

import copy
import json
import math
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import read_folder
from onlyworlds._jsonfmt import encode
from onlyworlds.legendkeeper import (
    LEGENDKEEPER_NAMESPACE,
    FileSource,
    ImportReport,
    SourceError,
    import_legendkeeper,
)
from onlyworlds.worldfile import RECORDS_MANIFEST

FIX = Path(__file__).resolve().parent / "fixtures" / "legendkeeper"
EXPORT3 = FIX / "the-quay-world-3.json"
HOME = "ajkxoqw3"  # the first top-level resource: keys the file road's ids
BASTION, MAIN = "lz0baol5", "cgljslnc"  # the board's resource and document
WIKI, TUTORIA, TUTORIA_MAP = "oqwc8iom", "cdtsrn5b", "awzvlq67"
CHARACTER, LOCATION = "nj687ndp", "v1cjkvea"  # the Character and Location templates: typed by their tags


def uid(*parts: str) -> str:
    return str(uuid.uuid5(LEGENDKEEPER_NAMESPACE, ":".join(("legendkeeper", HOME, *parts))))


BOARD_MAP = uid("board", BASTION, MAIN)


def export3() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(EXPORT3.read_text(encoding="utf-8"))
    return data


def resource(data: dict[str, Any], rid: str) -> dict[str, Any]:
    (r,) = (r for r in data["resources"] if r["id"] == rid)
    found: dict[str, Any] = r
    return found


def board_doc(data: dict[str, Any]) -> dict[str, Any]:
    (doc,) = (d for d in resource(data, BASTION)["documents"] if d["id"] == MAIN)
    found: dict[str, Any] = doc
    return found


RECORD = f"records/legendkeeper/boards/{MAIN}.json"


def record(out: Path, rel: str = RECORD) -> dict[str, Any]:
    found: dict[str, Any] = json.loads((out / rel).read_text(encoding="utf-8"))
    return found


def manifest(out: Path) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = json.loads((out / RECORDS_MANIFEST).read_text(encoding="utf-8"))
    return found


def ext_bytes(body: dict[str, Any]) -> int:
    """The size of a body's extension keys as JSON: what keel caps at 64 KB an element."""
    ext = {k: v for k, v in body.items() if k.startswith(("x_", "atlas_", "shadow_"))}
    return len(json.dumps(ext, ensure_ascii=False).encode("utf-8"))


def board_shapes() -> dict[str, dict[str, Any]]:
    return {
        r["val"]["id"]: r["val"] for r in board_doc(export3())["content"]["shapesV2"] if r["val"]["typeName"] == "shape"
    }


def write(tmp: Path, data: dict[str, Any], name: str = "variant.json") -> Path:
    path = tmp / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def run(tmp: Path, src: Any = EXPORT3, name: str = "world") -> tuple[Path, ImportReport]:
    out = tmp / name
    pid = HOME if isinstance(src, _ApiBoard) else None  # a Source is given the project id; a file keys its own
    return out, import_legendkeeper(src, pid, out_dir=out)


def bodies(out: Path) -> list[dict[str, Any]]:
    return [e.body for e in read_folder(out).elements.values()]


def from_board(out: Path, board: str = BOARD_MAP) -> dict[str, dict[str, Any]]:
    """Everything made from one board, by id: its Map and every element carrying its id."""
    return {b["id"]: b for b in bodies(out) if b["id"] == board or b.get("x_legendkeeper_board_map") == board}


def by_shape(out: Path, etype: str) -> dict[str, dict[str, Any]]:
    return {b["x_legendkeeper_id"]: b for b in from_board(out).values() if b["type"] == etype}


def records(*recs: dict[str, Any]) -> dict[str, Any]:
    """A board document's content as the export writes it: tldraw records in ``shapesV2``."""
    page = {"id": "page:page", "typeName": "page", "name": "Page 1", "index": "a1", "meta": {}}
    return {"shapes": [], "bindings": [], "shapesV2": [{"key": r["id"], "val": r} for r in (page, *recs)]}


def shape(sid: str, kind: str, x: float, y: float, rot: float = 0.0, parent: str = "page:page", **props: Any) -> Any:
    return {
        "id": f"shape:{sid}",
        "typeName": "shape",
        "type": kind,
        "x": x,
        "y": y,
        "rotation": rot,
        "parentId": parent if parent.startswith("page:") else f"shape:{parent}",
        "props": props,
    }


def bind(bid: str, arrow: str, to: str, terminal: str) -> dict[str, Any]:
    return {
        "id": f"binding:{bid}",
        "typeName": "binding",
        "type": "arrow",
        "fromId": f"shape:{arrow}",
        "toId": f"shape:{to}",
        "props": {"terminal": terminal},
    }


# --- the tutorial board, from the export file ------------------------------------


def test_the_tutorial_board_becomes_a_map_and_what_its_shapes_make(tmp_path: Path) -> None:
    out, report = run(tmp_path)
    (board,) = report.boards
    assert (board.name, board.resource, board.hidden, board.pages) == ("Board Bastion: Main", "Board Bastion", False, 1)
    assert board.made == {
        "card pins": 12,  # the 12 element shapes, each a Pin; none shows a board, so no child Maps
        "note pins": 39,  # 4 notes + 35 texts (36 texts, one of them empty), each a Narrative and its Pin
        "child maps": 0,
        "zones": 14,  # the 14 frames
        "markers": 56,  # 14 frames x 4 corners
        "relations": 2,  # the 2 arrows between the cards of two pages (Wiki City to Board Bastion, to the Realm)
        "narratives": 39,
    }
    # 26 arrows: 2 Relations, 22 with an end free or on neither a page card nor a frame (a geo, a bookmark, ...),
    # and 2 whose ends are one element: "resize" (the frame "Drag & Drop" to itself) and "resize to nest an
    # article!" (one Wiki City card to another)
    assert (board.loose_arrows, board.self_arrows) == (22, 2)
    assert board.counted == {"geo": 20, "draw": 11, "image": 13, "bookmark": 3, "group": 15, "text (empty)": 1}
    assert len(board.geo_texts) == 12 and "Press CMD/CTRL + G" in board.geo_texts  # 8 geo shapes have no text
    assert board.urls == [
        "https://www.legendkeeper.com/how-to-make-a-great-horror-rpg-campaign/",
        "https://www.legendkeeper.com/how-to-make-a-great-horror-rpg-campaign/",
        "https://legendkeeper.com",
    ]
    made = from_board(out)
    # 1 Map + 51 Pins + 39 Narratives + 2 Relations + 14 Zones + 56 Markers
    assert len(made) == 1 + 51 + 39 + 2 + 14 + 56 == 163
    the_map = made[BOARD_MAP]
    assert the_map["name"] == "Board Bastion: Main" and the_map["supertype"] == "Board"
    assert (the_map["width"], the_map["height"]) == (board.width, board.height) == (4109, 4780)
    assert "image_url" not in the_map and "hidden" not in the_map and "parent_map" not in the_map
    assert the_map["x_legendkeeper_document"] == MAIN and the_map["x_legendkeeper_resource"] == uid(BASTION)
    # the board's records, whole and as read (the shapesV2 records split by typeName, in the order read), in
    # the folder's records/, the Map naming the file; the Map's extension keys fit under keel's 64 KB
    assert the_map["x_legendkeeper_board_record"] == RECORD and "x_legendkeeper_board" not in the_map
    raw = record(out)
    v2 = [r["val"] for r in board_doc(export3())["content"]["shapesV2"]]
    for key, kind, count in (("shapes", "shape", 154), ("bindings", "binding", 52), ("assets", "asset", 35)):
        assert raw[key] == [r for r in v2 if r["typeName"] == kind] and len(raw[key]) == count
    assert len(raw["pages"]) == 1 and (out / RECORD).read_bytes() == encode(raw)  # the folder's own JSON
    assert len(json.dumps(raw).encode("utf-8")) > 65536  # why it is not on the Map
    assert ext_bytes(the_map) < 65536
    assert manifest(out) == [
        {
            "producer": "legendkeeper",
            "format": "tldraw board records as LegendKeeper serves them",
            "version": "1",
            "deltas": False,
        }
    ]  # no "private": nothing on the board is hidden
    assert not report.records_private
    # the box's top left is a top-level text's origin, "CTRL + Mousewheel to zoom in and out." at (-690, -830)
    assert (
        the_map["x_legendkeeper_board_extent"]["min_x"] == -690
        and the_map["x_legendkeeper_board_extent"]["min_y"] == -830
    )
    assert not any(n.kind == "board" for n in report.not_imported)
    text = report.render()
    assert "'Board Bastion: Main': 4109 x 4780; Pins 12 for page cards (child Maps 0) and 39 for notes" in text
    assert "not made, counted: arrows not between two cards or frames 22; arrows from a thing to itself 2;" in text
    assert "Board records, each board's tldraw records whole, written under records/legendkeeper/boards/" in text
    assert "geo 20 (12 with text: 'Try pasting any url into this board', 'Press I'," in text
    assert any(n.startswith("board places: tldraw's page space") for n in report.notes)
    assert any(n.startswith("a board's records (shapes, bindings, assets, pages) are kept") for n in report.notes)


def test_the_cards_frames_notes_and_arrows(tmp_path: Path) -> None:
    out, _ = run(tmp_path)
    pins = by_shape(out, "pin")
    wiki = pins["shape:8LnJ47bgkOF7tBywJICh_"]
    assert (wiki["name"], wiki["element_type"], wiki["element_id"]) == ("Wiki City", "narrative", uid(WIKI))
    assert wiki["id"] == uid("board", BASTION, MAIN, "shape:8LnJ47bgkOF7tBywJICh_") and wiki["map"] == BOARD_MAP
    zones = by_shape(out, "zone")
    welcome = zones["shape:QyfZlqyyCFo1C4wgOzzkb"]
    assert (welcome["subtype"], welcome["shape"]) == ("Frame", "polygon")
    assert (welcome["name"], welcome["shape"]) == ("👋 Welcome to Boards v2!", "polygon")
    markers = [b for b in from_board(out).values() if b["type"] == "marker" and b["zone"] == welcome["id"]]
    assert sorted(m["order"] for m in markers) == [0, 1, 2, 3] and {m["map"] for m in markers} == {BOARD_MAP}
    # the frame sits at (-230, -510), 1670 x 920, unrotated: its corners less the box's min_x -690, and max_y less them
    top_left = next(m for m in markers if m["order"] == 0)
    assert (top_left["x"], top_left["y"]) == (-230 + 690, 3950 + 510)  # max_y 3950
    narratives = by_shape(out, "narrative")
    note = narratives["shape:D0WfsPpZ5JtK7uLY3oJGF"]
    assert note["name"] == "Resize the card to show"  # its first line
    assert note["description"] == "Resize the card to show\na variety of presentation options."
    assert (note["supertype"], note["subtype"], note["x_legendkeeper_parent"]) == ("Note", "note", uid(BASTION))
    assert narratives["shape:cnYeKd-_PDJGHskU34oyL"]["subtype"] == "text"
    assert pins["shape:D0WfsPpZ5JtK7uLY3oJGF"]["element_id"] == note["id"]  # the note's Pin (its own id, ':pin')
    relations = by_shape(out, "relation")
    arrow = relations["shape:PBbRJmLcpcqAZEcZvsOdF"]
    assert (arrow["name"], arrow["supertype"]) == ("Nesting boards is currently unsupported", "Board link")
    assert (arrow["x_legendkeeper_source"], arrow["x_legendkeeper_target"]) == (uid(WIKI), uid(BASTION))
    assert arrow["narratives"] == [uid(WIKI), uid(BASTION)] and arrow["x_legendkeeper_board_map"] == BOARD_MAP
    # "resize" (the frame "Drag & Drop" to itself) and "resize to nest an article!" (Wiki City to Wiki City)
    # link a thing to itself: no Relation
    assert "shape:sHHS6Uh5S7KthbIP2Z82F" not in relations and "shape:WgRHzlcW7RfC0VJfzRszM" not in relations
    assert sorted(r["name"] for r in relations.values()) == [
        "Nesting boards is currently unsupported",
        "resize to nest a map!",
    ]
    # an arrow from an image to a card ("drag from sidebar") and one from a text to a card make nothing
    assert "shape:u2911WGWl5IH48rDS_r0i" not in relations and "shape:qPwAgjq6i5igdxYVjH-oA" not in relations


def test_two_positions_checked_by_hand(tmp_path: Path) -> None:
    """Worked out here from the fixture's numbers, not through the door's own transform."""
    out, _ = run(tmp_path)
    ext = from_board(out)[BOARD_MAP]["x_legendkeeper_board_extent"]
    min_x, max_y = ext["min_x"], ext["max_y"]
    assert (min_x, max_y) == (-690, 3950)
    pins = by_shape(out, "pin")

    # Wiki City's card: in the frame "Embed Pages & Maps!" at (-240, 1770), unrotated; the card at
    # (428.1221470275402, 447.5743150777357), unrotated, 160 x 175.16974187195748: its centre
    cx = -240 + 428.1221470275402 + 160 / 2  # 268.1221470275402
    cy = 1770 + 447.5743150777357 + 175.16974187195748 / 2  # 2305.1591860137146
    card = pins["shape:8LnJ47bgkOF7tBywJICh_"]
    assert card["x_legendkeeper_board_pos"] == pytest.approx([cx, cy])
    assert (card["x"], card["y"]) == (958, 1645)  # 268.12 + 690 = 958.12; 3950 - 2305.16 = 1644.84
    assert (card["x"], card["y"]) == (round(cx - min_x), round(max_y - cy))

    # "Make insane conspiracy boards!": a note in a group rotated 12 degrees (0.20943951023931956 rad), at
    # (1290, 340) in the frame "Welcome to Boards v2!" at (-230, -510), unrotated; the note at
    # (151.1182104730217, -124.82743029918254) in the group, rotated 6 degrees more, 200 x 200 (scale 1)
    g, r = 0.20943951023931956, 0.10471975511965947
    gx, gy = -230 + 1290, -510 + 340  # the group's origin on the page: (1060, -170)
    nx = gx + math.cos(g) * 151.1182104730217 - math.sin(g) * -124.82743029918254  # 1233.767
    ny = gy + math.sin(g) * 151.1182104730217 + math.cos(g) * -124.82743029918254  # -260.680
    t = g + r  # 18 degrees on the page
    cx, cy = nx + math.cos(t) * 100 - math.sin(t) * 100, ny + math.sin(t) * 100 + math.cos(t) * 100
    assert (cx, cy) == pytest.approx((1297.973, -134.673), abs=1e-3)
    note = pins["shape:66aJ-InZDrYHrFdB0vNnk"]
    assert note["x_legendkeeper_board_pos"] == pytest.approx([cx, cy])
    assert (note["x"], note["y"]) == (1988, 4085)  # 1297.97 + 690 = 1987.97; 3950 + 134.67 = 4084.67


# --- a synthetic board: a top-level card, a card under two rotations, three arrows --------------


def synthetic(tmp: Path) -> tuple[Path, ImportReport]:
    data = export3()
    board_doc(data)["content"] = records(
        shape("A", "element", 100, 200, w=40, h=60, resourceId=CHARACTER, documentId=None),
        shape("F", "frame", 1000, 0, math.pi / 2, w=300, h=200, name="Turned"),
        shape("G", "group", 50, 0, math.pi / 2, parent="F"),
        shape("B", "element", 10, 20, parent="G", w=20, h=10, resourceId=LOCATION, documentId=""),
        shape(
            "N",
            "note",
            400,
            100,
            scale=0.5,
            growY=0,
            richText={
                "type": "doc",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Plan"}]},
                    {"type": "paragraph", "content": [{"type": "text", "text": "the raid"}]},
                ],
            },
        ),
        shape("R1", "arrow", 0, 0, text="knows"),
        shape("R2", "arrow", 0, 0, text=""),
        shape("R3", "arrow", 0, 0, text=""),
        shape("R4", "arrow", 0, 0, text="sticky"),
        bind("b1", "R1", "A", "start"),
        bind("b2", "R1", "B", "end"),
        bind("b3", "R2", "A", "start"),  # its end is free
        bind("b4", "R3", "F", "start"),  # from the frame (its Zone) to a card
        bind("b5", "R3", "B", "end"),
        bind("b6", "R4", "N", "start"),  # from a note: neither a page card nor a frame
        bind("b7", "R4", "A", "end"),
    )
    return run(tmp, write(tmp, data))


def test_a_synthetic_board_by_hand(tmp_path: Path) -> None:
    out, report = synthetic(tmp_path)
    # A: top level at (100, 200), 40 x 60: centre (120, 230); corners x 100..140, y 200..260.
    # F: at (1000, 0) turned 90 degrees, 300 x 200: R(90)(u, v) = (-v, u), so its corners are (1000, 0),
    #    (1000, 300), (800, 300), (800, 0).
    # G: at (50, 0) in F: (1000, 0) + R(90)(50, 0) = (1000, 50), turned 90 + 90 = 180 degrees.
    # B: at (10, 20) in G: (1000, 50) + R(180)(10, 20) = (990, 30), 180 degrees; its centre
    #    (990, 30) + R(180)(10, 5) = (980, 25); corners x 970..990, y 20..30.
    # N: a note at (400, 100), scale 0.5: 100 x 100, centre (450, 150).
    # The box: x 100..1000, y 0..300: width 900, height 300; x = X - 100, y = 300 - Y.
    (board,) = report.boards
    assert (board.width, board.height) == (900, 300)
    pins = by_shape(out, "pin")
    assert (pins["shape:A"]["x"], pins["shape:A"]["y"]) == (120 - 100, 300 - 230)
    assert (pins["shape:B"]["x"], pins["shape:B"]["y"]) == (980 - 100, 300 - 25)
    assert pins["shape:B"]["x_legendkeeper_board_pos"] == pytest.approx([980, 25])
    assert (pins["shape:N"]["x"], pins["shape:N"]["y"]) == (450 - 100, 300 - 150)
    assert (pins["shape:A"]["element_type"], pins["shape:B"]["element_type"]) == ("character", "location")
    corners = {m["order"]: (m["x"], m["y"]) for m in from_board(out).values() if m["type"] == "marker"}
    assert corners == {0: (900, 300), 1: (900, 0), 2: (700, 0), 3: (700, 300)}
    note = by_shape(out, "narrative")["shape:N"]
    assert (note["name"], note["description"]) == ("Plan", "Plan\nthe raid")  # a newer tldraw's richText
    # the arrows: R1 (card to card) and R3 (frame to card) are Relations; R2 (a free end) and R4 (from a note) not
    rels = by_shape(out, "relation")
    assert sorted(rels) == ["shape:R1", "shape:R3"]
    rel = rels["shape:R1"]
    assert (rel["name"], rel["supertype"]) == ("knows", "Board link")
    assert (rel["x_legendkeeper_source"], rel["x_legendkeeper_target"]) == (uid(CHARACTER), uid(LOCATION))
    assert rel["actor"] == uid(CHARACTER) and rel["locations"] == [uid(LOCATION)]  # as a titled link's Relation
    assert rel["x_legendkeeper_board_map"] == BOARD_MAP and "hidden" not in rel
    zone = uid("board", BASTION, MAIN, "shape:F")
    framed = rels["shape:R3"]
    assert (framed["name"], framed["zones"], framed["locations"]) == ("Board link", [zone], [uid(LOCATION)])
    assert (framed["x_legendkeeper_source"], framed["x_legendkeeper_target"]) == (zone, uid(LOCATION))
    assert board.loose_arrows == 2 and board.made["relations"] == 2


def test_an_arrow_needs_both_ends_bound_to_cards(tmp_path: Path) -> None:
    data = export3()
    board_doc(data)["content"] = records(
        shape("A", "element", 0, 0, w=10, h=10, resourceId=CHARACTER, documentId=None),
        shape("B", "element", 50, 0, w=10, h=10, resourceId=LOCATION, documentId=None),
        shape("R", "arrow", 0, 0, text="drawn between them, bound to neither"),
        shape("S", "arrow", 0, 0, text=""),
        bind("b1", "S", "A", "end"),  # S: its end on A, its start free
    )
    out, report = run(tmp_path, write(tmp_path, data))
    assert by_shape(out, "relation") == {} and report.boards[0].loose_arrows == 2


# --- hidden ----------------------------------------------------------------------


def test_a_card_on_a_hidden_page_is_a_hidden_pin(tmp_path: Path) -> None:
    data = export3()
    resource(data, WIKI)["isHidden"] = True
    out, report = run(tmp_path, write(tmp_path, data))
    cards = {k for k, s in board_shapes().items() if s["type"] == "element"}
    pins = [p for k, p in by_shape(out, "pin").items() if k in cards]
    wiki = [p for p in pins if p["element_id"] == uid(WIKI)]
    assert len(wiki) == 3 and all(p["hidden"] is True for p in wiki)  # Wiki City's three cards
    assert all("hidden" not in p for p in pins if p not in wiki)  # the other nine
    assert report.hidden.board_pins == 3 and report.hidden.boards == 0
    # both Relations start at a Wiki City card: hidden too
    rels = by_shape(out, "relation")
    assert len(rels) == 2 and all(r["hidden"] is True for r in rels.values())
    # and one of the 'Points of interest' Relations (a titled link, not the board's) ends at Wiki City
    links = [
        b for b in bodies(out) if b["type"] == "relation" and "x_legendkeeper_board_map" not in b and b.get("hidden")
    ]
    assert len(links) == 1 and report.hidden.relations == 2 + 1
    # the board's records name a hidden page's resource: the producer's records are private
    assert manifest(out)[0]["private"] is True and report.records_private
    assert 'Marked "private": true in records/RECORDS.json' in report.render()
    assert "hidden" not in from_board(out)[BOARD_MAP]
    # nothing the board made names it in the open (a map pin's own rule is the map's: named in the report)
    visible = json.dumps([b for b in from_board(out).values() if b.get("hidden") is not True])
    assert '"name": "Wiki City"' not in visible


def test_a_hidden_board_hides_everything_made_from_it(tmp_path: Path) -> None:
    data = export3()
    board_doc(data)["isHidden"] = True
    out, report = run(tmp_path, write(tmp_path, data))
    made = from_board(out)
    assert len(made) == 163 and all(b["hidden"] is True for b in made.values())
    assert manifest(out)[0]["private"] is True
    assert report.hidden.boards == 1 and report.hidden.board_pins == 0 and report.boards[0].hidden


# --- a card that shows a board or a map ----------------------------------------------------


def test_a_card_showing_a_board_makes_that_board_a_child_map(tmp_path: Path) -> None:
    """The tutorial has no card showing a board: Wiki City gets a second board, "Plans", a card on Main
    shows it, a card on Plans shows Main back (a loop, never followed), and a card on Main shows the
    Realm of Tutoria's map document. Board Bastion comes before Wiki City in the tree, so Main's cards
    are placed first: Plans takes parent_map Main, and Main's own would close the loop."""
    data = export3()
    content = board_doc(data)["content"]
    to_plans = shape("toPlans", "element", 0, 0, w=10, h=10, resourceId=WIKI, documentId="plans001")
    to_map = shape("toMap", "element", 0, 0, w=10, h=10, resourceId=TUTORIA, documentId=TUTORIA_MAP)
    content["shapesV2"] += [{"key": s["id"], "val": s} for s in (to_plans, to_map)]
    resource(data, WIKI)["documents"].append(
        {
            "id": "plans001",
            "name": "Plans",
            "type": "board",
            "isHidden": False,
            "content": records(
                shape("back", "element", 0, 0, w=10, h=10, resourceId=BASTION, documentId=MAIN),
                shape("n", "note", 0, 0, text="raid at dawn"),
            ),
        }
    )
    out, report = run(tmp_path, write(tmp_path, data))
    plans_id = uid("board", WIKI, "plans001")
    maps = {b["id"]: b for b in bodies(out) if b["type"] == "map"}
    plans, main = maps[plans_id], maps[BOARD_MAP]
    assert plans["name"] == "Wiki City: Plans" and plans["parent_map"] == BOARD_MAP
    assert "parent_map" not in main  # Main sits under Plans' loop: not followed
    assert any("is shown on 'Wiki City: Plans', which sits under it: no parent_map (a loop)" in n for n in report.notes)
    pins = by_shape(out, "pin")
    assert (pins["shape:toPlans"]["element_type"], pins["shape:toPlans"]["element_id"]) == ("map", plans_id)
    assert pins["shape:toPlans"]["name"] == "Wiki City: Plans"
    realm = uid("map", TUTORIA, TUTORIA_MAP)
    assert (pins["shape:toMap"]["element_type"], pins["shape:toMap"]["element_id"]) == ("map", realm)
    assert "parent_map" not in maps[realm]  # a map document shown on a board is placed, not parented
    back = next(b for b in bodies(out) if b.get("x_legendkeeper_id") == "shape:back" and b["type"] == "pin")
    assert (back["element_type"], back["element_id"], back["map"]) == ("map", BOARD_MAP, plans_id)
    assert {b.name: b.made["child maps"] for b in report.boards} == {"Board Bastion: Main": 1, "Wiki City: Plans": 0}


# --- the two roads, and ids ------------------------------------------------------------------


class _ApiBoard:
    """The file's answers, but its board served as the API serves it: the document's ``board`` key
    taken off, and ``.../docs/<id>/board`` answering the recorded API answer."""

    def __init__(self, file: FileSource, board: Any) -> None:
        self.file, self.board = file, board
        self.producer_input, self.notes = file.producer_input, file.notes
        self.calls: list[str] = []

    def get(self, path: str, params: Any = None) -> Any:
        self.calls.append(path)
        if path.endswith(f"/docs/{MAIN}/board"):
            if self.board is None:
                raise SourceError(path, 500, "BOOM", "the board did not answer")
            return copy.deepcopy(self.board)
        answer = self.file.get(path, params)
        if path.endswith(f"/resources/{BASTION}"):
            for d in answer["documents"]:
                d.pop("board", None)
        return answer


def api_board_in_the_files_ids() -> dict[str, Any]:
    """The API's board answer, its cards' resource ids (the API project's) turned into the file's
    through the same card shape in each."""
    api: dict[str, Any] = json.loads((FIX / "api-board.json").read_text(encoding="utf-8"))["board"]
    file_shapes = {r["val"]["id"]: r["val"] for r in board_doc(export3())["content"]["shapesV2"]}
    to_file: dict[str, str] = {}
    for s in api["shapes"]:
        if s["type"] == "element":
            to_file[s["props"]["resourceId"]] = file_shapes[s["id"]]["props"]["resourceId"]
    assert len(to_file) == 4  # four resources carry the twelve cards
    for s in api["shapes"]:
        if s["type"] == "element":
            s["props"]["resourceId"] = to_file[s["props"]["resourceId"]]
            assert s == file_shapes[s["id"]]  # every other byte of each card as in the file
    for a in api["assets"]:  # a bookmark's preview address names its resource too
        for k, v in a["props"].items():
            for old, new in to_file.items():
                if isinstance(v, str) and f"/{old}/" in v:
                    a["props"][k] = v.replace(f"/{old}/", f"/{new}/")
    return api


def test_the_api_board_gives_the_same_elements_as_the_file(tmp_path: Path) -> None:
    api = api_board_in_the_files_ids()
    assert sorted(api) == ["assets", "bindings", "pages", "schema", "shapes", "version"]
    source = _ApiBoard(FileSource(EXPORT3), api)
    a_out, a_report = run(tmp_path, source, name="api")
    f_out, f_report = run(tmp_path, EXPORT3, name="file")
    assert any(c.endswith(f"/resources/{BASTION}/docs/{MAIN}/board") for c in source.calls)
    assert a_report.unread == [] and len(a_report.boards) == len(f_report.boards) == 1
    a_made, f_made = from_board(a_out), from_board(f_out)
    assert len(a_made) == 163 and sorted(a_made) == sorted(f_made)
    assert a_made == f_made  # every body, field for field
    # the board's records file: the same records by id, each road listing them in its own order
    a_raw, f_raw = record(a_out), record(f_out)
    for key in ("shapes", "bindings", "assets", "pages"):
        assert sorted(a_raw[key], key=lambda r: r["id"]) == sorted(f_raw[key], key=lambda r: r["id"]), key
    assert manifest(a_out) == manifest(f_out)
    assert a_report.boards == f_report.boards


def test_a_board_that_does_not_answer_is_unread_and_not_imported(tmp_path: Path) -> None:
    out, report = run(tmp_path, _ApiBoard(FileSource(EXPORT3), None))
    assert any("'Main'" in u and "the board did not answer" in u for u in report.unread)
    assert [(n.kind, n.document) for n in report.not_imported] == [("board", "Main")]
    assert report.boards == [] and from_board(out) == {}


def test_the_older_content_lists_are_read_when_there_is_no_shapes_v2(tmp_path: Path) -> None:
    data = export3()
    v2 = board_doc(data)["content"]["shapesV2"]
    board_doc(data)["content"] = {
        "shapes": [r["val"] for r in v2 if r["val"]["typeName"] == "shape"],
        "bindings": [r["val"] for r in v2 if r["val"]["typeName"] == "binding"],
    }
    out, report = run(tmp_path, write(tmp_path, data))
    f_out, _ = run(tmp_path, EXPORT3, name="file")
    raw = record(out)  # as read: the two lists, no assets or pages
    assert {k: len(v) for k, v in raw.items()} == {"shapes": 154, "bindings": 52, "assets": 0, "pages": 0}
    assert from_board(out) == from_board(f_out) and report.boards[0].made["card pins"] == 12


def test_two_imports_give_the_same_ids(tmp_path: Path) -> None:
    one, _ = run(tmp_path, name="one")
    two, _ = run(tmp_path, name="two")
    assert from_board(one) == from_board(two)
    ids = sorted(from_board(one))
    assert len(ids) == len(set(ids)) == 163 and BOARD_MAP in ids
    assert (one / RECORD).read_bytes() == (two / RECORD).read_bytes()
    assert uid("board", BASTION, MAIN, "shape:QyfZlqyyCFo1C4wgOzzkb", "0") in ids  # a frame's first Marker
    assert uid("board", BASTION, MAIN, "shape:66aJ-InZDrYHrFdB0vNnk", "pin") in ids  # a note's Pin


def test_a_plan_writes_no_records_and_the_folder_reads_and_lints(tmp_path: Path) -> None:
    report = import_legendkeeper(EXPORT3, out_dir=tmp_path / "planned", plan_only=True)
    assert not (tmp_path / "planned").exists() and "to be written (a plan writes none)" in report.render()
    out, _ = run(tmp_path)
    assert sorted(p.relative_to(out).as_posix() for p in (out / "records").rglob("*") if p.is_file()) == [
        "records/RECORDS.json",
        RECORD,
    ]
    assert len(read_folder(out).elements) == 113 + 163 + 4  # the folder still opens, records beside its elements
    r = subprocess.run([sys.executable, "-m", "onlyworlds.lint", str(out)], capture_output=True, text=True)
    lines = r.stdout.strip().splitlines()
    assert r.returncode == 0 and "280" in lines[-1], r.stdout + r.stderr
    assert [line for line in lines[:-1] if not line.startswith("walk note:")] == [], r.stdout + r.stderr


def test_the_map_carried_the_raw_board_over_keel_s_cap_before(tmp_path: Path) -> None:
    """The size the records move saves: the Map's extension keys with the records on it, and now."""
    out, _ = run(tmp_path)
    the_map = from_board(out)[BOARD_MAP]
    before = ext_bytes({**the_map, "x_legendkeeper_board": record(out)})
    assert before > 65536 > ext_bytes(the_map)
