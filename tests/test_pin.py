"""Where ``API-Pin`` rides: every method but GET, ``GET /me``, and every request of a 10-digit legacy key.

keel verifies a PIN wherever one is sent (argon2, 64 MiB each); a PIN on every read OOM-killed
staging after a restart (2026-10-22; Skeld's rule). Scripted HTTP, no network.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from conftest import FakeTransport, jresp

from onlyworlds import Client

ID = "018f0000-0000-7000-8000-000000000001"
PID = "018f0000-0000-7000-8000-0000000000aa"

# One body every call below accepts: an element, a world, a page, a feed page, a head, a proposal.
BODY = {
    "id": ID,
    "name": "K",
    "data": [],
    "has_more": False,
    "next_cursor": None,
    "changes": [],
    "cursor": "1",
    "head": 1,
    "epoch": None,
    "state": "open",
    "fields": {},
    "items": [],
    "proposal": {"id": PID, "state": "open"},
}

Call = Callable[[Client], object]

READS: list[tuple[str, Call]] = [
    ("list_page", lambda c: c.list_page("character")),
    ("get", lambda c: c.get("character", ID)),
    ("changes", lambda c: c.changes()),
    ("head", lambda c: c.head()),
    ("draught", lambda c: c.draught(ID)),
    ("world_proposals", lambda c: c.world_proposals()),
    ("list_proposals", lambda c: c.list_proposals("character", ID)),
    ("get_world", lambda c: c.get_world()),
]

WRITES: list[tuple[str, Call]] = [
    ("create", lambda c: c.create("character", {"name": "K"})),
    ("patch", lambda c: c.patch("character", ID, {"name": "K2"})),
    ("upsert", lambda c: c.upsert("character", ID, {"name": "K"})),
    ("delete", lambda c: c.delete("character", ID)),
    ("edit_links", lambda c: c.edit_links("character", ID, "friends", add=["a"])),
    ("bulk", lambda c: c.bulk([{"type": "character", "element": {"name": "K"}}])),
    ("propose", lambda c: c.propose("character", ID, {"name": "K2"}, evidence="a source")),
    ("decline_proposal", lambda c: c.decline_proposal("character", ID, PID)),
    ("patch_world", lambda c: c.patch_world({"name": "W"})),
]

ME: list[tuple[str, Call]] = [("me", lambda c: c.me())]


def _sent(key: str, pin: str | None, calls: list[tuple[str, Call]]) -> dict[str, tuple[str, str | None]]:
    """Each call's (method, API-Pin as sent) through a recording transport."""
    out: dict[str, tuple[str, str | None]] = {}
    for name, fn in calls:
        t = FakeTransport(handler=lambda *a: jresp(200, BODY))
        fn(Client(key, pin, transport=t))
        assert len(t.calls) == 1, name
        out[name] = (t.calls[0].method, t.calls[0].headers.get("API-Pin"))
    return out


def test_the_pin_rides_only_where_keel_checks_it() -> None:
    # An ow_w_ key with a PIN: on every write and on GET /me, never on any other read.
    reads = _sent("ow_w_testkey", "1234", READS)
    writes = _sent("ow_w_testkey", "1234", WRITES)
    me = _sent("ow_w_testkey", "1234", ME)
    assert {n: pin for n, (_, pin) in reads.items()} == dict.fromkeys(reads, None)
    assert {n: m for n, (m, _) in reads.items()} == dict.fromkeys(reads, "GET")
    assert {n: pin for n, (_, pin) in writes.items()} == dict.fromkeys(writes, "1234")
    assert {m for m, _ in writes.values()} == {"POST", "PATCH", "PUT", "DELETE"}
    assert me == {"me": ("GET", "1234")}

    # A 10-digit legacy key with a PIN: on every call, reads included (keel #421).
    legacy = _sent("0123456789", "1234", READS + WRITES + ME)
    assert {n: pin for n, (_, pin) in legacy.items()} == dict.fromkeys(legacy, "1234")

    # An ow_r_ key with no PIN: never a header, not even an empty one.
    bare = _sent("ow_r_readkey", None, READS + WRITES + ME)
    assert {n: pin for n, (_, pin) in bare.items()} == dict.fromkeys(bare, None)


@pytest.mark.parametrize(
    ("key", "method", "path", "pinned"),
    [
        ("ow_w_testkey", "GET", "anything/new/", False),
        ("ow_w_testkey", "GET", "me/?x=1", True),
        ("ow_w_testkey", "GET", "me/sub/", False),
        ("ow_w_testkey", "OPTIONS", "anything/new/", True),
        ("ow_w_testkey", "post", "anything/new/", True),
        ("01234567890", "GET", "anything/", False),  # eleven digits: not a legacy key
        ("0123456789", "GET", "anything/", True),
    ],
)
def test_the_rule_is_derived_from_the_request(key: str, method: str, path: str, pinned: bool) -> None:
    t = FakeTransport(handler=lambda *a: jresp(200, BODY))
    Client(key, "1234", transport=t).request(method, path)
    assert ("API-Pin" in t.calls[0].headers) is pinned


@pytest.mark.parametrize("key", ["ow_w_testkey", "0123456789"])
def test_health_carries_no_credential(key: str) -> None:
    """keel's document gives ``GET /health`` no security: neither the key nor the PIN rides there."""
    t = FakeTransport(handler=lambda *a: jresp(200, {"status": "ok"}))
    Client(key, "1234", transport=t).health()
    assert not {"API-Key", "API-Pin"} & set(t.calls[0].headers)


def test_repr_never_prints_credentials() -> None:
    shown = repr(Client("ow_w_secretkey", "9876"))
    assert "secretkey" not in shown and "9876" not in shown
