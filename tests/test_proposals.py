"""The proposed change (keel #519, PR 180; round 2, keel #565, PR 188): the proposal calls, the review
of a marked new element, the 202 a held write answers, and the six error codes. Scripted HTTP, no network."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any

import pytest
from conftest import FakeTransport, jresp

from onlyworlds import ApiError, Client, ProposedError, Response, StaleProposal

ID = "018f0000-0000-7000-8000-000000000001"
PID = "019a0000-0000-7000-8000-0000000000aa"
BASE = "https://www.onlyworlds.com/api/v2/"
MakeClient = Callable[..., Client]

PROPOSAL: dict[str, Any] = {
    "kind": "proposal",
    "id": PID,
    "element_type": "location",
    "element_id": ID,
    "state": "open",
    "fields": {"description": "A walled port."},
    "omitted": [],
    "base": {"description": "A port."},
    "base_seq": 4,
    "evidence": "Chapter 3 says so.",
    "expires": "2026-11-21T00:00:00Z",
    "by": "019a0000-0000-7000-8000-0000000000bb",
    "via": "key",
    "client": "python",
    "decided_by": None,
    "decided_at": None,
    "decline_reason": None,
    "created_at": "2026-10-22T16:30:00Z",
    "updated_at": "2026-10-22T16:30:00Z",
}
NEW = "018f0000-0000-7000-8000-000000000002"
#: A queue row for a new element marked for review (keel #565): the element is the record.
MARKED: dict[str, Any] = {
    "kind": "new_element",
    "id": NEW,
    "element_type": "character",
    "element_id": NEW,
    "state": "open",
    "by": "019a0000-0000-7000-8000-0000000000bb",
    "evidence": "Chapter 4 names her.",
    "expires": "2026-11-22",
    "created_at": "2026-10-23T07:00:00Z",
    "updated_at": "2026-10-23T07:00:00Z",
}


def path(call: Any) -> str:
    return str(call.url).removeprefix(BASE)


# --- the calls -----------------------------------------------------------------


def test_propose_posts_fields_and_evidence_and_returns_the_proposal(make_client: MakeClient) -> None:
    t = FakeTransport(script=[jresp(201, {"proposal": PROPOSAL})])
    got = make_client(t).propose("location", ID, {"description": "A walled port."}, evidence="Chapter 3 says so.")
    assert got == PROPOSAL
    (call,) = t.calls
    assert (call.method, path(call)) == ("POST", f"location/{ID}/proposals")
    assert call.body == {"fields": {"description": "A walled port."}, "evidence": "Chapter 3 says so."}
    assert call.headers["X-OW-Client"] == "python"
    assert call.headers["Idempotency-Key"]  # always one: a retried timeout never makes a second proposal


def test_propose_sends_expires_your_key_and_a_datetime_as_iso(make_client: MakeClient) -> None:
    t = FakeTransport(handler=lambda *a: jresp(201, {"proposal": PROPOSAL}))
    c = make_client(t)
    c.propose("location", ID, {"name": "H"}, evidence="e", expires="2026-12-01T00:00:00Z", idempotency_key="k-1")
    c.propose("location", ID, {"name": "H"}, evidence="e", expires=dt.datetime(2026, 12, 1, tzinfo=dt.UTC))
    assert t.calls[0].body["expires"] == "2026-12-01T00:00:00Z"
    assert t.calls[0].headers["Idempotency-Key"] == "k-1"
    assert t.calls[1].body["expires"] == "2026-12-01T00:00:00+00:00"
    assert t.calls[1].headers["Idempotency-Key"] not in ("", "k-1")


def test_a_retried_propose_repeats_its_key_and_body(make_client: MakeClient, sleeps: list[float]) -> None:
    t = FakeTransport(script=[TimeoutError("lost"), jresp(201, {"proposal": PROPOSAL})])
    make_client(t).propose("location", ID, {"name": "H"}, evidence="e")
    assert t.calls[0].headers["Idempotency-Key"] == t.calls[1].headers["Idempotency-Key"]
    assert t.calls[0].body == t.calls[1].body


def test_propose_cleans_fields_as_a_patch_body_and_refuses_a_stub(make_client: MakeClient) -> None:
    t = FakeTransport(handler=lambda *a: jresp(201, {"proposal": PROPOSAL}))
    c = make_client(t)
    c.propose("location", ID, {"name": "H", "change_seq": 4, "updated_at": "x", "x_note": 1}, evidence="e")
    assert t.calls[0].body["fields"] == {"name": "H", "x_note": 1}
    with pytest.raises(ValueError, match="known-of stub"):
        c.propose("location", ID, {"known_of": True, "name": ""}, evidence="e")
    with pytest.raises(ValueError, match="text field"):
        c.propose("location", ID, {"description": 5}, evidence="e")
    assert len(t.calls) == 1


def test_list_proposals_on_one_element(make_client: MakeClient) -> None:
    page = {"data": [PROPOSAL], "has_more": False, "next_cursor": None}
    t = FakeTransport(handler=lambda *a: jresp(200, page))
    c = make_client(t)
    assert c.list_proposals("location", ID) == page
    c.list_proposals("location", ID, state="all", since="2026-10-01T00:00:00Z", limit=5, cursor="cur")
    assert [(x.method, path(x)) for x in t.calls] == [
        ("GET", f"location/{ID}/proposals"),
        ("GET", f"location/{ID}/proposals?state=all&since=2026-10-01T00%3A00%3A00Z&limit=5&cursor=cur"),
    ]
    assert "X-OW-Client" not in t.calls[0].headers  # a read


def test_accept_returns_the_proposal_and_the_element(make_client: MakeClient) -> None:
    answer = {"proposal": {**PROPOSAL, "state": "accepted"}, "element": {"id": ID, "description": "A walled port."}}
    t = FakeTransport(script=[jresp(200, answer)])
    assert make_client(t).accept_proposal("location", ID, PID) == answer
    (call,) = t.calls
    assert (call.method, path(call), call.body) == ("POST", f"location/{ID}/proposals/{PID}/accept", None)
    assert call.headers["X-OW-Client"] == "python"


def test_decline_sends_its_reason_only_when_given(make_client: MakeClient) -> None:
    declined = {**PROPOSAL, "state": "declined", "decline_reason": "Not canon."}
    t = FakeTransport(handler=lambda *a: jresp(200, {"proposal": declined}))
    c = make_client(t)
    assert c.decline_proposal("location", ID, PID, reason="Not canon.") == declined
    c.decline_proposal("location", ID, PID)
    assert [(x.method, path(x), x.body) for x in t.calls] == [
        ("POST", f"location/{ID}/proposals/{PID}/decline", {"reason": "Not canon."}),
        ("POST", f"location/{ID}/proposals/{PID}/decline", {}),
    ]


def test_withdraw_is_a_delete_answering_204(make_client: MakeClient) -> None:
    t = FakeTransport(script=[Response(204, b"", {})])
    assert make_client(t).withdraw_proposal("location", ID, PID) is None
    assert (t.calls[0].method, path(t.calls[0])) == ("DELETE", f"location/{ID}/proposals/{PID}")


def test_world_proposals_sends_only_what_is_given(make_client: MakeClient) -> None:
    page = {"data": [], "has_more": False, "next_cursor": None}
    t = FakeTransport(handler=lambda *a: jresp(200, page))
    c = make_client(t)
    assert c.world_proposals() == page
    c.world_proposals(state="lapsed", since="2026-10-01T00:00:00Z", element=ID, limit=1000, cursor="c")
    assert [path(x) for x in t.calls] == [
        "world/proposals",
        f"world/proposals?state=lapsed&since=2026-10-01T00%3A00%3A00Z&element={ID}&limit=1000&cursor=c",
    ]


def test_walk_world_proposals_follows_the_cursor(make_client: MakeClient) -> None:
    second = {**PROPOSAL, "id": "019a0000-0000-7000-8000-0000000000ab"}
    t = FakeTransport(
        script=[
            jresp(200, {"data": [PROPOSAL], "has_more": True, "next_cursor": "n1"}),
            jresp(200, {"data": [second], "has_more": False, "next_cursor": None}),
        ]
    )
    rows = list(make_client(t).walk_world_proposals(state="all", limit=1))
    assert [r["id"] for r in rows] == [PID, second["id"]]
    assert [path(x) for x in t.calls] == [
        "world/proposals?state=all&limit=1",
        "world/proposals?state=all&limit=1&cursor=n1",
    ]


def test_the_walk_yields_both_kinds_of_row_and_sends_the_cursor_back_as_it_came(make_client: MakeClient) -> None:
    # keel #565: one order newest first, both kinds; the cursor is opaque (`<microseconds>.<id>`
    # today), never the last row's id.
    opaque = f"1729666800000000.{PID}"
    t = FakeTransport(
        script=[
            jresp(200, {"data": [MARKED], "has_more": True, "next_cursor": opaque}),
            jresp(200, {"data": [PROPOSAL], "has_more": False, "next_cursor": None}),
        ]
    )
    rows = list(make_client(t).walk_world_proposals())
    assert [r["kind"] for r in rows] == ["new_element", "proposal"]
    assert [path(x) for x in t.calls] == ["world/proposals", f"world/proposals?cursor={opaque}"]


def test_a_walk_that_says_more_without_a_cursor_is_refused(make_client: MakeClient) -> None:
    t = FakeTransport(script=[jresp(200, {"data": [], "has_more": True, "next_cursor": None})])
    with pytest.raises(ValueError, match="next_cursor"):
        list(make_client(t).walk_world_proposals())


@pytest.mark.parametrize("bad", ["../x", "a/b", ""])
def test_proposal_path_segments_are_checked(make_client: MakeClient, bad: str) -> None:
    t = FakeTransport()
    c = make_client(t)
    with pytest.raises(ValueError):
        c.accept_proposal("location", ID, bad)
    with pytest.raises(ValueError):
        c.propose("location", bad, {"name": "x"}, evidence="e")
    with pytest.raises(ValueError):
        c.review_new_element("character", bad, "accept")
    assert t.calls == []


# --- a new element marked for review (keel #565) -------------------------------------


def test_review_accept_posts_the_decision_and_returns_the_element(make_client: MakeClient) -> None:
    answer = {"element": {"id": NEW, "name": "Ann", "x_review_proposed": None}}
    t = FakeTransport(script=[jresp(200, answer)])
    assert make_client(t).review_new_element("character", NEW, "accept") == answer
    (call,) = t.calls
    assert (call.method, path(call), call.body) == ("POST", f"character/{NEW}/review", {"decision": "accept"})
    assert call.headers["X-OW-Client"] == "python"


def test_review_decline_sends_its_reason_only_when_given(make_client: MakeClient) -> None:
    t = FakeTransport(handler=lambda *a: jresp(200, {"deleted": NEW}))
    c = make_client(t)
    assert c.review_new_element("character", NEW, "decline", reason="Not canon.") == {"deleted": NEW}
    c.review_new_element("character", NEW, "decline")
    assert [x.body for x in t.calls] == [{"decision": "decline", "reason": "Not canon."}, {"decision": "decline"}]


def test_review_refuses_another_decision_and_a_reason_on_accept_before_sending(make_client: MakeClient) -> None:
    t = FakeTransport()
    c = make_client(t)
    with pytest.raises(ValueError, match="accept' or 'decline"):
        c.review_new_element("character", NEW, "approve")
    with pytest.raises(ValueError, match="decline only"):
        c.review_new_element("character", NEW, "accept", reason="fine")
    assert t.calls == []


@pytest.mark.parametrize(("decision", "answer"), [("accept", {"deleted": NEW}), ("decline", {"element": {}})])
def test_a_review_answer_without_its_key_is_refused(make_client: MakeClient, decision: str, answer: Any) -> None:
    t = FakeTransport(script=[jresp(200, answer)])
    with pytest.raises(ValueError, match="returned no"):
        make_client(t).review_new_element("character", NEW, decision)


# --- the 202: a write held as a proposal ---------------------------------------------


def _proposed(*_: Any) -> Response:
    return jresp(202, {"proposal": PROPOSAL})


@pytest.mark.parametrize("write", ["patch", "upsert", "edit_links"])
def test_a_202_on_a_write_raises_proposed_error_with_the_proposal(make_client: MakeClient, write: str) -> None:
    t = FakeTransport(handler=_proposed)
    c = make_client(t)
    with pytest.raises(ProposedError) as got:
        if write == "patch":
            c.patch("location", ID, {"description": "A walled port."})
        elif write == "upsert":
            c.upsert("location", ID, {"name": "Harbor"})
        else:
            c.edit_links("location", ID, "populations", add=["x"])
    e = got.value
    assert isinstance(e, ApiError) and e.status == 202 and e.is_proposed
    assert e.proposal == PROPOSAL and e.code is None
    assert not e.is_validation_error and not e.is_permission_error
    assert PID in str(e)
    assert len(t.calls) == 1  # a 202 is an answer, never retried


def test_a_202_without_a_proposal_still_raises(make_client: MakeClient) -> None:
    t = FakeTransport(handler=lambda *a: Response(202, b"", {}))
    with pytest.raises(ProposedError) as got:
        make_client(t).patch("location", ID, {"name": "x"})
    assert got.value.proposal is None


def test_an_ordinary_answer_is_not_proposed(make_client: MakeClient) -> None:
    t = FakeTransport(handler=lambda *a: jresp(200, {"id": ID, "name": "x"}))
    assert make_client(t).patch("location", ID, {"name": "x"}) == {"id": ID, "name": "x"}
    assert not ApiError("PATCH", "x", jresp(422, {"error": {"code": "invalid_request"}})).is_proposed


def test_a_bulk_slot_answering_202_stays_in_the_result(make_client: MakeClient) -> None:
    slots = [
        {"status": 202, "id": ID, "proposal": PROPOSAL},
        {"status": 201, "id": "018f0000-0000-7000-8000-000000000002", "created_at": "a", "updated_at": "a"},
    ]
    t = FakeTransport(script=[jresp(200, {"errors": False, "items": slots})])
    res = make_client(t).bulk(
        [{"type": "location", "element": {"id": ID, "name": "H"}}, {"type": "location", "element": {"name": "N"}}]
    )
    assert res.items == slots and res.errors is False
    assert res.proposed == [slots[0]]


# --- the six codes ------------------------------------------------------------------


def _err(status: int, etype: str, code: str, **beside: Any) -> ApiError:
    body = {"error": {"type": etype, "code": code, "message": code, "param": None, "doc_url": f"https://x/{code}"}}
    return ApiError("POST", "x", jresp(status, {**body, **beside}))


CODES = [
    (422, "invalid_request", "field_not_visible", "is_field_not_visible"),
    (422, "invalid_request", "too_many_open", "is_too_many_open"),
    (409, "invalid_request", "stale_proposal", "is_stale_proposal"),
    (403, "permission_error", "proposed_only", "is_proposed_only"),
    (403, "permission_error", "own_proposal", "is_own_proposal"),
    (422, "invalid_request", "not_proposed", "is_not_proposed"),  # keel #565: a review of an unmarked element
]


@pytest.mark.parametrize(("status", "etype", "code", "flag"), CODES)
def test_each_proposal_code_has_its_own_predicate_and_no_other(status: int, etype: str, code: str, flag: str) -> None:
    e = _err(status, etype, code)
    assert [f for *_, f in CODES if getattr(e, f)] == [flag]
    assert not e.is_permission_error and not e.is_not_author and not e.is_proposed
    assert not e.is_id_conflict and not e.is_idempotency_conflict and not e.is_precondition_failed
    # the same code at another status is not the case
    assert not getattr(_err(400, etype, code), flag)


def test_a_stale_accept_carries_conflicts_and_current(make_client: MakeClient) -> None:
    conflicts = [{"field": "description", "base": "A port.", "current": "A burned port."}]
    current = {"id": ID, "name": "Harbor", "description": "A burned port.", "change_seq": 9}
    body = {
        "error": {
            "type": "invalid_request", "code": "stale_proposal", "message": "m", "param": None,
            "doc_url": "https://x/stale_proposal",
        },
        "conflicts": conflicts,
        "current": current,
    }  # fmt: skip
    t = FakeTransport(script=[jresp(409, body)])
    with pytest.raises(StaleProposal) as got:
        make_client(t).accept_proposal("location", ID, PID)
    e = got.value
    assert isinstance(e, ApiError) and e.is_stale_proposal and e.status == 409
    assert e.conflicts == conflicts and e.current == current
    assert len(t.calls) == 1  # a 409 stale_proposal is never retried


def test_a_stale_proposal_without_its_extras_still_parses() -> None:
    from onlyworlds.errors import api_error

    e = api_error("POST", "x", jresp(409, {"error": {"code": "stale_proposal"}}))
    assert isinstance(e, StaleProposal) and e.conflicts == [] and e.current is None
    odd = api_error("POST", "x", jresp(409, {"error": {"code": "stale_proposal"}, "conflicts": [1, {"field": "a"}]}))
    assert isinstance(odd, StaleProposal) and odd.conflicts == [{"field": "a"}]
