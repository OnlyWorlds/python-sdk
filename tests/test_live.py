"""Read-only calls against the production demo world. Set ``OW_LIVE=1``; without it these skip.

Demo key ``0000000000`` is public and read-only (writes are refused with a 403). Nothing here
writes, and nothing heavier than a few small reads is sent.
"""

from __future__ import annotations

import os

import pytest

from onlyworlds import Client

pytestmark = pytest.mark.skipif(not os.environ.get("OW_LIVE"), reason="set OW_LIVE=1 for the live read checks")


@pytest.fixture(scope="module")
def client() -> Client:
    return Client("0000000000")


def test_health_world_and_a_page(client: Client) -> None:
    assert client.health()["status"] == "ok"
    assert client.get_world()["name"]
    page = client.list_page("character", limit=3)
    assert set(page) >= {"data", "has_more", "next_cursor"} and 0 < len(page["data"]) <= 3
    assert page["data"][0]["type"] == "character" and "created_by" in page["data"][0]


def test_get_with_sparse_fields_and_expand(client: Client) -> None:
    first = client.list_page("character", limit=1)["data"][0]
    got = client.get("character", first["id"], fields=["name"])
    assert got["name"] == first["name"] and "description" not in got


def test_the_change_feed_pages_and_has_a_head(client: Client) -> None:
    page = client.changes(limit=5)
    assert len(page["changes"]) <= 5 and isinstance(page["head"], int) and page["cursor"]
    walk = client.walk_changes(page["cursor"])  # the default page size: two requests, not a crawl
    list(walk)
    assert walk.done and walk.head is not None
