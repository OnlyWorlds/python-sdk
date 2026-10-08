"""The typed client calls: what each sends, what it returns, and how it fails. Scripted HTTP, no network."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from conftest import FakeTransport, jresp

from onlyworlds import ApiError, Client, Response, parse_retry_after, sanitize_payload, uuid7

ID = "018f0000-0000-7000-8000-000000000001"
V7 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
MakeClient = Callable[..., Client]


def env(status: int, etype: str, code: str, headers: dict[str, str] | None = None) -> Any:
    body = {"error": {"type": etype, "code": code, "message": code, "param": None, "doc_url": f"https://x/{code}"}}
    return jresp(status, body, headers)


# --- what each call sends ----------------------------------------


def test_each_call_uses_its_verb_path_and_no_world(make_client: MakeClient) -> None:
    t = FakeTransport(handler=lambda *a: jresp(200, {"id": ID, "name": "K"}))
    c = make_client(t)
    c.get("character", ID)
    c.upsert("character", ID, {"name": "K"})
    c.patch("character", ID, {"name": "K2"})
    c.edit_links("character", ID, "friends", add=["a"], remove=["b"])
    assert [(x.method, x.url.removeprefix("https://www.onlyworlds.com/api/v2/")) for x in t.calls] == [
        ("GET", f"character/{ID}/"),
        ("PUT", f"character/{ID}/"),
        ("PATCH", f"character/{ID}/"),
        ("POST", f"character/{ID}/links/friends"),
    ]
    assert t.calls[3].body == {"add": ["a"], "remove": ["b"]}
    assert t.calls[0].headers["API-Key"] == "ow_w_testkey" and t.calls[0].headers["API-Pin"] == "1234"


def test_delete_is_204_and_returns_none(make_client: MakeClient) -> None:
    t = FakeTransport(script=[Response(204, b"", {})])
    assert make_client(t).delete("character", ID) is None
    assert (t.calls[0].method, t.calls[0].url.endswith(f"character/{ID}/")) == ("DELETE", True)


def test_writes_strip_what_the_api_rejects_and_keep_extensions(make_client: MakeClient) -> None:
    read_body = {
        "id": ID, "name": "K", "type": "character", "world": "w", "created_at": "a", "updated_at": "b",
        "change_seq": 4, "created_by": None, "x_tool_state": {"keep": [1]}, "atlas_note": "n",
    }  # fmt: skip
    t = FakeTransport(handler=lambda *a: jresp(200, {"id": ID, "name": "K"}))
    c = make_client(t)
    c.upsert("character", ID, read_body)
    c.patch("character", ID, read_body)
    for call in t.calls:
        assert set(call.body) == {"id", "name", "created_by", "x_tool_state", "atlas_note"}
    assert sanitize_payload({"world": 1, "name": "n"}) == {"name": "n"}


def test_list_query_is_built_not_concatenated(make_client: MakeClient) -> None:
    t = FakeTransport(script=[jresp(200, {"data": [], "has_more": False, "next_cursor": None})])
    make_client(t).list_page(
        "character", limit=5, cursor="a b&c=1", expand=["friends", "location"], fields=["name"],
        filter={"name__icontains": "x y", "supertype": "s"},
    )  # fmt: skip
    q = t.calls[0].url.split("?", 1)[1]
    assert q == "limit=5&cursor=a%20b%26c%3D1&expand=friends,location&fields=name&name__icontains=x%20y&supertype=s"


def test_default_page_size_is_the_clients(make_client: MakeClient) -> None:
    t = FakeTransport(script=[jresp(200, {"data": [], "has_more": False, "next_cursor": None})])
    make_client(t).list_page("map")
    assert t.calls[0].url.endswith("map/?limit=100")


def test_iter_elements_follows_the_cursor_and_refuses_a_missing_one(make_client: MakeClient) -> None:
    pages = [
        jresp(200, {"data": [{"id": "1"}], "has_more": True, "next_cursor": "C1"}),
        jresp(200, {"data": [{"id": "2"}], "has_more": False, "next_cursor": None}),
    ]
    t = FakeTransport(script=list(pages))
    assert [e["id"] for e in make_client(t).iter_elements("character")] == ["1", "2"]
    assert t.calls[1].url.endswith("cursor=C1") or "cursor=C1" in t.calls[1].url
    broken = FakeTransport(script=[jresp(200, {"data": [], "has_more": True, "next_cursor": None})])
    with pytest.raises(ValueError, match="has_more without next_cursor"):
        list(make_client(broken).iter_elements("character"))


def test_path_segments_are_checked(make_client: MakeClient) -> None:
    c = make_client(FakeTransport())
    for call in (
        lambda: c.get("character/../world", ID),
        lambda: c.get("character", "x/y"),
        lambda: c.get("Character", ID),
        lambda: c.edit_links("character", ID, "a?b", add=[]),
        lambda: c.list_page("a b"),
    ):
        with pytest.raises(ValueError, match="path segment"):
            call()


# --- create, ids and idempotency ----------------------------------------


def test_create_mints_a_v7_id_only_when_missing_and_sends_an_idempotency_key(make_client: MakeClient) -> None:
    t = FakeTransport(handler=lambda *a: jresp(201, {"id": ID, "name": "K"}))
    c = make_client(t)
    c.create("character", {"name": "K"})
    c.create("character", {"name": "K", "id": "my-own-id"}, idempotency_key="k-1")
    assert V7.match(t.calls[0].body["id"])
    assert t.calls[1].body["id"] == "my-own-id"
    assert t.calls[1].headers["Idempotency-Key"] == "k-1"
    assert len(t.calls[0].headers["Idempotency-Key"]) == 36


def test_a_retried_create_repeats_the_same_id_and_key(make_client: MakeClient, sleeps: list[float]) -> None:
    t = FakeTransport(
        script=[env(503, "api_error", "server_busy", {"Retry-After": "5"})], handler=lambda *a: jresp(201, {"id": "x"})
    )
    make_client(t).create("character", {"name": "K"})
    assert len(t.calls) == 2 and sleeps == [5.0]
    assert t.calls[0].body["id"] == t.calls[1].body["id"]
    assert t.calls[0].headers["Idempotency-Key"] == t.calls[1].headers["Idempotency-Key"]


def test_uuid7_layout_and_order() -> None:
    a, b = uuid7(1_700_000_000_000), uuid7(1_700_000_000_001)
    assert V7.match(a) and V7.match(b) and a[:13] < b[:13]
    assert uuid7(0, rand=lambda n: b"\xff" * n).startswith("00000000-0000-7")
    with pytest.raises(ValueError):
        uuid7(-1)
    with pytest.raises(ValueError):
        uuid7(2**48)


# --- bulk and changes ----------------------------------------


def test_bulk_body_flag_key_and_replay(make_client: MakeClient) -> None:
    ok = {"errors": True, "items": [{"status": 201, "id": "a"}, {"status": 409, "error": {"code": "id_conflict"}}]}
    t = FakeTransport(script=[jresp(200, ok, {"idempotent-replay": "true"}), jresp(200, ok)])
    c = make_client(t)
    r = c.bulk([{"type": "character", "element": {"name": "A", "type": "character", "created_at": "x"}}], atomic=True,
               idempotency_key="b-1")  # fmt: skip
    assert r.errors and r.was_replay and r.items[1]["error"]["code"] == "id_conflict"
    sent = t.calls[0].body
    assert uuid.UUID(sent["items"][0]["element"].pop("id")).version == 5  # derived from your key "b-1"
    assert sent == {"items": [{"type": "character", "element": {"name": "A"}}], "atomic": True}
    assert t.calls[0].headers["Idempotency-Key"] == "b-1" and t.calls[0].url.endswith("/bulk/")
    assert c.bulk([]).was_replay is False


def test_bulk_resend_after_a_lost_answer_names_the_same_elements(make_client: MakeClient) -> None:
    """keel stores a bulk answer only after the batch commits: a 502 after the commit replays
    nothing, so an id-less item resent as id-less would be created twice. Ids given are kept."""
    ok = {"errors": False, "items": [{"status": 201}, {"status": 201}]}
    t = FakeTransport(script=[jresp(502, {}), jresp(200, ok)])
    item = {"name": "A"}
    make_client(t).bulk([{"type": "character", "element": item}, {"type": "character", "element": {"id": "c-1"}}])
    first, second = (call.body["items"] for call in t.calls)
    assert first == second and V7.match(first[0]["element"]["id"]) and first[1]["element"]["id"] == "c-1"
    assert item == {"name": "A"}  # the caller's dict is not touched


def test_your_key_with_the_same_elements_sends_the_same_body(make_client: MakeClient) -> None:
    """Calling again with your own Idempotency-Key must replay, not 409 idempotency_error (staging, 10-06)."""
    ok = {"errors": False, "items": [{"status": 201}, {"status": 201}]}
    t = FakeTransport(
        handler=lambda *_: jresp(200, ok) if _[0] == "POST" and _[1].endswith("/bulk/") else jresp(201, {})
    )
    c = make_client(t)
    items = [{"type": "character", "element": {"name": "A"}}, {"type": "character", "element": {"name": "B"}}]
    c.bulk(items, idempotency_key="k-1")
    c.bulk(items, idempotency_key="k-1")
    c.bulk(items, idempotency_key="k-2")
    c.create("character", {"name": "A"}, idempotency_key="k-1")
    c.create("character", {"name": "A"}, idempotency_key="k-1")
    one, two, other = (call.body["items"] for call in t.calls[:3])
    assert one == two and one[0]["element"]["id"] != one[1]["element"]["id"]
    assert other[0]["element"]["id"] != one[0]["element"]["id"]
    assert t.calls[3].body == t.calls[4].body


def test_rate_limited_429_is_never_retried(make_client: MakeClient, sleeps: list[float]) -> None:
    """keel's only v2 429 is the failed-PIN throttle: each retry is one more failure toward a locked key."""
    t = FakeTransport(script=[jresp(429, {"error": {"code": "rate_limited"}}, {"Retry-After": "900"})])
    with pytest.raises(ApiError) as e:
        make_client(t).get("character", "c-1")
    assert e.value.code == "rate_limited" and len(t.calls) == 1 and sleeps == []


