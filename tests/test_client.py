"""The typed client calls: what each sends, what it returns, and how it fails. Scripted HTTP, no network."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from conftest import FakeTransport, jresp

from onlyworlds import ApiError, Client, PreconditionFailed, Response, parse_retry_after, sanitize_payload, uuid7

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


def test_view_as_is_sent_as_as_on_get_and_list_and_only_when_given(make_client: MakeClient) -> None:
    page = {"data": [], "has_more": False, "next_cursor": None}
    t = FakeTransport(handler=lambda *a: jresp(200, {"id": ID, "name": "K", **page}))
    c = make_client(t)
    c.list_page("character", limit=5, filter={"supertype": "s"}, view_as="public")
    list(c.iter_elements("character", limit=5, view_as=ID))
    c.get("character", ID, fields=["name"], view_as="public")
    c.list_page("character", limit=5)
    c.get("character", ID)
    queries = [x.url.split("?", 1)[1] if "?" in x.url else "" for x in t.calls]
    assert queries == [
        "limit=5&supertype=s&as=public",
        f"limit=5&as={ID}",
        "fields=name&as=public",
        "limit=5",
        "",
    ]


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


def test_a_timeout_then_in_flight_retries_to_the_replay(make_client: MakeClient, sleeps: list[float]) -> None:
    """keel #307: a retry after a timeout can meet the first request still running (409
    idempotency_in_flight, Retry-After 1); the next try, same key and body, gets the replay."""
    in_flight = {"error": {"type": "idempotency_error", "code": "idempotency_in_flight"}}
    t = FakeTransport(
        script=[
            TimeoutError("read timed out"),
            jresp(409, in_flight, {"Retry-After": "1"}),
            jresp(201, {"id": ID, "name": "A", "type": "character"}, {"Idempotent-Replay": "true"}),
        ]
    )
    made = make_client(t).create("character", {"name": "A"}, idempotency_key="k-9")
    assert made["id"] == ID and len(t.calls) == 3 and sleeps[1] == 1.0
    assert len({c.headers["Idempotency-Key"] for c in t.calls}) == 1
    assert t.calls[0].body == t.calls[1].body == t.calls[2].body


def test_a_key_conflict_409_is_never_retried(make_client: MakeClient, sleeps: list[float]) -> None:
    t = FakeTransport(script=[jresp(409, {"error": {"type": "idempotency_error", "code": "idempotency_error"}})])
    with pytest.raises(ApiError) as e:
        make_client(t).create("character", {"name": "A"}, idempotency_key="k-9")
    assert e.value.is_idempotency_conflict and not e.value.is_idempotency_in_flight and len(t.calls) == 1


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


def test_changes_after_is_sent_on_every_page_of_a_walk(make_client: MakeClient) -> None:
    t = FakeTransport(
        script=[
            jresp(200, {"cursor": "C1", "changes": [{"op": "upsert", "id": "1"}], "has_more": True, "head": 9}),
            jresp(200, {"cursor": "C2", "changes": [], "has_more": False, "head": 9}),
            jresp(200, {"cursor": "C3", "changes": [], "has_more": False, "head": 9}),
        ]
    )
    client = make_client(t)
    walk = client.walk_changes("C0", after="2026-10-21T09:00:00Z")
    assert [op["id"] for op in walk] == ["1"]
    for call in t.calls[:2]:
        assert "after=2026-10-21T09%3A00%3A00Z" in call.url
    assert "since=C1" in t.calls[1].url
    client.changes(since="C2")
    assert "after=" not in t.calls[2].url


def test_draught_sends_the_seven_policy_keys_and_list_page_the_two_filters(make_client: MakeClient) -> None:
    t = FakeTransport(
        script=[jresp(200, {"world": {"id": "w"}, "cut": {}}), jresp(200, {"world": {}}), jresp(200, {"data": []})]
    )
    client = make_client(t)
    packet = client.draught(
        "c1", components=["self", "events"], mode="act", as_of=453, undated="exclude", since="cur", budget=5, depth=0
    )
    assert packet["cut"] == {}
    url = t.calls[0].url
    assert "/character/c1/context?" in url
    for part in (
        "components=self,events",
        "mode=act",
        "as_of=453",
        "undated=exclude",
        "since=cur",
        "budget=5",
        "depth=0",
    ):
        assert part in url, part
    client.draught("c1")
    assert t.calls[1].url.endswith("/character/c1/context")
    client.list_page("character", ids=["a", "b"], created_by="owner")
    assert "ids=a,b" in t.calls[2].url and "created_by=owner" in t.calls[2].url


def test_a_numeric_cursor_becomes_the_walks_cursor_as_text(make_client: MakeClient) -> None:
    """keel answers an owner's cursor at the head as a number; the walk keeps it, as a string, to pass back."""
    t = FakeTransport(
        script=[
            jresp(200, {"cursor": 225, "changes": [{"op": "upsert", "id": "1"}], "has_more": True, "head": 226}),
            jresp(200, {"cursor": 226, "changes": [{"op": "upsert", "id": "2"}], "has_more": False, "head": 226}),
            jresp(200, {"cursor": 226, "changes": [], "has_more": False, "head": 226}),
        ]
    )
    client = make_client(t)
    walk = client.walk_changes("C0")
    assert [op["id"] for op in walk] == ["1", "2"]
    assert (walk.cursor, walk.head) == ("226", 226)
    assert "since=225" in t.calls[1].url
    again = client.walk_changes(walk.cursor)
    assert list(again) == [] and "since=226" in t.calls[2].url and again.cursor == "226"


