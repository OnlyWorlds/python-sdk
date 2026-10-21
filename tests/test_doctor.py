"""The doctor (onlyworlds.doctor): one planted case per flag, each beside a clean twin that differs
by the planted value alone, so every flag is watched failing and watched passing. Folders are
built in tmp_path; the API door runs against fakes. Nothing here touches the network."""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import io
import json
import shutil
import subprocess
from collections.abc import Callable, Mapping
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from conftest import FakeTransport, jresp

from onlyworlds import FORMAT_VERSION, Client, Response, doctor, read_folder, write_folder
from onlyworlds.doctor import FLAGS, Report, doctor_api, doctor_folder, fold_name, render_prose

NOW = dt.datetime(2026, 10, 21, 12, 0, tzinfo=dt.UTC)
WORLD = {"id": "w0000000-0000-7000-8000-000000000000", "name": "Harbor World", "format_version": FORMAT_VERSION}
L1 = "l0000000-0000-7000-8000-000000000001"
L2 = "l0000000-0000-7000-8000-000000000002"
C1 = "c0000000-0000-7000-8000-000000000001"
C2 = "c0000000-0000-7000-8000-000000000002"
E1 = "e0000000-0000-7000-8000-000000000001"
T1 = "t0000000-0000-7000-8000-000000000001"
LAW1 = "a0000000-0000-7000-8000-000000000001"
N1 = "n0000000-0000-7000-8000-000000000001"
R1 = "r0000000-0000-7000-8000-000000000001"
P1 = "p0000000-0000-7000-8000-000000000001"
GHOST = "g0000000-0000-7000-8000-00000000dead"

Elements = dict[str, list[dict[str, Any]]]


def clean() -> Elements:
    """A world no flag finds anything in. The Law and the Narrative are Seethe's case: an empty
    description, their text in ``declaration`` and ``story``."""
    return {
        "location": [{"id": L1, "name": "Harbor", "description": "A port."}],
        "character": [{"id": C1, "name": "Ann", "description": "A sailor.", "location": L1}],
        "event": [
            {"id": E1, "name": "Storm", "history": "It rained.", "start_date": 10, "end_date": 12, "characters": [C1]}
        ],
        "title": [
            {"id": T1, "name": "Harbormaster", "description": "", "authority": "Runs the port.", "holders": [C1]}
        ],
        "law": [
            {
                "id": LAW1,
                "name": "Harbor Charter",
                "supertype": "Charter",
                "description": "",
                "declaration": "The port is free.",
                "locations": [L1],
            }
        ],
        "narrative": [{"id": N1, "name": "Ann's Tale", "description": "", "story": "She sailed.", "protagonist": C1}],
        "relation": [
            {
                "id": R1,
                "name": "Ann holds the harbor",
                "supertype": "Tenure",
                "background": "Since spring.",
                "actor": C1,
                "titles": [T1],
                "start_date": 5,
            }
        ],
    }


def with_(base: Elements, etype: str, *bodies: dict[str, Any]) -> Elements:
    out = copy.deepcopy(base)
    out.setdefault(etype, []).extend(copy.deepcopy(list(bodies)))
    return out


def edit(base: Elements, etype: str, eid: str, **fields: Any) -> Elements:
    out = copy.deepcopy(base)
    (body,) = [b for b in out[etype] if b["id"] == eid]
    body.update(fields)
    return out


def folder_report(tmp_path: Path, elements: Elements, world: Mapping[str, Any] = WORLD, **kw: Any) -> Report:
    root = tmp_path / f"w{len(list(tmp_path.iterdir()))}"
    write_folder(root, world, elements)
    return doctor_folder(read_folder(root), now=NOW, **kw)


def found(report: Report, flag: str) -> list[dict[str, Any]]:
    return [f for f in report.findings if f["flag"] == flag]


