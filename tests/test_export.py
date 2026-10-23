from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from conftest import FakeTransport, jresp

from onlyworlds import FORMAT_VERSION, Client, __version__, export_world, read_folder
from onlyworlds.export import EXPORT_PRODUCER, exported_as
from onlyworlds.http import Response


def test_export_paginates_and_writes_a_folder(tmp_path: Path, make_client: Callable[..., Client]) -> None:
    chars = [{"id": f"c0000000-0000-7000-8000-00000000000{i}", "type": "character", "name": f"C{i}"} for i in range(3)]
    world = {"id": "w1", "name": "World", "time_range_current": 3, "public_read": False}

    def handler(method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> Response:
        u = urlparse(url)
        q = parse_qs(u.query)
        path = u.path.removeprefix("/api/v2/")
        assert method == "GET"
        if path == "world/":
            return jresp(200, world)
        if path == "me/":
            return jresp(200, {"world": {"id": "w1", "name": "World"}, "scope": "write", "kind": "owner",
                               "role": "owner", "membership": None, "character": None})  # fmt: skip
        if path == "character/":
            if "cursor" not in q:
                return jresp(200, {"data": chars[:2], "has_more": True, "next_cursor": "seq:2/x"})
            assert q["cursor"] == ["seq:2/x"]
            return jresp(200, {"data": chars[2:], "has_more": False, "next_cursor": None})
        return jresp(200, {"data": [], "has_more": False, "next_cursor": None})

    t = FakeTransport(handler=handler)
    rep = export_world(tmp_path / "out", client=make_client(t))
    assert rep.counts == {"character": 3}
    assert any("cursor=seq%3A2%2Fx" in c.url for c in t.calls)  # opaque cursor, url-quoted
    assert len(t.calls) == 1 + 1 + 22 + 1  # world, me, one page per type, a second character page
    f = read_folder(tmp_path / "out")
    assert len(f.elements) == 3
    w = json.loads((tmp_path / "out" / "world.json").read_text(encoding="utf-8"))
    assert list(w) == [
        "id",
        "name",
        "time_current",
        "public_read",
        "source",
        "exported_as",
        "producer",
        "format_version",
    ]


# --- v0.3.9 provenance lines: source and exported_as (§4.2) ---------------------------------

WID = "018f0000-0000-7000-8000-0000000000aa"
CID = "018f0000-0000-7000-8000-0000000000cc"


def _me(kind: str, role: str, character: str | None = None) -> dict[str, object]:
    return {"world": {"id": WID, "name": "W"}, "scope": "read", "kind": kind, "role": role,
            "membership": None if kind == "owner" else "m1", "character": character}  # fmt: skip


def _export(
    tmp_path: Path,
    make_client: Callable[..., Client],
    me: Response,
    character: Response | None = None,
    world: Mapping[str, object] | None = None,
    producer: Mapping[str, str] | None = None,
) -> tuple[dict[str, object], FakeTransport]:
    def handler(method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> Response:
        path = urlparse(url).path.removeprefix("/api/v2/")
        assert method == "GET"
        if path == "world/":
            return jresp(200, dict(world) if world is not None else {"id": WID, "name": "W", "public_read": False})
        if path == "me/":
            return me
        if path == f"character/{CID}/":
            assert character is not None, "the Character is read only for a guest"
            return character
        return jresp(200, {"data": [], "has_more": False, "next_cursor": None})

    t = FakeTransport(handler=handler)
    out = tmp_path / "out"
    export_world(out, client=make_client(t, attempts=1), producer=producer)
    return json.loads((out / "world.json").read_text(encoding="utf-8")), t


def test_an_export_carries_the_servers_origin_beside_its_own_lines(
    tmp_path: Path, make_client: Callable[..., Client]
) -> None:
    first = {"source": None, "producer": {"tool": "lantern", "version": "0.9.0", "input": "bare"}}
    world = {"id": WID, "name": "W", "public_read": False, "origin": first}
    w, _ = _export(tmp_path, make_client, jresp(200, _me("owner", "owner")), world=world)
    assert w["origin"] == first  # v0.3.16: the world's first import, as the server keeps it
    assert isinstance(w["source"], dict) and w["source"]["world"] == WID  # this export's own line, fresh
    w2, _ = _export(tmp_path / "b", make_client, jresp(200, _me("owner", "owner")))
    assert "origin" not in w2  # none served, none written


def test_world_json_says_where_it_came_from(tmp_path: Path, make_client: Callable[..., Client]) -> None:
    w, _ = _export(tmp_path, make_client, jresp(200, _me("owner", "owner")))
    assert w["format_version"] == "0.3.17" == FORMAT_VERSION
    src = w["source"]
    assert isinstance(src, dict) and list(src) == ["server", "world", "at"]
    assert src["server"] == "https://www.onlyworlds.com"  # the API origin, not the /api/v2 base
    assert src["world"] == WID
    at = datetime.fromisoformat(str(src["at"]))
    assert at.tzinfo is not None and abs(datetime.now(UTC) - at) < timedelta(minutes=5)
    assert str(src["at"]).endswith("Z")


def test_owner_key_exports_the_owner_slice(tmp_path: Path, make_client: Callable[..., Client]) -> None:
    # an owner's /me may name the owner's Character; the owner slice is the whole world, so none is written
    w, _ = _export(tmp_path, make_client, jresp(200, _me("owner", "owner", CID)))
    assert w["exported_as"] == {"kind": "owner", "role": "owner", "character": None}


def test_contributor_key_exports_a_member_slice(tmp_path: Path, make_client: Callable[..., Client]) -> None:
    w, _ = _export(tmp_path, make_client, jresp(200, _me("person", "contributor", CID)))
    assert w["exported_as"] == {"kind": "member", "role": "contributor", "character": None}


def test_co_builder_key_exports_a_member_slice(tmp_path: Path, make_client: Callable[..., Client]) -> None:
    w, _ = _export(tmp_path, make_client, jresp(200, _me("agent", "co_builder")))
    assert w["exported_as"] == {"kind": "member", "role": "co_builder", "character": None}


def test_guest_key_exports_its_characters_slice(tmp_path: Path, make_client: Callable[..., Client]) -> None:
    character = jresp(200, {"id": CID, "type": "character", "name": "Mira"})
    w, t = _export(tmp_path, make_client, jresp(200, _me("player", "guest", CID)), character)
    assert w["exported_as"] == {"kind": "character", "role": "guest", "character": {"id": CID, "name": "Mira"}}
    assert any(urlparse(c.url).path.endswith(f"/character/{CID}/") for c in t.calls)


def test_no_me_writes_no_exported_as(tmp_path: Path, make_client: Callable[..., Client]) -> None:
    w, _ = _export(tmp_path, make_client, jresp(404, {"error": {"type": "not_found", "code": "not_found"}}))
    assert "exported_as" not in w  # absent, never guessed
    assert w["source"]["world"] == WID  # type: ignore[index]  # the export still says where it came from


def test_guest_whose_character_cannot_be_read_writes_no_exported_as(
    tmp_path: Path, make_client: Callable[..., Client]
) -> None:
    missing = jresp(404, {"error": {"type": "not_found", "code": "not_found"}})
    w, _ = _export(tmp_path, make_client, jresp(200, _me("person", "guest", CID)), missing)
    assert "exported_as" not in w


def test_exported_as_mapping_names_only_what_it_knows() -> None:
    def never(cid: str) -> str | None:
        raise AssertionError("no Character read")

    assert exported_as(None, never) is None
    assert exported_as({"kind": "person", "role": "guest", "character": None}, never) is None
    assert exported_as({"kind": "person", "role": "steward"}, never) is None  # a role the table does not name
    named = exported_as({"kind": "agent", "role": "guest", "character": CID}, lambda cid: "")
    assert named == {"kind": "character", "role": "guest", "character": {"id": CID, "name": ""}}


# --- v0.3.14 the producer line (§4.2) --------------------------------------------------------


def test_a_fresh_export_writes_the_producer_line(tmp_path: Path, make_client: Callable[..., Client]) -> None:
    w, _ = _export(tmp_path, make_client, jresp(200, _me("owner", "owner")))
    assert w["producer"] == {"tool": "onlyworlds", "version": __version__, "input": "server"}
    assert list(w["producer"]) == ["tool", "version", "input"]  # type: ignore[arg-type]
    assert dict(EXPORT_PRODUCER) == w["producer"]


def test_no_me_still_writes_the_producer_line(tmp_path: Path, make_client: Callable[..., Client]) -> None:
    w, _ = _export(tmp_path, make_client, jresp(404, {"error": {"type": "not_found", "code": "not_found"}}))
    assert w["producer"] == dict(EXPORT_PRODUCER)  # the slice can be unknown; who made the folder never is


def test_an_export_is_a_birth_so_the_line_is_its_own(tmp_path: Path, make_client: Callable[..., Client]) -> None:
    # A GET /world body carrying another folder's lines (keel keeps them at a folder upload, #477):
    # they name the maker of THAT folder, so this folder's own are written, as for source.
    theirs = {"tool": "azgaar-converter", "version": "0.4.0", "input": "azgaar-map"}
    their_source = {"server": None, "world": "w0", "at": "2026-10-01T00:00:00.000Z"}
    body = {"id": WID, "name": "W", "source": their_source, "producer": theirs}
    w, _ = _export(tmp_path, make_client, jresp(200, _me("owner", "owner")), world=body)
    assert w["producer"] == dict(EXPORT_PRODUCER)
    assert w["source"]["world"] == WID  # type: ignore[index]


def test_a_re_export_never_writes_over_a_folder_or_its_producer(
    tmp_path: Path, make_client: Callable[..., Client]
) -> None:
    out = tmp_path / "out"
    out.mkdir()
    theirs = {"tool": "atlas", "version": "1.70.0", "input": "bare"}
    world_json = out / "world.json"
    world_json.write_text(json.dumps({"id": WID, "name": "W", "producer": theirs}), encoding="utf-8")
    before = world_json.read_bytes()
    t = FakeTransport(handler=lambda *_: jresp(200, {"id": WID, "name": "W"}))
    with pytest.raises(FileExistsError):
        export_world(out, client=make_client(t, attempts=1))
    assert world_json.read_bytes() == before  # the maker's line stays the maker's


def test_a_tool_exporting_in_its_own_name_writes_its_own_line(
    tmp_path: Path, make_client: Callable[..., Client]
) -> None:
    keel = {"input": "server", "version": "2026.10.22", "tool": "keel"}  # any key order in, the spec's out
    w, _ = _export(tmp_path, make_client, jresp(200, _me("owner", "owner")), producer=keel)
    assert w["producer"] == keel and list(w["producer"]) == ["tool", "version", "input"]  # type: ignore[arg-type]
    other = {"tool": "papyrus", "version": "9", "input": "papyrus-scroll"}  # an input word is never refused
    w, _ = _export(tmp_path / "2", make_client, jresp(200, _me("owner", "owner")), producer=other)
    assert w["producer"] == other


def test_a_producer_of_the_wrong_shape_is_refused_before_anything_is_read(
    tmp_path: Path, make_client: Callable[..., Client]
) -> None:
    t = FakeTransport(handler=lambda *_: jresp(200, {"id": WID, "name": "W"}))
    for bad in (
        {"tool": "keel", "version": "1"},
        {"tool": "keel", "version": "1", "input": "server", "extra": "x"},
        {"tool": "keel", "version": 1, "input": "server"},
        {"tool": "keel", "version": "1", "input": " "},
    ):
        with pytest.raises(ValueError):
            export_world(tmp_path / "out", client=make_client(t, attempts=1), producer=bad)  # type: ignore[arg-type]
    assert t.calls == [] and not (tmp_path / "out").exists()


def test_an_override_never_replaces_a_line_a_folder_carries(tmp_path: Path, make_client: Callable[..., Client]) -> None:
    out = tmp_path / "out"
    out.mkdir()
    theirs = {"tool": "azgaar-converter", "version": "0.4.0", "input": "azgaar-map"}
    world_json = out / "world.json"
    world_json.write_text(json.dumps({"id": WID, "name": "W", "producer": theirs}), encoding="utf-8")
    before = world_json.read_bytes()
    t = FakeTransport(handler=lambda *_: jresp(200, {"id": WID, "name": "W"}))
    keel = {"tool": "keel", "version": "2026.10.22", "input": "server"}
    with pytest.raises(FileExistsError):
        export_world(out, client=make_client(t, attempts=1), producer=keel)
    assert world_json.read_bytes() == before