def test_a_feed_that_says_more_without_moving_is_refused(make_client: MakeClient) -> None:
    stuck = jresp(200, {"cursor": "C0", "changes": [], "has_more": True, "head": 1})
    with pytest.raises(ValueError, match="no new cursor"):
        list(make_client(FakeTransport(script=[stuck])).walk_changes("C0"))


# --- the conditional head poll (keel #518) ----------------------------------------


def head_body(head: int, epoch: int | None = None, cursor: Any = None) -> dict[str, Any]:
    return {
        "cursor": head if cursor is None else cursor,
        "changes": [],
        "has_more": False,
        "head": head,
        "epoch": epoch,
    }


def not_modified(etag: str) -> Response:
    return Response(304, b"", {"ETag": etag, "Cache-Control": "no-store"})


RESYNC = jresp(409, {"error": {"type": "invalid_request", "code": "resync_required", "reason": "view"}})


def test_head_sends_no_tag_first_and_keeps_the_one_it_got_verbatim(make_client: MakeClient) -> None:
    t = FakeTransport(script=[jresp(200, head_body(821), {"etag": 'W/"821:-"'}), not_modified('"821:-"')])
    client = make_client(t)
    first = client.head()
    assert first == {"head": 821, "cursor": "821", "epoch": None, "unchanged": False}
    assert t.calls[0].method == "GET" and t.calls[0].url.endswith("/changes/?head=true")
    assert "If-None-Match" not in t.calls[0].headers
    second = client.head()
    assert t.calls[1].headers["If-None-Match"] == 'W/"821:-"'  # as received: the weak prefix and the quotes
    assert second == {"head": 821, "cursor": "821", "epoch": None, "unchanged": True}


def test_a_304_answers_what_the_last_200_said_and_a_later_200_replaces_the_tag(make_client: MakeClient) -> None:
    t = FakeTransport(
        script=[
            jresp(200, {**head_body(7, epoch=3, cursor="g:3:7"), "epoch_reason": "view"}, {"ETag": '"7:3"'}),
            not_modified('"7:3"'),
            jresp(200, head_body(9, epoch=3, cursor="g:3:9"), {"ETag": '"9:3"'}),
            not_modified('"9:3"'),
        ]
    )
    client = make_client(t)
    assert client.head() == {"head": 7, "cursor": "g:3:7", "epoch": 3, "epoch_reason": "view", "unchanged": False}
    assert client.head() == {"head": 7, "cursor": "g:3:7", "epoch": 3, "epoch_reason": "view", "unchanged": True}
    assert t.calls[1].body is None  # a 304 has no body, and the poll sends none
    assert client.head() == {"head": 9, "cursor": "g:3:9", "epoch": 3, "unchanged": False}
    assert t.calls[2].headers["If-None-Match"] == '"7:3"'
    assert client.head()["unchanged"] is True
    assert t.calls[3].headers["If-None-Match"] == '"9:3"'


def test_a_200_without_a_tag_leaves_none_to_send(make_client: MakeClient) -> None:
    t = FakeTransport(
        script=[jresp(200, head_body(1), {"ETag": '"1:-"'}), jresp(200, head_body(2)), jresp(200, head_body(2))]
    )
    client = make_client(t)
    client.head()
    assert client.head()["unchanged"] is False
    client.head()
    assert "If-None-Match" not in t.calls[2].headers


