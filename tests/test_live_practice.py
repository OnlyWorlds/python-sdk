"""Writes against the production practice world. Set ``OW_LIVE=1``; without it these skip.

The practice world is a world anyone may write to: its key and PIN are published on the docs' Keys and
PINs page, and every night at 03:00 UTC it goes back to the same copy. The literals are read from the
docs' own file of them (``contract/practice.json`` on the docs site's repository), never copied here,
so a rotated key needs no change in this repository. Each test makes what it writes, names it with a
fresh id, and deletes it again; a run sends a few dozen requests, under the world's 60 a minute.
"""

from __future__ import annotations

import json
import os
import urllib.request
import uuid

import pytest

from onlyworlds import ApiError, Client, PreconditionFailed

pytestmark = pytest.mark.skipif(not os.environ.get("OW_LIVE"), reason="set OW_LIVE=1 for the live practice-world writes")

LITERALS = "https://raw.githubusercontent.com/OnlyWorlds/onlyworlds.github.io/main/contract/practice.json"


@pytest.fixture(scope="module")
def practice() -> dict[str, str]:
    with urllib.request.urlopen(LITERALS, timeout=20) as r:  # a failure here fails the run: never a silent skip
        lit = json.load(r)
    assert lit["key"].startswith("ow_w_") and lit["pin"] and lit["world_id"]
    return lit


@pytest.fixture(scope="module")
def writer(practice: dict[str, str]) -> Client:
    return Client(practice["key"], practice["pin"])


def _name(what: str) -> str:
    return f"{what} (package test {uuid.uuid4().hex[:8]})"


def test_the_key_is_the_practice_world(writer: Client, practice: dict[str, str]) -> None:
    me = writer.me()
    assert me["world"]["id"] == practice["world_id"] and me["world"]["name"] == "Practice"
    assert me["scope"] == "write"


def test_create_names_the_client_and_a_replay_writes_once(writer: Client) -> None:
    key = str(uuid.uuid4())
    body = {"name": _name("Ilse the Ranger")}
    first = writer.create("character", dict(body), idempotency_key=key)
    try:
        assert first["type"] == "character" and first["name"] == body["name"]
        assert first["changed_client"] == "python" and first["changed_via"] == "api"
        again = writer.create("character", dict(body), idempotency_key=key)
        assert again["id"] == first["id"]
        assert [e["id"] for e in writer.list_page("character", filter={"name": body["name"]})["data"]] == [first["id"]]
    finally:
        writer.delete("character", first["id"])


def test_a_stale_if_match_writes_nothing(writer: Client) -> None:
    peak = writer.create("location", {"name": _name("Dragon Peak")})
    try:
        moved = writer.patch("location", peak["id"], {"supertype": "Mountain"}, if_match=peak["change_seq"])
        assert moved["change_seq"] > peak["change_seq"]
        with pytest.raises(PreconditionFailed) as err:
            writer.patch("location", peak["id"], {"supertype": "Hill"}, if_match=peak["change_seq"])
        assert err.value.status == 412 and err.value.current is not None
        assert err.value.current["supertype"] == "Mountain"
        assert writer.get("location", peak["id"])["supertype"] == "Mountain"
    finally:
        writer.delete("location", peak["id"])


def test_refusals_name_what_they_refuse(writer: Client) -> None:
    with pytest.raises(ApiError) as misspelt:
        writer.create("character", {"name": _name("Nobody"), "nmae": "x"})
    assert misspelt.value.status == 422 and misspelt.value.param == "nmae"
    with pytest.raises(ApiError) as nowhere:
        writer.create("character", {"name": _name("Nobody"), "location": str(uuid.uuid4())})
    assert nowhere.value.status == 400 and nowhere.value.code == "invalid_link" and nowhere.value.param == "location"


def test_a_wrong_pin_is_refused_by_name(practice: dict[str, str]) -> None:
    wrong = "1000" if practice["pin"] != "1000" else "1001"
    with pytest.raises(ApiError) as err:
        Client(practice["key"], wrong).create("character", {"name": _name("Nobody")})
    assert err.value.status == 401 and err.value.code == "invalid_credentials" and err.value.param == "API-Pin"


def test_a_deleted_element_reads_gone(writer: Client) -> None:
    made = writer.create("object", {"name": _name("Ember stone")})
    writer.delete("object", made["id"])
    with pytest.raises(ApiError) as err:
        writer.get("object", made["id"])
    assert err.value.status == 410 and err.value.code == "gone"
    writer.delete("object", made["id"])  # a second delete is the idempotent 204
