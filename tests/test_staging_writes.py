"""Writes on the wire, against a scratch world on keel-staging. Skipped unless the keys are in the environment.

The staging keys are never in the repo or in CI: set ``OW_STAGING_BASE``, ``OW_STAGING_OWNER_KEY`` and
``_PIN``, ``OW_STAGING_CONTRIB_KEY`` and ``_PIN`` (a contributor member's own key and account PIN), and
``OW_STAGING_MEMBERSHIP`` (that member's membership id). Every element a test makes is deleted after it.
The first call after idle can take a minute (cold start).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest

from onlyworlds import Client, uuid7
from onlyworlds.errors import ApiError

_NEED = (
    "OW_STAGING_BASE",
    "OW_STAGING_OWNER_KEY",
    "OW_STAGING_OWNER_PIN",
    "OW_STAGING_CONTRIB_KEY",
    "OW_STAGING_CONTRIB_PIN",
    "OW_STAGING_MEMBERSHIP",
)
pytestmark = pytest.mark.skipif(
    not all(os.environ.get(k) for k in _NEED), reason="set the OW_STAGING_* variables for the write checks"
)


def _client(key: str, pin: str | None) -> Client:
    return Client(key, pin, base_url=os.environ["OW_STAGING_BASE"], timeout=120)


@pytest.fixture(scope="module")
def owner() -> Client:
    return _client(os.environ["OW_STAGING_OWNER_KEY"], os.environ["OW_STAGING_OWNER_PIN"])


@pytest.fixture(scope="module")
def contrib() -> Client:
    return _client(os.environ["OW_STAGING_CONTRIB_KEY"], os.environ["OW_STAGING_CONTRIB_PIN"])


@pytest.fixture
def made(owner: Client) -> Iterator[list[tuple[str, str]]]:
    """Collects (type, id) pairs and deletes them afterwards, whoever made them."""
    pairs: list[tuple[str, str]] = []
    yield pairs
    for element_type, element_id in pairs:
        owner.delete(element_type, element_id)


def test_create_gets_a_v7_id_and_no_author_for_the_owner(owner: Client, made: list[tuple[str, str]]) -> None:
    el = owner.create("character", {"name": "Wire A", "description": "first"})
    made.append(("character", el["id"]))
    assert el["type"] == "character" and el["id"][14] == "7" and el["created_by"] is None
    assert owner.get("character", el["id"])["description"] == "first"


def test_same_key_replays_and_a_different_payload_is_refused(owner: Client, made: list[tuple[str, str]]) -> None:
    key, eid = str(uuid.uuid4()), str(uuid7())
    body = {"id": eid, "name": "Idem"}
    first = owner.send("POST", "character/", body, {"Idempotency-Key": key})
    again = owner.send("POST", "character/", body, {"Idempotency-Key": key})
    made.append(("character", eid))
    assert first.response is not None and again.response is not None
    assert (first.response.status, again.response.status) == (201, 201)
    assert first.response.header("Idempotent-Replay") is None and again.response.header("Idempotent-Replay") == "true"
    with pytest.raises(ApiError) as other:
        owner.create("character", {"name": "Other"}, idempotency_key=key)
    assert (other.value.status, other.value.code, other.value.is_idempotency_conflict) == (
        409,
        "idempotency_error",
        True,
    )
    with pytest.raises(ApiError) as clash:  # a fresh key, the same id: a conflict, not a replay
        owner.create("character", body)
    assert clash.value.is_id_conflict and clash.value.param == "id"


def test_put_replaces_and_patch_merges(owner: Client, made: list[tuple[str, str]]) -> None:
    eid = str(uuid7())
    made.append(("character", eid))
    assert owner.upsert("character", eid, {"name": "Put One", "description": "d"})["description"] == "d"
    assert owner.upsert("character", eid, {"name": "Put Two"})["description"] == ""  # PUT replaces
    patched = owner.patch("character", eid, {"description": "p", "created_by": "dropped"})  # sanitised before sending
    assert (patched["name"], patched["description"], patched["created_by"]) == ("Put Two", "p", None)
    raw = owner.call(
        "PATCH", f"character/{eid}/", {"description": "q", "created_by": os.environ["OW_STAGING_MEMBERSHIP"]}
    )
    assert raw["created_by"] is None  # a write body that carries created_by has it dropped, never an error
    with pytest.raises(ApiError) as unknown:
        owner.patch("character", eid, {"nonsense_field": 1})
    assert (unknown.value.status, unknown.value.param) == (422, "nonsense_field")


def test_name_is_required_but_may_be_empty_and_null_is_not_zero(owner: Client, made: list[tuple[str, str]]) -> None:
    with pytest.raises(ApiError) as nameless:
        owner.create("character", {"description": "nameless"})
    assert (nameless.value.status, nameless.value.param) == (422, "name")
    blank = owner.create("character", {"name": ""})
    null_name = owner.create("character", {"name": None})
    made += [("character", blank["id"]), ("character", null_name["id"])]
    assert (blank["name"], null_name["name"]) == ("", "")  # wire fact: required means the key is present
    unset = owner.create("character", {"name": "Nulls", "height": None})
    zero = owner.create("character", {"name": "Zero", "height": 0})
    made += [("character", unset["id"]), ("character", zero["id"])]
    assert (unset["height"], zero["height"]) == (None, 0)
    with pytest.raises(ApiError) as bad:  # the raw call: the typed create refuses this before sending
        owner.call("POST", "character/", {"id": str(uuid7()), "name": "StrInt", "height": "tall"})
    assert (bad.value.status, bad.value.param) == (422, "height")
    with pytest.raises(ValueError, match=r"character\.height"):
        owner.create("character", {"name": "StrInt", "height": "tall"})


def test_links_dedupe_tolerate_absent_ids_and_are_scrubbed_on_delete(
    owner: Client, made: list[tuple[str, str]]
) -> None:
    person = owner.create("character", {"name": "Linker"})
    family = owner.create("family", {"name": "Linked"})
    made.append(("character", person["id"]))
    fid = family["id"]
    assert owner.edit_links("character", person["id"], "family", add=[fid, fid])["family"] == [fid]
    assert owner.edit_links("character", person["id"], "family", remove=[str(uuid7())])["family"] == [fid]
    with pytest.raises(ApiError) as missing:
        owner.edit_links("character", person["id"], "family", add=[str(uuid7())])
    assert (missing.value.status, missing.value.code) == (400, "invalid_link")
    for field in ("name", "no_such_field"):  # a scalar and an unknown name are both refused the same way
        with pytest.raises(ApiError) as refused:
            owner.edit_links("character", person["id"], field, add=[fid])
        assert (refused.value.status, refused.value.param) == (422, field)
    owner.delete("family", fid)
    owner.delete("family", fid)  # a second delete is a 204 too
    assert owner.get("character", person["id"])["family"] == []
    with pytest.raises(ApiError) as gone:
        owner.get("family", fid)
    assert gone.value.status == 404


def test_bulk_partial_atomic_cycles_and_replay(owner: Client, made: list[tuple[str, str]]) -> None:
    a, b, bad = str(uuid7()), str(uuid7()), str(uuid7())
    made += [("character", a), ("character", b)]
    partial = owner.bulk(
        [
            {"type": "character", "element": {"id": a, "name": "Cyc1", "friends": [b]}},
            {"type": "character", "element": {"id": b, "name": "Cyc2", "friends": [a]}},
            {"type": "character", "element": {"id": bad, "name": "Bad", "friends": [str(uuid7())]}},
        ]
    )
    assert partial.errors and [s["status"] for s in partial.items] == [201, 201, 400]
    assert partial.items[2]["error"]["code"] == "invalid_link"
    assert owner.get("character", a)["friends"] == [b] and owner.get("character", b)["friends"] == [a]
    with pytest.raises(ApiError):
        owner.get("character", bad)  # the failed slot wrote nothing

    ok, nope = str(uuid7()), str(uuid7())
    atomic = owner.bulk(
        [
            {"type": "character", "element": {"id": ok, "name": "AtomicOk"}},
            {"type": "character", "element": {"id": nope, "name": "AtomicBad", "friends": [str(uuid7())]}},
        ],
        atomic=True,
    )
    assert atomic.errors and [s["status"] for s in atomic.items] == [201, 400]  # the counterfactual 201
    with pytest.raises(ApiError) as rolled_back:
        owner.get("character", ok)
    assert rolled_back.value.status == 404

    key = str(uuid.uuid4())
    one = owner.bulk([{"type": "character", "element": {"name": "Keyed"}}], idempotency_key=key)
    two = owner.bulk([{"type": "character", "element": {"name": "Keyed"}}], idempotency_key=key)
    made.append(("character", one.items[0]["id"]))
    assert (one.was_replay, two.was_replay) == (False, True) and one.items == two.items


def test_the_change_feed_carries_upserts_and_deletes_but_not_world_meta(
    owner: Client, made: list[tuple[str, str]]
) -> None:
    el = owner.create("character", {"name": "Feed"})
    made.append(("character", el["id"]))
    seen = {c["op"] for c in owner.walk_changes(limit=200)}
    assert {"upsert", "delete"} <= seen
    world = owner.get_world()
    head = owner.changes(limit=1)["head"]
    owner.patch_world({"name": world["name"] + " probe"})
    try:
        assert owner.changes(limit=1)["head"] == head  # a world-meta change does not enter /changes
    finally:
        owner.patch_world({"name": world["name"]})
    with pytest.raises(ApiError) as unknown:
        owner.patch_world({"nonsense": 1})
    assert (unknown.value.status, unknown.value.param) == (422, "nonsense")


def test_a_contributor_changes_only_what_they_made(owner: Client, contrib: Client, made: list[tuple[str, str]]) -> None:
    theirs = contrib.create("character", {"name": "Contrib One"})
    made.append(("character", theirs["id"]))
    assert theirs["created_by"] == os.environ["OW_STAGING_MEMBERSHIP"]
    assert contrib.patch("character", theirs["id"], {"description": "mine"})["description"] == "mine"

    mine = owner.create("character", {"name": "Owner's"})
    made.append(("character", mine["id"]))
    attempts = {
        "patch": lambda: contrib.patch("character", mine["id"], {"description": "x"}),
        "delete": lambda: contrib.delete("character", mine["id"]),
        "put": lambda: contrib.upsert("character", mine["id"], {"name": "overwritten"}),
        "links": lambda: contrib.edit_links("character", mine["id"], "family", add=[]),
    }
    for name, attempt in attempts.items():
        with pytest.raises(ApiError) as refused:
            attempt()
        assert (refused.value.status, refused.value.code, refused.value.is_not_author) == (403, "not_author", True), (
            name
        )
    assert owner.get("character", mine["id"])["name"] == "Owner's"

    own, stolen = {"name": "ContribBulkOk"}, {"id": mine["id"], "name": "stolen"}
    result = contrib.bulk([{"type": "character", "element": own}, {"type": "character", "element": stolen}])
    made.append(("character", result.items[0]["id"]))
    assert [s["status"] for s in result.items] == [201, 403] and result.items[1]["error"]["code"] == "not_author"

    with pytest.raises(ApiError) as world:
        contrib.patch_world({"name": "no"})
    assert (world.value.status, world.value.is_owner_only, world.value.is_not_author) == (403, True, False)
    assert contrib.get_world()["id"] == owner.get_world()["id"] and contrib.changes(limit=1)["head"] >= 0


def test_a_key_needs_its_own_pin(owner: Client) -> None:
    pairs = [
        (os.environ["OW_STAGING_CONTRIB_KEY"], os.environ["OW_STAGING_OWNER_PIN"]),
        (os.environ["OW_STAGING_OWNER_KEY"], os.environ["OW_STAGING_CONTRIB_PIN"]),
        (os.environ["OW_STAGING_OWNER_KEY"], None),
    ]
    for key, pin in pairs:
        with pytest.raises(ApiError) as refused:
            _client(key, pin).create("character", {"name": "x"})
        assert (refused.value.status, refused.value.code) == (401, "invalid_credentials")


def test_an_id_from_another_world_is_a_conflict_everywhere(owner: Client) -> None:
    demo = _client("0000000000", None)  # staging carries the seeded demo world, readable without a PIN
    foreign = demo.list_page("character", limit=1)["data"][0]["id"]
    with pytest.raises(ApiError) as put:
        owner.upsert("character", foreign, {"name": "steal"})
    with pytest.raises(ApiError) as post:
        owner.create("character", {"id": foreign, "name": "steal"})
    slot = owner.bulk([{"type": "character", "element": {"id": foreign, "name": "steal"}}]).items[0]
    assert (put.value.is_id_conflict, post.value.is_id_conflict) == (True, True)
    assert (slot["status"], slot["error"]["code"]) == (409, "id_conflict")


def test_unicode_and_the_extension_cap(owner: Client, made: list[tuple[str, str]]) -> None:
    with pytest.raises(ApiError) as surrogate:
        owner.create("character", {"name": "bad \ud800 name"})
    assert (surrogate.value.status, surrogate.value.param) == (422, "name")
    with pytest.raises(ApiError) as big:
        owner.create("character", {"name": "big", "x_probe_blob": "a" * 70000})
    assert (big.value.status, big.value.param) == (422, "extensions")
    ext = owner.create("character", {"name": "ext", "x_probe_flag": True})
    made.append(("character", ext["id"]))
    assert ext["x_probe_flag"] is True