def snapshot(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


# --- the clean world ----------------------------------------------------------


def test_the_clean_world_has_nothing_to_look_at(tmp_path: Path) -> None:
    r = folder_report(tmp_path, clean())
    assert r.findings == []
    assert r.ran == ["1", "3", "4", "5", "6a", "6b", "9", "10"]
    assert [x["flag"] for x in r.not_run] == ["2", "7", "8"]
    assert r.world == {"id": WORLD["id"], "name": WORLD["name"], "door": "folder"}
    assert r.written == 0
    assert r.compared["3"] == {"n": 1, "of": 1}
    assert r.exit_code == 0


def test_the_json_report_keeps_its_key_order(tmp_path: Path) -> None:
    r = folder_report(tmp_path, clean())
    assert list(r.as_dict()) == ["world", "ran", "not_run", "findings", "compared", "written"]
    assert set(r.compared) <= set(FLAGS)


# --- 1. a link to an element that is not there ----------------------------------


def test_1_a_link_to_a_missing_id(tmp_path: Path) -> None:
    planted = folder_report(tmp_path, edit(clean(), "character", C1, rivals=[GHOST]))
    twin = folder_report(tmp_path, edit(clean(), "character", C1, rivals=[C1]))
    (f,) = found(planted, "1")
    assert f["element"] == {"type": "character", "id": C1, "name": "Ann"}
    assert f["evidence"] == {"field": "rivals", "missing_id": GHOST}
    assert found(twin, "1") == []
    assert planted.compared["1"]["n"] == planted.compared["1"]["of"] == twin.compared["1"]["n"]


def test_1_reads_atlas_spelling_of_a_pin_map(tmp_path: Path) -> None:
    pin = {"id": P1, "name": "Seat", "description": "A seat.", "map_id": GHOST}
    planted = folder_report(tmp_path, with_(clean(), "pin", pin))
    twin = folder_report(
        tmp_path, with_(clean(), "pin", {**pin, "map_id": None, "element_type": "location", "element_id": L1})
    )
    assert [f["evidence"]["field"] for f in found(planted, "1")] == ["map"]
    assert found(twin, "1") == []


# --- 3. an event ending before it starts ----------------------------------------


def test_3_an_event_ending_before_it_starts(tmp_path: Path) -> None:
    planted = folder_report(tmp_path, edit(clean(), "event", E1, end_date=8))
    twin = folder_report(tmp_path, edit(clean(), "event", E1, end_date=10))
    (f,) = found(planted, "3")
    assert f["evidence"] == {"start_date": 10, "end_date": 8}
    assert found(twin, "3") == []


def test_3_says_how_little_it_compared(tmp_path: Path) -> None:
    # Seethe's hand run on the Manifest: 0 of 28 Events carried both dates; a clean count alone reads as a pass
    r = folder_report(tmp_path, edit(clean(), "event", E1, end_date=None))
    assert found(r, "3") == []
    assert r.compared["3"] == {"n": 0, "of": 1}
    assert "0 of 1 Events with both dates" in render_prose(r)


# --- 4. no links in or out --------------------------------------------------------


def test_4_an_element_with_no_links(tmp_path: Path) -> None:
    isle = {"id": L2, "name": "Lonely Isle", "description": "Far out."}
    planted = folder_report(tmp_path, with_(clean(), "location", isle))
    twin = folder_report(tmp_path, with_(clean(), "location", {**isle, "parent_location": L1}))
    (f,) = found(planted, "4")
    assert f["element"]["id"] == L2
    assert found(twin, "4") == []


def test_4_an_element_only_linked_to_is_not_alone(tmp_path: Path) -> None:
    isle = {"id": L2, "name": "Lonely Isle", "description": "Far out."}
    r = folder_report(tmp_path, edit(with_(clean(), "location", isle), "character", C1, birthplace=L2))
    assert found(r, "4") == []


def test_4_never_calls_a_stub_linkless(tmp_path: Path) -> None:
    stub = {"id": C2, "name": "Bo", "description": "", "known_of": True, "updated_at": "2026-10-20T00:00:00Z"}
    r = folder_report(tmp_path, with_(clean(), "character", stub))
    assert found(r, "4") == []
    assert r.compared["4"] == {"n": 7, "of": 8}  # the stub's links are unknown, so it is not compared


# --- 5. names that collide after folding ---------------------------------------


def test_fold_name() -> None:
    assert fold_name("Kael, Inspector") == fold_name("kael   inspector") == "kael inspector"
    assert fold_name("\uff21\uff4e\uff4e") == "ann"  # NFKC: full-width letters
    assert fold_name("STRASSE") == fold_name("straße")  # casefold, not lower
    assert fold_name(" ... ") == ""


def test_5_names_colliding_within_a_type(tmp_path: Path) -> None:
    other = {"id": C2, "name": "ANN!", "description": "Another.", "friends": [C1]}
    planted = folder_report(tmp_path, with_(clean(), "character", other))
    twin = folder_report(tmp_path, with_(clean(), "character", {**other, "name": "Anna"}))
    (f,) = found(planted, "5")
    assert f["evidence"] == {"folded": "ann", "with": [{"type": "character", "id": C2, "name": "ANN!"}]}
    assert found(twin, "5") == []


def test_5_a_name_shared_across_types_is_no_collision(tmp_path: Path) -> None:
    # Moppetopia's Crumblefields is a location, a pin and a zone: the format's own convention
    zone = {"id": "z0000000-0000-7000-8000-000000000001", "name": "harbor", "role": "The port's waters."}
    pin = {"id": P1, "name": "Harbor", "description": "", "element_type": "location", "element_id": L1}
    across = folder_report(tmp_path, with_(with_(clean(), "zone", zone), "pin", pin))
    within = folder_report(tmp_path, with_(clean(), "location", {**zone, "type": "location", "parent_location": L1}))
    assert found(across, "5") == []
    assert [f["element"]["id"] for f in found(within, "5")] == [L1]
    assert "names shared across types are not counted" in render_prose(across)


# --- 6. a stub never filled, both readings --------------------------------------


def test_6a_a_known_of_stub_older_than_n_days(tmp_path: Path) -> None:
    stub = {"id": C2, "name": "Bo", "description": "", "known_of": True, "updated_at": "2026-09-01T00:00:00Z"}
    planted = folder_report(tmp_path, with_(clean(), "character", stub))
    twin = folder_report(tmp_path, with_(clean(), "character", {**stub, "updated_at": "2026-10-20T00:00:00Z"}))
    (f,) = found(planted, "6a")
    assert f["element"]["id"] == C2
    assert found(twin, "6a") == []
    assert found(folder_report(tmp_path, with_(clean(), "character", stub), days=60), "6a") == []
    assert planted.compared["6a"] == {"n": 1, "of": 1}


def test_6b_an_element_with_no_text(tmp_path: Path) -> None:
    law = {"id": "a0000000-0000-7000-8000-000000000002", "name": "Toll", "description": "", "locations": [L1]}
    planted = folder_report(tmp_path, with_(clean(), "law", {**law, "declaration": "", "purpose": "  "}))
    twin = folder_report(tmp_path, with_(clean(), "law", {**law, "purpose": "To pay for the docks."}))
    (f,) = found(planted, "6b")
    assert f["element"]["id"] == law["id"]
    assert "declaration" in f["evidence"]["fields"] and "name" not in f["evidence"]["fields"]
    assert found(twin, "6b") == []


def test_6b_seethes_35_false_alarms(tmp_path: Path) -> None:
    # Her first hand run read `description` alone and called 35 of 115 elements stubs; each had text in its own fields
    r = folder_report(
        tmp_path,
        edit(clean(), "title", T1, authority="", eligibility="Born in the harbor."),
    )
    assert found(r, "6b") == []  # Law: declaration; Narrative: story; Title: eligibility


def test_6b_leaves_a_stub_to_6a(tmp_path: Path) -> None:
    stub = {"id": C2, "name": "Bo", "description": "", "known_of": True, "updated_at": "2026-10-20T00:00:00Z"}
    r = folder_report(tmp_path, with_(clean(), "character", stub))
    assert found(r, "6b") == []
    assert r.compared["6b"]["n"] == 6 and r.compared["6b"]["of"] == 7  # the Relation is skipped, the stub not compared


def test_6b_skips_the_types_whose_text_is_description_alone(tmp_path: Path) -> None:
    # Moppetopia: 148 of 177 findings were 6b on Markers, Pins and a Map
    assert doctor._SPARSE_TYPES == ("map", "marker", "pin", "relation")  # measured from the schema
    marker = {"id": "m0000000-0000-7000-8000-000000000001", "name": "Dock", "description": "", "zone": None}
    zone = {"id": "z0000000-0000-7000-8000-000000000001", "name": "Dock", "description": "", "role": "", "context": ""}
    skipped = folder_report(tmp_path, with_(clean(), "marker", {**marker, "map": None}))
    compared = folder_report(tmp_path, with_(clean(), "zone", zone))
    assert found(skipped, "6b") == []
    assert [f["element"]["type"] for f in found(compared, "6b")] == ["zone"]
    assert skipped.compared["6b"] == {"n": 6, "of": 6, "skipped_types": ["map", "marker", "pin", "relation"]}
    assert "not compared: map, marker, pin, relation" in render_prose(skipped)


# --- message-shaped findings ------------------------------------------------------


def test_a_finding_on_a_message_is_kind_message(tmp_path: Path) -> None:
    # BrainBoost: two "Re:" messages collided by name; they are room things, not facts about the world
    re1 = {"id": "n0000000-0000-7000-8000-000000000002", "name": "Re: Plans", "supertype": "Message", "story": "Yes."}
    re2 = {**re1, "id": "n0000000-0000-7000-8000-000000000003", "story": "No."}
    planted = folder_report(tmp_path, with_(clean(), "narrative", {**re1, "narrator": C1}, {**re2, "narrator": C1}))
    twin = folder_report(
        tmp_path,
        with_(clean(), "narrative", {**re1, "narrator": C1, "supertype": "Letter"}, {**re2, "narrator": C1}),
    )
    (f,) = found(planted, "5")
    assert f["kind"] == "message"
    (g,) = found(twin, "5")
    assert "kind" not in g  # the element it names is a Letter
    assert planted.to_look_at == [] and planted.exit_code == 1
    prose = render_prose(planted)
    assert prose.splitlines()[2].startswith("0 things to look at,")
    assert "(1 on messages and room things, listed last)" in prose.splitlines()[2]
    assert prose.index("What could not be checked") < prose.index(
        "Messages and room things (not facts about the world)"
    )
    assert "they still make the exit code 1" in prose
    assert "Messages and room things" not in render_prose(twin)


def test_every_parlor_supertype_is_a_message(tmp_path: Path) -> None:
    for supertype in ("Message", "Board", "Work item", "Spec", "Heart", "Vote", "Sitting", "work ITEM"):
        lone = {"id": N1.replace("1", "9"), "name": "Lone", "supertype": supertype, "story": "Text."}
        (f,) = found(folder_report(tmp_path, with_(clean(), "narrative", lone)), "4")
        assert f.get("kind") == "message", supertype
    (f,) = found(folder_report(tmp_path, with_(clean(), "narrative", {**lone, "supertype": "Chronicle"})), "4")
    assert "kind" not in f


# --- 9 and 10. the file side ----------------------------------------------------


def test_9_an_old_format_version(tmp_path: Path) -> None:
    planted = folder_report(tmp_path, clean(), {**WORLD, "format_version": "0.3.7"})
    twin = folder_report(tmp_path, clean(), {**WORLD, "format_version": FORMAT_VERSION})
    (f,) = found(planted, "9")
    assert f["element"] is None and f["evidence"]["format_version"] == "0.3.7"
    assert found(twin, "9") == []


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_10_an_api_key_in_a_tracked_world_json(tmp_path: Path) -> None:
    secret = "ow_w_not_a_real_key_0123456789"
    reports = {}
    for case in ("tracked", "untracked", "tracked-no-key"):
        root = tmp_path / case
        api = {"world_id": WORLD["id"]} if case == "tracked-no-key" else {"api_key": secret}
        write_folder(root, {**WORLD, "api": api}, clean())
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        if case != "untracked":
            subprocess.run(["git", "-C", str(root), "add", "world.json"], check=True)
        reports[case] = doctor_folder(read_folder(root), now=NOW)
    (f,) = found(reports["tracked"], "10")
    assert f["evidence"] == {"file": "world.json", "key": "api.api_key", "tracked": True}
    assert secret not in json.dumps(reports["tracked"].as_dict()) and secret not in render_prose(reports["tracked"])
    assert found(reports["untracked"], "10") == []
    assert found(reports["tracked-no-key"], "10") == []


def test_10_a_folder_outside_git_holds_its_key_privately(tmp_path: Path) -> None:
    r = folder_report(tmp_path, clean(), {**WORLD, "api": {"api_key": "ow_w_x"}})
    assert found(r, "10") == [] and "10" in r.ran


# --- the folder door never writes; the command line -------------------------------


def run_main(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = doctor.main(argv)
    return code, out.getvalue(), err.getvalue()


def test_the_folder_door_changes_no_file(tmp_path: Path) -> None:
    root = tmp_path / "w"
    write_folder(root, WORLD, edit(clean(), "character", C1, rivals=[GHOST]))
    before = snapshot(root)
    for argv in ([str(root)], [str(root), "--json"]):
        run_main(argv)
    assert snapshot(root) == before


def test_exit_codes(tmp_path: Path) -> None:
    write_folder(tmp_path / "clean", WORLD, clean())
    write_folder(tmp_path / "sick", WORLD, edit(clean(), "event", E1, end_date=1))
    (tmp_path / "empty").mkdir()
    assert run_main([str(tmp_path / "clean")])[0] == 0
    assert run_main([str(tmp_path / "sick")])[0] == 1
    assert run_main([str(tmp_path / "empty")])[0] == 2
    assert run_main([str(tmp_path / "missing")])[0] == 2
    assert run_main([])[0] == 2
    assert run_main([str(tmp_path / "clean"), "--api"])[0] == 2


def test_the_prose_report_reads_counts_first(tmp_path: Path) -> None:
    root = tmp_path / "w"
    write_folder(root, WORLD, edit(clean(), "event", E1, end_date=1))
    _, out, _ = run_main([str(root)])
    lines = out.splitlines()
    assert lines[2] == "1 things to look at, 8 flags ran, 3 could not run, 0 things written"
    assert lines.index("What was checked") < lines.index("What could not be checked, and why")
    assert "  - event Storm (" + E1 + "): it ends before it starts" in lines
    assert (
        "  2. A Title whose holders changed with no dated Relation: needs the feed's history of Title.holders" in lines
    )


def test_the_json_report_is_ascii(tmp_path: Path) -> None:
    root = tmp_path / "w"
    write_folder(root, {**WORLD, "name": "Hâvre"}, clean())
    code, out, _ = run_main([str(root), "--json"])
    assert out.isascii() and json.loads(out)["world"]["name"] == "Hâvre"
    assert code == 0


# --- the API door -----------------------------------------------------------------


def wire(etype: str, body: Mapping[str, Any], seq: int) -> dict[str, Any]:
    return {
        "type": etype,
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-10-01T00:00:00Z",
        "change_seq": seq,
        **body,
    }


def feed_of(elements: Elements) -> list[dict[str, Any]]:
    """One upsert per element at its change_seq, as keel serves it (its row at its latest seq)."""
    rows = [
        {"op": "upsert", "type": b["type"], "id": b["id"], "updated_at": b["updated_at"], "element": b}
        for bodies in elements.values()
        for b in bodies
    ]
    return sorted(rows, key=lambda r: (r["element"]["change_seq"], r["id"]))


def on_the_wire(elements: Elements) -> Elements:
    seq = iter(range(1, 10_000))
    return {t: [wire(t, b, next(seq)) for b in bodies] for t, bodies in elements.items()}


class FakeReader:
    """Client's read methods over fixed data; every write method raises."""

    def __init__(
        self,
        elements: Elements,
        rows: list[dict[str, Any]] | None = None,
        *,
        role: str = "owner",
        page: int = 2,
        feed_fails: bool = False,
    ):
        self.elements = elements
        self.rows = feed_of(elements) if rows is None else rows
        self.role = role
        self.page = page
        self.feed_fails = feed_fails
        self.calls: list[str] = []

    def me(self) -> dict[str, Any]:
        self.calls.append("me")
        return {"world": WORLD["id"], "role": self.role, "kind": "owner"}

    def get_world(self) -> dict[str, Any]:
        self.calls.append("get_world")
        return {"id": WORLD["id"], "name": WORLD["name"]}

    def list_page(self, element_type: str, *, limit: int | None = None, cursor: str | None = None) -> dict[str, Any]:
        self.calls.append(f"list_page {element_type}")
        assert limit == 1000
        at = int(cursor or 0)
        data = self.elements.get(element_type, [])
        nxt = at + self.page
        return {"data": data[at:nxt], "has_more": nxt < len(data), "next_cursor": str(nxt) if nxt < len(data) else None}

    def changes(self, *, since: str | None = None, limit: int | None = None) -> dict[str, Any]:
        self.calls.append("changes")
        if self.feed_fails:
            raise ConnectionError("no answer")
        at = int(since or 0)
        nxt = at + 3
        head = max((r.get("element", {}).get("change_seq", 0) for r in self.rows), default=0)
        return {"changes": self.rows[at:nxt], "has_more": nxt < len(self.rows), "cursor": str(nxt), "head": head}

    def _write(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the doctor wrote")

    create = upsert = patch = delete = edit_links = bulk = patch_world = _write


def api_report(reader: FakeReader, **kw: Any) -> Report:
    return doctor_api(reader, now=NOW, **kw)


def test_the_api_door_on_the_clean_world() -> None:
    reader = FakeReader(on_the_wire(clean()))
    r = api_report(reader)
    assert r.findings == []
    assert r.world["door"] == "api"
    assert r.ran == ["1", "3", "4", "5", "6a", "6b", "8"]
    assert {x["flag"]: x["why"] for x in r.not_run} == {
        "2": "the feed carries current bodies only; a holders change cannot be seen (measured: 7 upserts for 7 ids)",
        "7": "read marks are not readable through the API",
        "9": "a file-side check: the API door reads no world.json",
        "10": "a file-side check: the API door reads no world.json",
    }
    assert set(reader.calls) >= {"me", "get_world", "changes", "list_page character"}


def test_1_the_api_door_finds_a_missing_id_and_pages_lists() -> None:
    elements = on_the_wire(
        with_(clean(), "character", {"id": C2, "name": "Bo", "description": "B.", "friends": [GHOST]})
    )
    reader = FakeReader(elements, page=1)
    (f,) = found(api_report(reader), "1")
    assert f["element"]["id"] == C2
    assert reader.calls.count("list_page character") == 2  # two pages of one
    assert found(api_report(FakeReader(on_the_wire(clean()))), "1") == []


def test_1_does_not_run_through_a_guest_key() -> None:
    elements = on_the_wire(edit(clean(), "character", C1, rivals=[GHOST]))
    r = api_report(FakeReader(elements, role="guest"))
    assert found(r, "1") == [] and "1" not in r.ran and "1" not in r.compared
    assert [x["why"] for x in r.not_run if x["flag"] == "1"] == [
        "a guest key cannot see every element: a link to one it cannot see is not a deletion"
    ]
    assert "1" in api_report(FakeReader(elements, role="contributor")).ran


def holders_feed(dated: bool) -> FakeReader:
    """A feed that, unlike keel's, holds two versions of the Title: its holders moved from Ann to Bo."""
    base = clean()
    base = with_(base, "character", {"id": C2, "name": "Bo", "description": "B.", "friends": [C1]})
    if not dated:
        base = edit(base, "relation", R1, start_date=None)
    elements = on_the_wire(base)
    (title,) = elements["title"]
    old = {**title, "holders": [C1], "change_seq": 1}
    new = {**title, "holders": [C2], "change_seq": 50}
    elements["title"] = [new]
    rows = feed_of(elements)
    rows.insert(0, {"op": "upsert", "type": "title", "id": T1, "updated_at": old["updated_at"], "element": old})
    return FakeReader(elements, rows)


def test_2_a_title_whose_holders_changed_with_no_dated_relation() -> None:
    planted = api_report(holders_feed(dated=False))
    twin = api_report(holders_feed(dated=True))
    (f,) = found(planted, "2")
    assert f["element"]["id"] == T1
    assert f["evidence"] == {"holders_before": [C1], "holders_after": [C2], "versions": 2}
    assert found(twin, "2") == []
    assert planted.compared["2"] == {"n": 1, "of": 1}


def charter_feed(after: int, charter: bool = True) -> FakeReader:
    base = clean() if charter else edit(clean(), "law", LAW1, supertype="Decree")
    elements = on_the_wire(base)
    rows = feed_of(elements)
    rows = [r for r in rows if r["id"] != LAW1] + [r for r in rows if r["id"] == LAW1]  # the charter last
    for i in range(after):
        rows.append({"op": "delete", "type": "object", "id": f"o-{i}", "deleted_at": "2026-10-02T00:00:00Z"})
    return FakeReader(elements, rows)


def test_8_a_charter_untouched_after_n_changes() -> None:
    planted = api_report(charter_feed(51), changes=50)
    twin = api_report(charter_feed(50), changes=50)
    (f,) = found(planted, "8")
    assert f["element"]["id"] == LAW1 and f["evidence"]["changes_after"] == 51
    assert found(twin, "8") == []
    assert planted.compared["8"] == {"n": 1, "of": 1}


def test_8_no_charter_is_a_finding_of_its_own() -> None:
    (f,) = found(api_report(charter_feed(0, charter=False)), "8")
    assert f["element"] is None and f["reason"].startswith("no charter")


def test_2_and_8_do_not_run_when_the_feed_cannot_be_read() -> None:
    r = api_report(FakeReader(on_the_wire(clean()), feed_fails=True))
    assert {x["flag"] for x in r.not_run} >= {"2", "8"}
    assert "8" not in r.ran


def test_6a_through_the_api() -> None:
    stub = {"id": C2, "name": "Bo", "description": "", "known_of": True}
    elements = on_the_wire(with_(clean(), "character", stub))
    elements["character"][1]["updated_at"] = "2026-09-01T00:00:00Z"
    (f,) = found(api_report(FakeReader(elements)), "6a")
    assert f["element"]["id"] == C2
    elements["character"][1]["updated_at"] = "2026-10-20T00:00:00Z"
    assert found(api_report(FakeReader(elements)), "6a") == []


def route(elements: Elements) -> Callable[[str, str, Mapping[str, str], bytes | None], Response]:
    """The API as a real Client meets it; any method but GET fails the test."""
    rows = feed_of(elements)

    def handler(method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> Response:
        assert method == "GET", f"the doctor sent {method} {url}"
        parts = urlsplit(url)
        path = parts.path.split("/api/v2/", 1)[1].strip("/")
        if path == "world":
            return jresp(200, {"id": WORLD["id"], "name": WORLD["name"]})
        if path == "me":
            return jresp(200, {"world": WORLD["id"], "role": "owner", "kind": "owner"})
        if path == "changes":
            assert parse_qs(parts.query)["limit"] == ["1000"]
            return jresp(200, {"cursor": "9:x", "changes": rows, "has_more": False, "head": len(rows)})
        assert parse_qs(parts.query)["limit"] == ["1000"]
        return jresp(200, {"data": elements.get(path, []), "has_more": False, "next_cursor": None})

    return handler


def test_the_api_door_sends_only_gets_through_a_real_client() -> None:
    transport = FakeTransport(handler=route(on_the_wire(edit(clean(), "event", E1, end_date=1))))
    client = Client("ow_w_testkey", "1234", transport=transport)
    r = doctor_api(client, now=NOW)
    assert [f["flag"] for f in r.findings] == ["3"]
    assert {c.method for c in transport.calls} == {"GET"}
    assert r.written == 0


def test_the_api_command_line(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = FakeTransport(handler=route(on_the_wire(clean())))
    seen: dict[str, Any] = {}

    def make(key: str, pin: str | None = None, **kw: Any) -> Client:
        seen.update(key=key, pin=pin)
        return Client(key, pin, transport=transport, **kw)

    monkeypatch.setattr(doctor, "Client", make)
    for name in ("OW_API_KEY", "OW_API_PIN", "ONLYWORLDS_API_KEY", "ONLYWORLDS_API_PIN"):
        monkeypatch.delenv(name, raising=False)
    assert run_main(["--api"])[0] == 2
    monkeypatch.setenv("OW_API_KEY", "ow_r_testkey")
    monkeypatch.setenv("OW_API_PIN", "")
    code, out, _ = run_main(["--api", "--json"])
    assert code == 0 and json.loads(out)["world"]["door"] == "api"
    assert seen == {"key": "ow_r_testkey", "pin": None}


def test_the_api_command_line_falls_back_to_the_toolkits_names(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = FakeTransport(handler=route(on_the_wire(clean())))
    seen: list[tuple[str, str | None]] = []

    def make(key: str, pin: str | None = None, **kw: Any) -> Client:
        seen.append((key, pin))
        return Client(key, pin, transport=transport, **kw)

    monkeypatch.setattr(doctor, "Client", make)
    for name in ("OW_API_KEY", "OW_API_PIN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ONLYWORLDS_API_KEY", "ow_w_toolkit")
    monkeypatch.setenv("ONLYWORLDS_API_PIN", "4321")
    assert run_main(["--api"])[0] == 0
    monkeypatch.setenv("OW_API_KEY", "ow_w_package")
    monkeypatch.setenv("OW_API_PIN", "1234")
    assert run_main(["--api"])[0] == 0
    assert seen == [("ow_w_toolkit", "4321"), ("ow_w_package", "1234")]  # the package's own names win


def test_the_api_command_line_when_nothing_can_be_read(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = FakeTransport(handler=lambda m, u, h, b: jresp(401, {"error": {"code": "invalid_key"}}))
    monkeypatch.setattr(doctor, "Client", lambda key, pin=None, **kw: Client(key, pin, transport=transport, **kw))
    monkeypatch.setenv("OW_API_KEY", "ow_r_bad")
    code, _, err = run_main(["--api"])
    assert code == 2 and "nothing could be read" in err


# --- the packet: the findings as work items (the packet profile, dist.36) ----------


def test_packets_on_the_clean_world(tmp_path: Path) -> None:
    assert doctor.packets(folder_report(tmp_path, clean()), now=NOW) == []
    root = tmp_path / "clean"
    write_folder(root, WORLD, clean())
    code, out, _ = run_main([str(root), "--packet"])
    assert code == 0 and json.loads(out) == []


def test_packets_one_entry_per_element_in_the_profiles_shape(tmp_path: Path) -> None:
    # C2: no links and no text (flags 4 and 6b on one element); a Message with the same faults is a
    # room thing and stays out; the packet is one Relation in the profile's shape, with no id
    msg = {"id": N1[:-1] + "9", "name": "Re: Plans", "supertype": "Message", "description": ""}
    world = with_(with_(clean(), "character", {"id": C2, "name": "Bo", "description": ""}), "narrative", msg)
    report = folder_report(tmp_path, world)
    assert {f["flag"] for f in report.findings if f["element"]["id"] == C2} == {"4", "6b"}
    assert any(f.get("kind") == "message" for f in report.findings)
    (packet,) = doctor.packets(report, now=NOW)
    assert list(packet) == [
        "type",
        "supertype",
        "subtype",
        "name",
        "description",
        "characters",
        "x_packet_elements",
        "x_packet_source",
        "x_packet_producer",
    ]
    assert packet["type"] == "relation" and packet["supertype"] == "Work item" and packet["subtype"] == "open"
    assert packet["name"] == "Doctor's findings, 2026-10-21"
    assert packet["description"].startswith(
        "1 of 1 elements to look at in Harbor World, from the doctor's run on 2026-10-21"
    )
    assert packet["characters"] == [C2]
    r4, r6b = (f["reason"] for f in report.to_look_at if f["element"]["id"] == C2)
    assert packet["x_packet_elements"] == [{"type": "character", "id": C2, "reason": f"{r4}. {r6b}."}]
    assert packet["x_packet_source"] == {"server": None, "world": WORLD["id"]}
    assert packet["x_packet_producer"] == {"tool": "onlyworlds doctor", "version": doctor.__version__}
    assert msg["id"] not in json.dumps(packet)
    # a reader needs no lookup: every entry's three keys are strings
    for e in packet["x_packet_elements"]:
        assert set(e) == {"type", "id", "reason"} and all(isinstance(v, str) for v in e.values())


def test_packets_leave_out_a_finding_on_the_world_itself() -> None:
    # flag 8's "no charter" names no element; a packet entry needs a type and an id
    report = Report(world={"id": WORLD["id"], "name": "W", "door": "api"}, ran=["8"])
    report.findings = [{"flag": "8", "element": None, "reason": "no Law with supertype Charter", "evidence": {}}]
    assert doctor.packets(report, server="https://www.onlyworlds.com", now=NOW) == []


def test_packets_split_past_the_cap() -> None:
    report = Report(world={"id": WORLD["id"], "name": "W", "door": "api"}, ran=["4"])
    ids = [f"c0000000-0000-7000-8000-{i:012d}" for i in range(300)]
    report.findings = [
        {
            "flag": "4",
            "element": {"type": "character", "id": i, "name": "x", "reason": ""},
            "reason": "no links",
            "evidence": {},
        }
        for i in ids
    ]
    parts = doctor.packets(report, server="https://www.onlyworlds.com", now=NOW, cap=4000)
    assert len(parts) > 1
    assert [p["name"] for p in parts] == [
        f"Doctor's findings, 2026-10-21 ({i} of {len(parts)})" for i in range(1, len(parts) + 1)
    ]
    assert [e["id"] for p in parts for e in p["x_packet_elements"]] == ids
    for p in parts:
        assert p["characters"] == [e["id"] for e in p["x_packet_elements"]]
        assert doctor._packet_bytes(p["x_packet_elements"], p["x_packet_source"], p["x_packet_producer"]) <= 4000
        assert p["x_packet_source"] == {"server": "https://www.onlyworlds.com", "world": WORLD["id"]}
    (whole,) = doctor.packets(report, now=NOW)
    assert len(whole["x_packet_elements"]) == 300 and "(1 of" not in whole["name"]


def test_the_packet_command_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "w"
    write_folder(root, WORLD, with_(clean(), "character", {"id": C2, "name": "Bo", "description": "Alone."}))
    code, out, _ = run_main([str(root), "--packet"])
    (packet,) = json.loads(out)
    assert code == 1 and packet["x_packet_source"] == {"server": None, "world": WORLD["id"]}
    assert packet["x_packet_elements"] == [
        {"type": "character", "id": C2, "reason": "no link field is set on it and no element links to it."}
    ]
    code, _, err = run_main([str(root), "--packet", "--json"])
    assert code == 2 and "one of the two" in err
    # through the API door the source names the server the world was read from
    transport = FakeTransport(
        handler=route(on_the_wire(with_(clean(), "character", {"id": C2, "name": "Bo", "description": "Alone."})))
    )
    monkeypatch.setattr(doctor, "Client", lambda key, pin=None, **kw: Client(key, pin, transport=transport, **kw))
    monkeypatch.setenv("OW_API_KEY", "ow_r_testkey")
    monkeypatch.setenv("OW_API_PIN", "")
    code, out, _ = run_main(["--api", "--packet", "--base-url", "https://keel-staging.onrender.com/api/v2/"])
    (packet,) = json.loads(out)
    assert code == 1 and packet["x_packet_source"] == {
        "server": "https://keel-staging.onrender.com/api/v2",
        "world": WORLD["id"],
    }