def test_a_resync_409_from_any_feed_read_clears_the_tag(make_client: MakeClient) -> None:
    tagged = jresp(200, head_body(5), {"ETag": '"5:-"'})
    walk_page = jresp(200, {"cursor": "C1", "changes": [], "has_more": False, "head": 5})
    t = FakeTransport(
        script=[tagged, RESYNC, tagged, tagged, RESYNC, tagged, tagged, RESYNC, tagged, tagged, walk_page]
    )
    client = make_client(t)
    client.head()
    with pytest.raises(ApiError) as caught:
        client.head()
    assert caught.value.resync_reason == "view"
    client.head()
    assert "If-None-Match" not in t.calls[2].headers  # the poll after a 409 carries no tag

    client.head()
    with pytest.raises(ApiError):
        client.changes(since="C0")
    client.head()
    assert "If-None-Match" not in t.calls[5].headers

    client.head()
    with pytest.raises(ApiError):
        list(client.walk_changes("C0"))
    client.head()
    assert "If-None-Match" not in t.calls[8].headers
    client.head()
    assert t.calls[9].headers["If-None-Match"] == '"5:-"'  # held again after a 200
    assert [op for op in client.walk_changes("C0")] == []


def test_another_error_keeps_the_tag(make_client: MakeClient) -> None:
    t = FakeTransport(
        script=[
            jresp(200, head_body(5), {"ETag": '"5:-"'}),
            env(403, "permission_error", "permission_error"),
            not_modified('"5:-"'),
        ]
    )
    client = make_client(t)
    client.head()
    with pytest.raises(ApiError):
        client.head()
    assert client.head()["unchanged"] is True
    assert t.calls[2].headers["If-None-Match"] == '"5:-"'


def test_a_304_with_nothing_held_is_refused(make_client: MakeClient) -> None:
    client = make_client(FakeTransport(script=[not_modified('"5:-"')]))
    with pytest.raises(ValueError, match="304"):
        client.head()


def test_the_tag_is_per_client(make_client: MakeClient) -> None:
    t = FakeTransport(handler=lambda *a: jresp(200, head_body(4), {"ETag": '"4:-"'}))
    one, two = make_client(t), make_client(t)
    one.head()
    two.head()
    assert "If-None-Match" not in t.calls[1].headers


# --- errors ----------------------------------------


