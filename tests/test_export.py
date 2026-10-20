from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from conftest import FakeTransport, jresp

from onlyworlds import FORMAT_VERSION, Client, export_world, read_folder
from onlyworlds.export import exported_as
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
    assert list(w) == ["id", "name", "time_current", "public_read", "source", "exported_as", "format_version"]


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
) -> tuple[dict[str, object], FakeTransport]:
    def handler(method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> Response:
        path = urlparse(url).path.removeprefix("/api/v2/")
        assert method == "GET"
        if path == "world/":
            return jresp(200, {"id": WID, "name": "W", "public_read": False})
        if path == "me/":
            return me
        if path == f"character/{CID}/":
            assert character is not None, "the Character is read only for a guest"
            return character
        return jresp(200, {"data": [], "has_more": False, "next_cursor": None})

    t = FakeTransport(handler=handler)
    out = tmp_path / "out"
    export_world(out, client=make_client(t, attempts=1))
    return json.loads((out / "world.json").read_text(encoding="utf-8")), t


def test_world_json_says_where_it_came_from(tmp_path: Path, make_client: Callable[..., Client]) -> None:
    w, _ = _export(tmp_path, make_client, jresp(200, _me("owner", "owner")))
    assert w["format_version"] == "0.3.10" == FORMAT_VERSION
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
