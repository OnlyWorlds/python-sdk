"""The typed client calls: what each sends, what it returns, and how it fails. Scripted HTTP, no network."""

from __future__ import annotations

import re
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
    assert t.calls[0].body == {"items": [{"type": "character", "element": {"name": "A"}}], "atomic": True}
    assert t.calls[0].headers["Idempotency-Key"] == "b-1" and t.calls[0].url.endswith("/bulk/")
    assert c.bulk([]).was_replay is False


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
    assert ApiError("GET", "x", jresp(403, {"error": {"code": "owner_only"}})).is_not_author is False


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