@pytest.mark.parametrize(
    ("status", "etype", "code", "flag"),
    [
        (409, "invalid_request", "id_conflict", "is_id_conflict"),
        (409, "idempotency_error", "idempotency_error", "is_idempotency_conflict"),
        (403, "permission_error", "not_author", "is_not_author"),
        (403, "permission_error", "owner_only", "is_owner_only"),
        (403, "permission_error", "view_as_owner_only", "is_view_as_owner_only"),
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
        "is_view_as_owner_only",
        "is_busy",
        "is_auth_error",
        "is_validation_error",
        "is_known_of_not_writable",
    ]
    t = FakeTransport(script=[env(status, etype, code)])
    with pytest.raises(ApiError) as caught:
        make_client(t, attempts=1).patch("character", ID, {"name": "K"})
    e = caught.value
    assert (e.status, e.type, e.code) == (status, etype, code) and e.doc_url == f"https://x/{code}"
    assert [f for f in flags if getattr(e, f)] == [flag]


def test_known_of_not_writable_is_a_validation_error_with_its_own_flag() -> None:
    e = ApiError("PATCH", "x", jresp(422, {"error": {"code": "known_of_not_writable", "param": "known_of"}}))
    assert (e.is_known_of_not_writable, e.is_validation_error, e.param) == (True, True, "known_of")
    other = ApiError("PATCH", "x", jresp(422, {"error": {"code": "invalid_field"}}))
    assert (other.is_known_of_not_writable, other.is_validation_error) == (False, True)


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


def test_resync_reason_reads_the_409_envelope() -> None:
    """keel #421, keel PR 103: with the hidden mark on, the 409 resync_required says why in ``reason``."""
    for reason in ("role", "view"):
        body = {
            "error": {
                "type": "invalid_request",
                "code": "resync_required",
                "message": "m",
                "param": "since",
                "doc_url": "https://x/resync_required",
                "reason": reason,
            }
        }
        e = ApiError("GET", "changes/", jresp(409, body))
        assert (e.is_resync_required, e.resync_reason) == (True, reason)
    plain = ApiError("GET", "changes/", env(409, "invalid_request", "resync_required"))
    assert (plain.is_resync_required, plain.resync_reason) == (True, None)
    odd = {"error": {"code": "resync_required", "reason": "something"}}
    assert ApiError("GET", "changes/", jresp(409, odd)).resync_reason is None
    other = {"error": {"type": "invalid_request", "code": "id_conflict", "reason": "role"}}
    assert ApiError("POST", "bulk/", jresp(409, other)).resync_reason is None


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


# --- only if unchanged (keel #210) ----------------------------------------

PRECONDITION_412 = {
    "error": {
        "type": "invalid_request", "code": "precondition_failed", "param": "If-Match",
        "message": "The element has changed since change_seq 41 (now 44).", "doc_url": "https://x/precondition_failed",
    },
    "current": {"type": "character", "id": ID, "name": "Theirs", "change_seq": 44},
}  # fmt: skip


def test_if_match_sends_a_quoted_change_seq_on_patch_and_links_and_nothing_without(make_client: MakeClient) -> None:
    t = FakeTransport(handler=lambda *a: jresp(200, {"id": ID, "name": "K", "change_seq": 45}))
    c = make_client(t)
    c.patch("character", ID, {"name": "Mine"}, if_match=44)
    c.edit_links("character", ID, "friends", add=["a"], if_match=7)
    c.patch("character", ID, {"name": "Mine"})
    assert t.calls[0].headers["If-Match"] == '"44"'
    assert t.calls[1].headers["If-Match"] == '"7"'
    assert "If-Match" not in t.calls[2].headers


@pytest.mark.parametrize("bad", [4.5, -1, "44", True, None.__class__])
def test_an_if_match_that_is_not_a_whole_number_raises_before_sending(make_client: MakeClient, bad: Any) -> None:
    t = FakeTransport(handler=lambda *a: jresp(200, {}))
    with pytest.raises(ValueError, match="if_match"):
        make_client(t).patch("character", ID, {"name": "K"}, if_match=bad)
    assert t.calls == []


def test_a_412_is_precondition_failed_carrying_current(make_client: MakeClient) -> None:
    t = FakeTransport(handler=lambda *a: jresp(412, PRECONDITION_412))
    with pytest.raises(PreconditionFailed) as got:
        make_client(t).patch("character", ID, {"name": "Mine"}, if_match=41)
    e = got.value
    assert isinstance(e, ApiError) and e.is_precondition_failed and e.status == 412
    assert e.current == PRECONDITION_412["current"] and e.param == "If-Match"
    assert not e.is_validation_error and not e.is_id_conflict
    assert not ApiError("PATCH", "x", jresp(409, {"error": {"code": "id_conflict"}})).is_precondition_failed


def test_a_412_without_current_still_parses(make_client: MakeClient) -> None:
    t = FakeTransport(handler=lambda *a: jresp(412, {"error": PRECONDITION_412["error"]}))
    with pytest.raises(PreconditionFailed) as got:
        make_client(t).patch("character", ID, {"name": "Mine"}, if_match=41)
    assert got.value.current is None


def test_patch_world_takes_back_a_get_world_body_and_a_folder_spelling(make_client: MakeClient) -> None:
    t = FakeTransport(handler=lambda *_: jresp(200, {"id": "w"}))
    body = {"id": "w", "name": "W", "public_read": True, "created_at": "a", "updated_at": "b", "time_current": 5}
    make_client(t).patch_world(body)
    assert t.calls[0].body == {"name": "W", "time_range_current": 5}


def test_patch_world_never_sends_what_only_a_folder_carries(make_client: MakeClient) -> None:
    # a folder's world.json handed back whole: its own keys (§4.1, §4.2) say what the folder is
    t = FakeTransport(handler=lambda *_: jresp(200, {"id": "w"}))
    folder_world = {
        "id": "w",
        "name": "W",
        "format_version": "0.3.14",
        "writable": False,
        "source": {"server": "https://www.onlyworlds.com", "world": "w", "at": "2026-10-22T10:00:00.000Z"},
        "exported_as": {"kind": "owner", "role": "owner", "character": None},
        "producer": {"tool": "onlyworlds", "version": "0.16.0", "input": "server"},
        "api": {"world_id": "w"},
        "snapshot_of": "w0",
        "snapshot_counts": {"character": 1},
        "x_calendar": {"months": 12},
    }
    make_client(t).patch_world(folder_world)
    assert t.calls[0].body == {"name": "W", "x_calendar": {"months": 12}}


# --- keel #299: the agent declaration -------------------------------------


def test_agent_header_on_the_six_element_writes_only(make_client: MakeClient) -> None:
    body = {"id": ID, "name": "K", "type": "character", "items": [], "data": [], "has_more": False}
    t = FakeTransport(handler=lambda *a: jresp(200, body))
    make_client(t).patch("character", ID, {"name": "K2"})
    assert "X-OW-Agent" not in t.calls[-1].headers  # off by default
    agent = Client("ow_w_testkey", "1234", transport=t, agent=True)
    t.calls.clear()
    agent.create("character", {"name": "A"})
    agent.upsert("character", ID, {"name": "K"})
    agent.patch("character", ID, {"name": "K2"}, if_match=3)
    agent.edit_links("character", ID, "friends", add=["a"])
    agent.bulk([{"type": "character", "element": {"name": "B"}}])
    agent.delete("character", ID)
    assert [(c.method, c.headers.get("X-OW-Agent")) for c in t.calls] == [
        ("POST", "1"),
        ("PUT", "1"),
        ("PATCH", "1"),
        ("POST", "1"),
        ("POST", "1"),
        ("DELETE", "1"),
    ]
    assert t.calls[2].headers["If-Match"] == '"3"'  # the write's own headers survive
    t.calls.clear()
    agent.get("character", ID)
    agent.list_page("character")
    agent.get_world()
    agent.patch_world({"name": "W"})
    assert [c.headers.get("X-OW-Agent") for c in t.calls] == [None, None, None, None]


# --- keel #520: the client's name ------------------------------------------


def _six_writes(c: Client) -> None:
    c.create("character", {"name": "A"})
    c.upsert("character", ID, {"name": "K"})
    c.patch("character", ID, {"name": "K2"}, if_match=3)
    c.edit_links("character", ID, "friends", add=["a"])
    c.bulk([{"type": "character", "element": {"name": "B"}}])
    c.delete("character", ID)


def test_client_name_on_the_six_element_writes_only(make_client: MakeClient) -> None:
    body = {"id": ID, "name": "K", "type": "character", "items": [], "data": [], "has_more": False}
    t = FakeTransport(handler=lambda *a: jresp(200, body))
    _six_writes(make_client(t))
    assert [(c.method, c.headers.get("X-OW-Client")) for c in t.calls] == [
        ("POST", "python"),
        ("PUT", "python"),
        ("PATCH", "python"),
        ("POST", "python"),
        ("POST", "python"),
        ("DELETE", "python"),
    ]
    assert t.calls[2].headers["If-Match"] == '"3"'  # the write's own headers survive
    assert "X-OW-Agent" not in t.calls[0].headers  # the name is not the agent declaration
    t.calls.clear()
    c = make_client(t)
    c.get("character", ID)
    c.list_page("character")
    c.get_world()
    c.patch_world({"name": "W"})
    assert [c.headers.get("X-OW-Client") for c in t.calls] == [None, None, None, None]


def test_client_name_is_the_callers_and_rides_beside_the_agent_header() -> None:
    body = {"id": ID, "name": "K", "type": "character", "items": [], "data": [], "has_more": False}
    t = FakeTransport(handler=lambda *a: jresp(200, body))
    _six_writes(Client("ow_w_testkey", "1234", transport=t, client="atlas", agent=True))
    assert {(c.headers.get("X-OW-Client"), c.headers.get("X-OW-Agent")) for c in t.calls} == {("atlas", "1")}
    t.calls.clear()
    longest = "a-9" + "z" * 29
    Client("ow_w_testkey", "1234", transport=t, client=longest).delete("character", ID)
    assert t.calls[0].headers["X-OW-Client"] == longest


@pytest.mark.parametrize("bad", ["Atlas", "", "a" * 33, "a b", " atlas", "atlas\n", "atlas_1", "atlás"])
def test_client_name_outside_the_rule_is_refused_at_construction(bad: str) -> None:
    with pytest.raises(ValueError, match=r"client.*\[a-z0-9-\]\{1,32\}"):
        Client("ow_w_testkey", "1234", client=bad)


@pytest.mark.parametrize("bad", [None, 1, b"atlas", ["atlas"]])
def test_client_name_not_a_string_is_a_type_error(bad: Any) -> None:
    with pytest.raises(TypeError, match=r"client.*\[a-z0-9-\]\{1,32\}"):
        Client("ow_w_testkey", "1234", client=bad)
