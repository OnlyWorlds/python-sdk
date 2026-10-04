from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from conftest import FakeTransport, jresp

from onlyworlds import Client, export_world, read_folder
from onlyworlds.http import Response


def test_export_paginates_and_writes_a_folder(tmp_path: Path, make_client: Callable[..., Client]) -> None:
    chars = [{"id": f"c0000000-0000-7000-8000-00000000000{i}", "type": "character", "name": f"C{i}"} for i in range(3)]
    world = {"id": "w1", "name": "World", "time_range_current": 3, "public_read": False}

    def handler(method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> Response:
        u = urlparse(url)
        q = parse_qs(u.query)
        path = u.path.removeprefix("/api/v2/")
        assert method == "GET"
        if path == "world/":
            return jresp(200, world)
        if path == "character/":
            if "cursor" not in q:
                return jresp(200, {"data": chars[:2], "has_more": True, "next_cursor": "seq:2/x"})
            assert q["cursor"] == ["seq:2/x"]
            return jresp(200, {"data": chars[2:], "has_more": False, "next_cursor": None})
        return jresp(200, {"data": [], "has_more": False, "next_cursor": None})

    t = FakeTransport(handler=handler)
    rep = export_world(tmp_path / "out", client=make_client(t))
    assert rep.counts == {"character": 3}
    assert any("cursor=seq%3A2%2Fx" in c.url for c in t.calls)  # opaque cursor, url-quoted
    assert len(t.calls) == 1 + 22 + 1  # world, one page per type, a second character page
    f = read_folder(tmp_path / "out")
    assert len(f.elements) == 3
    w = json.loads((tmp_path / "out" / "world.json").read_text(encoding="utf-8"))
    assert list(w) == ["id", "name", "time_current", "public_read", "format_version"]