def test_bulk_without_items_is_an_error(make_client: MakeClient) -> None:
    with pytest.raises(ValueError, match="no items"):
        make_client(FakeTransport(script=[jresp(200, {"errors": False})])).bulk([])


def test_changes_walk_pages_to_the_tail_and_remembers_the_cursor(make_client: MakeClient) -> None:
    t = FakeTransport(
        script=[
            jresp(200, {"cursor": "C1", "changes": [{"op": "upsert", "id": "1"}], "has_more": True, "head": 9}),
            jresp(200, {"cursor": "C2", "changes": [{"op": "delete", "id": "2"}], "has_more": False, "head": 9}),
        ]
    )
    walk = make_client(t).walk_changes("C0", limit=1)
    assert [op["id"] for op in walk] == ["1", "2"]
    assert (walk.cursor, walk.head, walk.done) == ("C2", 9, True)
    assert "since=C0" in t.calls[0].url and "since=C1" in t.calls[1].url and "limit=1" in t.calls[0].url


def test_a_feed_that_says_more_without_moving_is_refused(make_client: MakeClient) -> None:
    stuck = jresp(200, {"cursor": "C0", "changes": [], "has_more": True, "head": 1})
    with pytest.raises(ValueError, match="no new cursor"):
        list(make_client(FakeTransport(script=[stuck])).walk_changes("C0"))


