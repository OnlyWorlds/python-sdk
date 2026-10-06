"""The push loop against a fake transport. No network, no live writes."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeTransport, jresp

from onlyworlds import Client, plan_push, push, verify_level, write_folder
from onlyworlds.http import Response

WORLD = {"id": "w0000000-0000-7000-8000-000000000000", "name": "W"}
C1 = "c0000000-0000-7000-8000-000000000001"
C2 = "c0000000-0000-7000-8000-000000000002"
P1 = "p0000000-0000-7000-8000-000000000001"

MakeClient = Callable[..., Client]


def wire_char(eid: str, name: str, **kw: Any) -> dict[str, Any]:
    return {
        "id": eid,
        "type": "character",
        "name": name,
        "description": "",
        "species": [],
        "birth_date": None,
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
        "change_seq": 7,
        **kw,
    }


def folders(
    tmp_path: Path, base: dict[str, list[dict[str, Any]]], edited: dict[str, list[dict[str, Any]]]
) -> tuple[Path, Path]:
    write_folder(tmp_path / "base", WORLD, base)
    write_folder(tmp_path / "edit", WORLD, edited)
    return tmp_path / "base", tmp_path / "edit"


def echo(overrides: Mapping[str, Any] | None = None) -> Callable[..., Response]:
    """A server that stores what it is sent (optionally storing something else for some fields)."""

    def handler(method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> Response:
        sent = json.loads(body) if body else {}
        stored = {**sent, **(overrides or {})}
        return jresp(200, {"id": url.rstrip("/").rsplit("/", 1)[-1], **stored, "change_seq": 99})

    return handler


def test_plan_is_field_level_and_skips_server_fields(tmp_path: Path) -> None:
    base, edit = folders(
        tmp_path,
        {"character": [wire_char(C1, "Gelon"), wire_char(C2, "Hieron")]},
        {
            "character": [
                wire_char(
                    C1,
                    "Gelon",
                    description="Tyrant of Gela",
                    change_seq=8,
                    updated_at="later",
                    local_updated_at="2026-09-28T00:00:00Z",
                ),
                wire_char(C2, "Hieron"),
            ]
        },
    )
    plan = plan_push(base, edit)
    assert [(p.type, p.id, p.fields) for p in plan.patches] == [("character", C1, {"description": "Tyrant of Gela"})]
    assert not plan.unmatched


def test_plan_cleared_shapes_and_string_empty_is_unset(tmp_path: Path) -> None:
    b = wire_char(C1, "G", description="old", species=["s1"], birth_date=5, x_tool="v", x_empty="")
    e = {k: v for k, v in b.items() if k not in ("description", "species", "birth_date", "x_tool")}
    e["x_empty"] = None  # extension: "" -> null IS a change
    b2 = wire_char(C2, "H", description="")
    e2 = wire_char(C2, "H", description=None)  # text: "" -> null is NOT a change (string-empty-is-unset)
    base, edit = folders(tmp_path, {"character": [b, b2]}, {"character": [e, e2]})
    plan = plan_push(base, edit)
    assert len(plan.patches) == 1
    assert plan.patches[0].fields == {
        "x_empty": None,
        "description": "",
        "species": [],
        "birth_date": None,
        "x_tool": None,
    }


def test_atlas_link_spelling_reads_as_bare(tmp_path: Path) -> None:
    wire_pin = {"id": P1, "type": "pin", "name": "Pin", "map": "m1", "x": 1}
    atlas_pin = {"id": P1, "type": "pin", "name": "Pin", "map_id": "m1", "x": 2, "server_updated_at": "t"}
    base, edit = folders(tmp_path, {"pin": [wire_pin]}, {"pin": [atlas_pin]})
    plan = plan_push(base, edit)
    assert [p.fields for p in plan.patches] == [{"x": 2}]  # map_id == map: no destructive map:null, no map_id sent


def test_unmatched_membership_refused(tmp_path: Path, make_client: MakeClient) -> None:
    base, edit = folders(tmp_path, {"character": [wire_char(C1, "A")]}, {"character": [wire_char(C2, "B")]})
    with pytest.raises(ValueError, match="membership"):
        push(base, edit, client=make_client(FakeTransport()), log_path=tmp_path / "log.jsonl")


def test_created_by_is_never_sent(tmp_path: Path) -> None:
    """keel drops created_by on a write but still bumps change_seq: sending it rewrites the element for nothing."""
    base, edit = folders(
        tmp_path,
        {"character": [wire_char(C1, "A", created_by="m-1"), wire_char(C2, "B", created_by="m-1")]},
        {"character": [wire_char(C1, "A"), wire_char(C2, "B2", created_by=None)]},
    )
    plan = plan_push(base, edit)
    assert [(p.id, p.fields) for p in plan.patches] == [(C2, {"name": "B2"})]


def test_generic_pair_is_sent_whole(tmp_path: Path) -> None:
    """keel 422s a PATCH that carries one half of a generic link ("must be set together")."""
    m1 = "m0000000-0000-7000-8000-000000000001"

    def pin(eid: str, et: str) -> dict[str, Any]:
        return {"id": P1, "type": "pin", "name": "p", "map": m1, "element_type": et, "element_id": eid}

    base, edit = folders(tmp_path, {"pin": [pin(C1, "character")]}, {"pin": [pin(C2, "character")]})
    assert plan_push(base, edit).patches[0].fields == {"element_id": C2, "element_type": "character"}
    base, edit = folders(tmp_path / "2", {"pin": [pin(C1, "character")]}, {"pin": [pin(C1, "creature")]})
    assert plan_push(base, edit).patches[0].fields == {"element_type": "creature", "element_id": C1}


@pytest.mark.parametrize(
    ("status", "code"),
    [(401, "invalid_credentials"), (401, "key_revoked"), (429, "rate_limited"), (403, "permission_error")],
)
def test_a_refused_key_stops_the_run(tmp_path: Path, make_client: MakeClient, status: int, code: str) -> None:
    """A wrong PIN on every patch would lock the key (10 failures, 15 minutes) for every tool that uses it."""
    chars = [wire_char(f"c0000000-0000-7000-8000-00000000000{i}", "A") for i in range(5)]
    edited = [{**c, "name": "B"} for c in chars]
    base, edit = folders(tmp_path, {"character": chars}, {"character": edited})
    t = FakeTransport(handler=lambda *_: jresp(status, {"error": {"code": code}}))
    log = tmp_path / "log.jsonl"
    res = push(base, edit, client=make_client(t), log_path=log, workers=1)
    assert len(t.calls) == 1 and res.attempted == 1 and res.aborted and str(status) in res.aborted
    t2 = FakeTransport(handler=echo())
    assert push(base, edit, client=make_client(t2), log_path=log, workers=1).ok == 5  # nothing was marked done


def test_not_author_does_not_stop_the_run(tmp_path: Path, make_client: MakeClient) -> None:
    base, edit = folders(
        tmp_path, {"character": [wire_char(C1, "A"), wire_char(C2, "A")]},
        {"character": [wire_char(C1, "B"), wire_char(C2, "B")]},
    )  # fmt: skip
    t = FakeTransport(script=[jresp(403, {"error": {"code": "not_author"}})], handler=echo())
    res = push(base, edit, client=make_client(t), log_path=tmp_path / "log.jsonl", workers=1)
    assert (res.ok, len(res.failed), res.aborted) == (1, 1, None)


def test_429_then_success_honors_retry_after(tmp_path: Path, make_client: MakeClient, sleeps: list[float]) -> None:
    base, edit = folders(tmp_path, {"character": [wire_char(C1, "A")]}, {"character": [wire_char(C1, "B")]})
    t = FakeTransport(script=[jresp(429, {"error": {}}, {"Retry-After": "7"})], handler=echo())
    res = push(base, edit, client=make_client(t), log_path=tmp_path / "log.jsonl", workers=1)
    assert (res.ok, res.retries, res.failed) == (1, 1, [])
    assert sleeps == [7.0]
    call = t.calls[-1]
    assert call.method == "PATCH" and call.url == f"https://www.onlyworlds.com/api/v2/character/{C1}/"
    assert call.body == {"name": "B"}
    assert call.headers["API-Key"] == "ow_w_testkey" and call.headers["API-Pin"] == "1234"
    assert call.headers["User-Agent"].startswith("onlyworlds-py/")


def test_503_server_busy_then_exception_then_success(
    tmp_path: Path, make_client: MakeClient, sleeps: list[float]
) -> None:
    base, edit = folders(tmp_path, {"character": [wire_char(C1, "A")]}, {"character": [wire_char(C1, "B")]})
    busy = jresp(503, {"error": {"code": "server_busy"}}, {"retry-after": "5"})
    t = FakeTransport(script=[busy, TimeoutError("read timed out")], handler=echo())
    res = push(base, edit, client=make_client(t), log_path=tmp_path / "log.jsonl", workers=1)
    assert res.ok == 1 and res.retries == 2
    assert sleeps == [5.0, 2.0]  # Retry-After honored; then exponential backoff (base 1 * 2**1)
    rec = json.loads((tmp_path / "log.jsonl").read_text(encoding="utf-8"))
    assert rec["retry_reasons"] == ["503", "TimeoutError: read timed out"]


def test_gives_up_and_logs_failure(tmp_path: Path, make_client: MakeClient) -> None:
    base, edit = folders(tmp_path, {"character": [wire_char(C1, "A")]}, {"character": [wire_char(C1, "B")]})
    t = FakeTransport(handler=lambda *a: jresp(502, {}))
    res = push(base, edit, client=make_client(t, attempts=3), log_path=tmp_path / "log.jsonl")
    assert res.ok == 0 and len(res.failed) == 1 and len(t.calls) == 3
    assert res.failed[0]["code"] == 502 and "gave up after 2 retries" in res.failed[0]["error"]


def test_4xx_is_not_retried(tmp_path: Path, make_client: MakeClient) -> None:
    base, edit = folders(tmp_path, {"character": [wire_char(C1, "A")]}, {"character": [wire_char(C1, "B")]})
    t = FakeTransport(handler=lambda *a: jresp(422, {"error": {"param": "name"}}))
    res = push(base, edit, client=make_client(t), log_path=tmp_path / "log.jsonl")
    assert len(t.calls) == 1 and res.failed[0]["code"] == 422 and "param" in res.failed[0]["error"]


def test_mismatch_is_a_failure_and_is_retried_on_rerun(tmp_path: Path, make_client: MakeClient) -> None:
    base, edit = folders(
        tmp_path,
        {"character": [wire_char(C1, "A", birth_date=None)]},
        {"character": [wire_char(C1, "A", birth_date=12)]},
    )
    t = FakeTransport(handler=echo({"birth_date": 1}))  # the server stored something else
    log = tmp_path / "log.jsonl"
    res = push(base, edit, client=make_client(t), log_path=log)
    assert res.ok == 0 and res.failed[0]["mismatch_fields"] == ["birth_date"]
    t2 = FakeTransport(handler=echo())
    res2 = push(base, edit, client=make_client(t2), log_path=log)
    assert res2.already_done == 0 and res2.ok == 1  # a mismatch never counts as landed


def test_rerun_skips_what_landed_but_not_a_new_edit(tmp_path: Path, make_client: MakeClient) -> None:
    base, edit = folders(
        tmp_path,
        {"character": [wire_char(C1, "A"), wire_char(C2, "B")]},
        {"character": [wire_char(C1, "A2"), wire_char(C2, "B2")]},
    )
    log = tmp_path / "log.jsonl"
    t = FakeTransport(script=[jresp(200, {"name": "A2"})], handler=lambda *a: jresp(500, {}))
    res = push(base, edit, client=make_client(t, attempts=1), log_path=log, workers=1)
    assert (res.ok, len(res.failed)) == (1, 1)

    t2 = FakeTransport(handler=echo())
    res2 = push(base, edit, client=make_client(t2), log_path=log)
    assert (res2.already_done, res2.attempted, res2.ok) == (1, 1, 1)
    assert [c.url.rsplit("/", 2)[-2] for c in t2.calls] == [C2]

    # the same element edited again: a different patch, so it is sent again
    edit3 = tmp_path / "edit3"
    write_folder(edit3, WORLD, {"character": [wire_char(C1, "A3"), wire_char(C2, "B2")]})
    t3 = FakeTransport(handler=echo())
    res3 = push(base, edit3, client=make_client(t3), log_path=log)
    assert (res3.already_done, res3.ok) == (1, 1)
    assert t3.calls[0].body == {"name": "A3"}


def test_reads_skelds_original_log_format(tmp_path: Path, make_client: MakeClient) -> None:
    base, edit = folders(tmp_path, {"character": [wire_char(C1, "A")]}, {"character": [wire_char(C1, "B")]})
    log = tmp_path / "log.jsonl"
    log.write_text(json.dumps({"id": C1, "type": "character", "code": 200, "mismatch": False, "retries": 0}) + "\n")
    res = push(base, edit, client=make_client(FakeTransport()), log_path=log)
    assert res.already_done == 1 and res.attempted == 0


def test_dry_run_and_key_pin_parameters(tmp_path: Path) -> None:
    base, edit = folders(tmp_path, {"character": [wire_char(C1, "A")]}, {"character": [wire_char(C1, "B")]})
    res = push(base, edit, api_key="k", pin="p", log_path=tmp_path / "log.jsonl", dry_run=True)
    assert res.planned == 1 and res.attempted == 0 and not (tmp_path / "log.jsonl").exists()
    with pytest.raises(ValueError, match="client"):
        push(base, edit, log_path=tmp_path / "log.jsonl")


def test_client_never_sends_world() -> None:
    c = Client("k", transport=FakeTransport())
    with pytest.raises(ValueError, match="world"):
        c.request("PATCH", "character/x/", {"world": "w", "name": "n"})
    assert "k" not in repr(c)


def test_verify_level(tmp_path: Path) -> None:
    base, edit = folders(tmp_path, {"character": [wire_char(C1, "A")]}, {"character": [wire_char(C1, "B")]})
    assert len(verify_level(base, edit).patches) == 1
    fresh = tmp_path / "fresh"
    write_folder(fresh, WORLD, {"character": [wire_char(C1, "B", change_seq=100, updated_at="now")]})
    assert verify_level(fresh, edit).patches == []
