"""Known-of stubs (folder format v0.3.10 §4.4; keel PR 113, B16): written as they are, read as
known of, never pushed or written back, and whole again once they arrive whole. Both ways each."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
from conftest import FakeTransport, jresp

from onlyworlds import (
    FORMAT_VERSION,
    KNOWN_OF_KEEPS,
    Client,
    export_world,
    is_known_of,
    plan_push,
    push,
    read_folder,
    write_folder,
)
from onlyworlds.http import Response

MakeClient = Callable[..., Client]
WORLD = {"id": "w0000000-0000-7000-8000-000000000000", "name": "W"}
DEV = "c0000000-0000-7000-8000-00000000000d"
MARA = "c0000000-0000-7000-8000-00000000000a"
KEPT = {"id", "type", "name", "description", "supertype", "subtype", "image_url"} | {
    "created_at",
    "updated_at",
    "change_seq",
}


def whole_dev(**kw: Any) -> dict[str, Any]:
    return {
        "id": DEV, "type": "character", "name": "Dev", "description": "Dev desc", "supertype": "Ferryman",
        "subtype": "", "image_url": None, "physicality": "zzphys", "location": "l1", "friends": [MARA],
        "STR": 14, "created_at": "2026-10-20T00:00:00Z", "updated_at": "2026-10-20T01:00:00Z",
        "change_seq": 9, "created_by": "m-1", "changed_by": "m-1", "changed_via": "api", "x_secret": "zzext",
        **kw,
    }  # fmt: skip


def stub_dev() -> dict[str, Any]:
    """Dev as keel serves him to a player who knows of him: the kept keys, every other field unset."""
    return {
        "id": DEV, "type": "character", "name": "Dev", "description": "Dev desc", "supertype": "Ferryman",
        "subtype": "", "image_url": None, "physicality": "", "location": None, "friends": [], "STR": None,
        "created_at": "2026-10-20T00:00:00Z", "updated_at": "2026-10-20T01:00:00Z", "change_seq": 9,
        "created_by": None, "changed_by": None, "changed_via": None, "known_of": True,
    }  # fmt: skip


def mara(**kw: Any) -> dict[str, Any]:
    return {"id": MARA, "type": "character", "name": "Mara", "description": "", "friends": [DEV], **kw}


def dev_file(root: Path) -> dict[str, Any]:
    (path,) = [p for p in (root / "elements" / "character").iterdir() if p.name.startswith("dev--")]
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_the_kept_keys_are_keels() -> None:
    assert frozenset(KEPT) == KNOWN_OF_KEEPS
    assert FORMAT_VERSION == "0.3.10"


def test_is_known_of_only_for_true() -> None:
    assert is_known_of(stub_dev()) is True
    for body in (whole_dev(), whole_dev(known_of=False), whole_dev(known_of="true"), whole_dev(known_of=1), {}):
        assert is_known_of(body) is False, body


# --- rule 1: a writer writes a stub as it is -------------------------------------------------


def test_a_stub_is_written_with_known_of_and_only_its_kept_keys(tmp_path: Path) -> None:
    write_folder(tmp_path / "w", WORLD, {"character": [stub_dev(), mara()]})
    on_disk = dev_file(tmp_path / "w")
    assert on_disk["known_of"] is True
    assert set(on_disk) == KEPT | {"known_of"}  # no "", null or [] for the unset fields
    assert list(on_disk)[-1] == "known_of" and on_disk["supertype"] == "Ferryman" and on_disk["subtype"] == ""


def test_a_whole_element_is_written_untouched(tmp_path: Path) -> None:
    write_folder(tmp_path / "w", WORLD, {"character": [whole_dev(location=None, friends=[])]})
    on_disk = dev_file(tmp_path / "w")
    assert on_disk == whole_dev(location=None, friends=[])  # its unset fields and extensions kept
    assert "known_of" not in on_disk


def test_export_writes_a_served_stub_as_a_stub(tmp_path: Path, make_client: MakeClient) -> None:
    def handler(method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> Response:
        path = urlparse(url).path.removeprefix("/api/v2/")
        if path == "world/":
            return jresp(200, WORLD)
        if path == "me/":
            return jresp(404, {"error": {"code": "not_found"}})
        if path == "character/":
            return jresp(200, {"data": [mara(), stub_dev()], "has_more": False, "next_cursor": None})
        return jresp(200, {"data": [], "has_more": False, "next_cursor": None})

    export_world(tmp_path / "out", client=make_client(FakeTransport(handler=handler)))
    assert set(dev_file(tmp_path / "out")) == KEPT | {"known_of"}
    f = read_folder(tmp_path / "out")
    assert f.known_of == [DEV] and not f.elements[MARA].known_of


# --- rule 2: a reader treats it as known of --------------------------------------------------


def test_the_reader_flags_a_stub_and_fills_in_nothing(tmp_path: Path) -> None:
    write_folder(tmp_path / "w", WORLD, {"character": [stub_dev(), mara()]})
    f = read_folder(tmp_path / "w")
    assert f.elements[DEV].known_of is True and f.known_of == [DEV]
    assert "physicality" not in f.elements[DEV].body and "friends" not in f.elements[DEV].body
    assert f.elements[MARA].known_of is False


def test_the_reader_reads_a_whole_element_as_whole(tmp_path: Path) -> None:
    write_folder(tmp_path / "w", WORLD, {"character": [whole_dev(), whole_dev(id=MARA, name="Mara", known_of=False)]})
    f = read_folder(tmp_path / "w")
    assert f.known_of == [] and not f.elements[DEV].known_of and not f.elements[MARA].known_of


# --- rule 3: a stub is never pushed ----------------------------------------------------------


def _folders(tmp_path: Path, base: list[dict[str, Any]], edited: list[dict[str, Any]]) -> tuple[Path, Path]:
    write_folder(tmp_path / "base", WORLD, {"character": base})
    write_folder(tmp_path / "edit", WORLD, {"character": edited})
    return tmp_path / "base", tmp_path / "edit"


def test_a_stub_in_the_folder_is_never_pushed(tmp_path: Path, make_client: MakeClient) -> None:
    # The baseline holds Dev whole; the folder holds him as a stub (a player's copy). A diff
    # would send every field the stub lacks as cleared: the plan sends none of them.
    base, edit = _folders(tmp_path, [whole_dev(), mara()], [stub_dev(), mara(description="swims")])
    plan = plan_push(base, edit)
    assert [(p.id, p.fields) for p in plan.patches] == [(MARA, {"description": "swims"})]
    assert plan.known_of == [DEV] and not plan.unmatched
    t = FakeTransport(handler=lambda m, u, h, b: jresp(200, {"id": MARA, **json.loads(b or b"{}")}))
    result = push(base, edit, client=make_client(t), log_path=tmp_path / "log.jsonl")
    assert result.known_of == [DEV] and result.ok == 1
    assert [c.url.rstrip("/").rsplit("/", 1)[-1] for c in t.calls] == [MARA]


def test_a_stub_in_the_baseline_is_not_diffed_and_a_stub_alone_is_not_unmatched(tmp_path: Path) -> None:
    base, edit = _folders(tmp_path, [stub_dev(), mara()], [whole_dev(), mara()])
    plan = plan_push(base, edit)
    assert plan.patches == [] and plan.known_of == [DEV]
    base, edit = _folders(tmp_path / "2", [mara()], [stub_dev(), mara()])
    plan = plan_push(base, edit)
    assert plan.known_of == [DEV] and plan.only_in_folder == [] and not plan.unmatched


def test_a_whole_element_still_pushes(tmp_path: Path) -> None:
    base, edit = _folders(tmp_path, [whole_dev()], [whole_dev(physicality="tall", known_of=False)])
    plan = plan_push(base, edit)
    assert [(p.id, p.fields) for p in plan.patches] == [(DEV, {"physicality": "tall"})]  # known_of never sent
    assert plan.known_of == []


def test_the_client_refuses_a_stub_on_every_element_write(make_client: MakeClient) -> None:
    t = FakeTransport()
    c = make_client(t)
    with pytest.raises(ValueError, match="known-of stub"):
        c.upsert("character", DEV, stub_dev())
    with pytest.raises(ValueError, match="known-of stub"):
        c.patch("character", DEV, stub_dev())
    with pytest.raises(ValueError, match="known-of stub"):
        c.create("character", stub_dev())
    with pytest.raises(ValueError, match=r"items\[1\]"):
        c.bulk([{"type": "character", "element": mara()}, {"type": "character", "element": stub_dev()}])
    assert t.calls == []


def test_a_read_body_echoed_into_a_write_sends_no_known_of(make_client: MakeClient) -> None:
    t = FakeTransport(handler=lambda *a: jresp(200, {"id": DEV, "name": "Dev"}))
    c = make_client(t)
    for body in (whole_dev(), whole_dev(known_of=False)):
        c.upsert("character", DEV, body)
        c.patch("character", DEV, body)
    for call in t.calls:
        assert call.body is not None and "known_of" not in call.body and call.body["physicality"] == "zzphys"


# --- rule 4: a stub that later arrives whole is written whole --------------------------------


def test_a_stub_that_arrives_whole_is_written_whole(tmp_path: Path) -> None:
    write_folder(tmp_path / "w", WORLD, {"character": [stub_dev(), whole_dev()]})  # a walk: stub, then whole
    on_disk = dev_file(tmp_path / "w")
    assert on_disk == whole_dev() and "known_of" not in on_disk
    # The other way (whole, then a stub: the grant went) is the last body too: a stub.
    write_folder(tmp_path / "x", WORLD, {"character": [whole_dev(), stub_dev()]})
    assert set(dev_file(tmp_path / "x")) == KEPT | {"known_of"}