# --- errors ----------------------------------------


@pytest.mark.parametrize(
    ("status", "etype", "code", "flag"),
    [
        (409, "invalid_request", "id_conflict", "is_id_conflict"),
        (409, "idempotency_error", "idempotency_error", "is_idempotency_conflict"),
        (403, "permission_error", "not_author", "is_not_author"),
        (403, "permission_error", "owner_only", "is_owner_only"),
        (503, "api_error", "server_busy", "is_busy"),
        (401, "authentication_error", "key_revoked", "is_auth_error"),
        (422, "invalid_request", "invalid_field", "is_validation_error"),
    ],
)
def test_each_error_has_its_own_flag_and_no_other(
    make_client: MakeClient, status: int, etype: str, code: str, flag: str
) -> None:
    flags = [
        "is_id_conflict",
        "is_idempotency_conflict",
        "is_not_author",
        "is_owner_only",
        "is_busy",
        "is_auth_error",
        "is_validation_error",
    ]
    t = FakeTransport(script=[env(status, etype, code)])
    with pytest.raises(ApiError) as caught:
        make_client(t, attempts=1).patch("character", ID, {"name": "K"})
    e = caught.value
    assert (e.status, e.type, e.code) == (status, etype, code) and e.doc_url == f"https://x/{code}"
    assert [f for f in flags if getattr(e, f)] == [flag]


def test_flat_and_unparseable_envelopes(make_client: MakeClient) -> None:
    flat = ApiError("GET", "x", jresp(403, {"code": "not_author", "type": "permission_error", "param": "name"}))
    assert (flat.code, flat.param, flat.is_not_author) == ("not_author", "name", True)
    bare = ApiError("GET", "x", jresp(403, "forbidden"))
    assert (bare.code, bare.is_not_author, bare.is_auth_error) == (None, False, False)
    html = ApiError("GET", "x", Response(502, b"<html>bad gateway</html>", {}))
    assert html.code is None and "502" in str(html)
    owner_only = ApiError("GET", "x", jresp(403, {"error": {"code": "owner_only"}}))
    assert (owner_only.is_not_author, owner_only.is_owner_only) == (False, True)


def test_a_409_without_a_code_is_neither_conflict() -> None:
    e = ApiError("POST", "x", jresp(409, "conflict"))
    assert (e.is_id_conflict, e.is_idempotency_conflict) == (False, False)


