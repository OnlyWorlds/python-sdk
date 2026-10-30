"""The Open with menu's rows: ``openers_for`` on every case of ``tests/fixtures/openers.fixture.json``, the same bytes
as the npm SDK's ``test/fixtures/openers.fixture.json`` (both suites hold its sha256), every expected row written by
hand. Then ``TOOLS``, the baked tools list, through the same function. A missing fixture fails, never skips."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import TOOLS, AddressError, openers_for, parse_ow_link

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "openers.fixture.json"
FIXTURE_SHA256 = "5a9ebbc8604d2fc87078fef25156dd2e767605a1b08cb2bec43e37c6bc2fd9db"
CASES = 54
WORLD = "0199c3a1-7b2e-7c3d-8e4f-5a6b7c8d9e0f"
ELEMENT = "0199c3a1-7b2e-7c3d-8e4f-5a6b7c8d9e1a"


def answer(doc: dict[str, Any], c: dict[str, Any]) -> dict[str, Any]:
    """One case's answer in the fixture's own shape: ``{"expect": ...}`` or ``{"refuse": ...}``."""
    try:
        return {"expect": openers_for(doc["lists"][c["tools"]], c["kind"], c["address"], c["surface"])}
    except AddressError as err:
        return {"refuse": {"error": "address", "reason": err.reason}}
    except TypeError as err:
        refuse = c.get("refuse")
        if refuse is not None and refuse["error"] == "type":
            return {"refuse": refuse if refuse["names"] in str(err) else {"error": "type", "message": str(err)}}
        return {"threw": repr(err)}


def test_every_case_of_the_shared_fixture() -> None:
    data = FIXTURE.read_bytes()
    assert hashlib.sha256(data).hexdigest() == FIXTURE_SHA256
    doc = json.loads(data.decode("utf-8"))
    wrong = []
    for c in doc["cases"]:
        assert c["tools"] in doc["lists"], c["name"]
        want = {"refuse": c["refuse"]} if "refuse" in c else {"expect": c["expect"]}
        got = answer(doc, c)
        if got != want:
            wrong.append(f"{c['name']}: gave {got}, want {want}")
    for line in wrong:
        print(line)
    assert wrong == []
    assert len(doc["cases"]) == CASES


def test_a_reading_from_parse_ow_link_gives_the_same_rows() -> None:
    link = f"https://www.onlyworlds.com/w/{WORLD}/character/{ELEMENT}@3?lens={ELEMENT}"
    plain = {"form": "text", "world": WORLD, "type": "character", "id": ELEMENT}
    surface = {"audience": "member", "signed_in": False}
    assert openers_for(TOOLS, "element", parse_ow_link(link), surface) == openers_for(TOOLS, "element", plain, surface)


def test_tools_gives_the_sites_row_then_each_listed_tool_with_a_door_in_the_lists_order() -> None:
    assert len(TOOLS) >= 1
    member = openers_for(TOOLS, "world", {"form": "human", "world": WORLD}, {"audience": "member", "signed_in": True})
    offered = [t for t in TOOLS if t["rung"] == "listed" and t["open"] is not None and t["open"]["world"] is not None]
    assert [r["id"] for r in member] == ["onlyworlds", *(t["id"] for t in offered)]
    assert member[0]["href"] == f"https://www.onlyworlds.com/w/{WORLD}"
    for r in member[1:]:
        assert r["href"].startswith("https://") and WORLD in r["href"] and "{" not in r["href"], r["href"]
    public = openers_for(TOOLS, "world", {"form": "human", "world": WORLD}, {"audience": "public"})
    free = [t["id"] for t in offered if t["open"] is not None and t["open"]["needs"] is None]
    assert [r["id"] for r in public] == ["onlyworlds", *free]


@pytest.mark.parametrize("value", ["no", None, 0, 1, "false"])
def test_online_that_is_not_a_boolean_is_refused_by_name(value: object) -> None:
    with pytest.raises(TypeError, match="surface online is a boolean"):
        openers_for(TOOLS, "world", {"form": "human", "world": WORLD}, {"audience": "member", "online": value})


def test_online_false_keeps_every_href_and_true_is_the_default() -> None:
    address = {"form": "human", "world": WORLD}
    online = openers_for(TOOLS, "world", address, {"audience": "member", "signed_in": True})
    offline = openers_for(TOOLS, "world", address, {"audience": "member", "signed_in": True, "online": False})
    assert openers_for(TOOLS, "world", address, {"audience": "member", "signed_in": True, "online": True}) == online
    assert [r["href"] for r in offline] == [r["href"] for r in online]
    for r in offline:
        web = r["href"].lower().startswith(("http:", "https:"))
        assert r["state"] == ("Needs a connection" if web else None), r