def test_retry_after_is_strict() -> None:
    assert parse_retry_after("5") == 5.0 and parse_retry_after(" 30 ") == 30.0
    for bad in ["1.5", "-1", "+5", "5.0", "soon", "", None]:
        assert parse_retry_after(bad) is None, bad
    assert parse_retry_after("Wed, 21 Oct 2015 07:28:30 GMT", now=1445412510 - 30) == 30.0
    assert parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT", now=1445412480 + 100) == 0.0
    e = ApiError("GET", "x", env(429, "rate_limited", "rate_limited", {"Retry-After": "7"}))
    assert e.retry_after == 7.0
    assert ApiError("GET", "x", env(429, "rate_limited", "rate_limited", {"Retry-After": "1.5"})).retry_after is None


# --- Review findings B1-B5 and the guest feed (2026-10-06) ---------------------------------


@pytest.mark.parametrize(
    ("etype", "field", "value"),
    [
        ("pin", "x", 2.5),
        ("pin", "x", True),
        ("pin", "x", "3"),
        ("character", "description", ["a"]),
        ("character", "name", 7),
    ],
)
def test_a_value_keel_would_store_as_another_is_refused_before_sending(
    make_client: MakeClient, etype: str, field: str, value: Any
) -> None:
    """keel stores int(2.5) == 2 and the repr of a list on a text field, both with a 200 (lenient by design)."""
    t = FakeTransport()
    c = make_client(t)
    for write in (
        lambda: c.create(etype, {"name": "n", field: value}),
        lambda: c.upsert(etype, "e-1", {"name": "n", field: value}),
        lambda: c.patch(etype, "e-1", {field: value}),
        lambda: c.bulk([{"type": etype, "element": {"name": "n", field: value}}]),
    ):
        with pytest.raises(ValueError, match=f"{etype}.{field}"):
            write()
    assert t.calls == []


def test_integral_floats_none_and_extensions_pass_the_kind_check(make_client: MakeClient) -> None:
    t = FakeTransport(handler=lambda *_: jresp(200, {"id": "p-1"}))
    make_client(t).patch("pin", "p-1", {"x": 3.0, "y": None, "description": "", "x_tool_n": 2.5})
    assert t.calls[0].body == {"x": 3.0, "y": None, "description": "", "x_tool_n": 2.5}


def test_a_retried_create_that_already_landed_is_read_back(make_client: MakeClient) -> None:
    """The first try committed, its answer was lost, the retry beat keel's replay record: 409 id_conflict."""
    conflict = jresp(409, {"error": {"code": "id_conflict"}})
    stored = {"id": "c-1", "name": "A", "description": "", "type": "character"}
    t = FakeTransport(script=[jresp(502, {}), conflict, jresp(200, stored)])
    assert make_client(t).create("character", {"id": "c-1", "name": "A", "description": None}) == stored
    assert [c.method for c in t.calls] == ["POST", "POST", "GET"]

    other = {**stored, "name": "B"}  # someone else's element under that id: still a conflict
    t = FakeTransport(script=[jresp(502, {}), conflict, jresp(200, other)])
    with pytest.raises(ApiError) as e:
        make_client(t).create("character", {"id": "c-1", "name": "A"})
    assert e.value.is_id_conflict

    t = FakeTransport(script=[conflict])  # no retry: the id was taken before this call
    with pytest.raises(ApiError):
        make_client(t).create("character", {"id": "c-1", "name": "A"})
    assert len(t.calls) == 1


@pytest.mark.parametrize(("status", "tries"), [(500, 2), (501, 1), (502, 3), (503, 3), (504, 3), (505, 1)])
def test_which_5xx_are_retried(make_client: MakeClient, status: int, tries: int) -> None:
    """keel's 500 is an unhandled exception, almost always deterministic: once at most."""
    t = FakeTransport(handler=lambda *_: jresp(status, {}))
    with pytest.raises(ApiError):
        make_client(t, attempts=3).get("character", "c-1")
    assert len(t.calls) == tries


def test_permission_and_resync_predicates() -> None:
    def err(status: int, code: str) -> ApiError:
        return ApiError("GET", "x", jresp(status, {"error": {"type": "x", "code": code}}))

    assert err(403, "permission_error").is_permission_error and not err(403, "not_author").is_permission_error
    assert err(409, "resync_required").is_resync_required and not err(409, "id_conflict").is_resync_required


def test_patch_world_takes_back_a_get_world_body_and_a_folder_spelling(make_client: MakeClient) -> None:
    t = FakeTransport(handler=lambda *_: jresp(200, {"id": "w"}))
    body = {"id": "w", "name": "W", "public_read": True, "created_at": "a", "updated_at": "b", "time_current": 5}
    make_client(t).patch_world(body)
    assert t.calls[0].body == {"name": "W", "time_range_current": 5}
