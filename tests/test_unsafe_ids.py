"""``write_folder`` refuses an element id that cannot name a file. The shared cases
(``tests/fixtures/unsafe-ids.cases.json``, the same bytes as the npm SDK's ``test/fixtures/unsafe-ids.cases.json``;
both suites hold its sha256): an id that holds ``/``, ``\\`` or a control character, or is ``.`` or ``..``, is
refused whatever the name, since ``<id>.json`` would leave its type folder, with a ValueError naming the type, the
id as JSON text and the case's why, and nothing is written (the target is not made, an empty one is left as it
was). Each written case gives its path. Then the same refusal through ``export_world``, whose ids come from the
server."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
from conftest import FakeTransport, jresp

from onlyworlds import Client, export_world, folder, legendkeeper, write_folder
from onlyworlds.http import Response
from onlyworlds.okf import write_bundle

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "unsafe-ids.cases.json"
FIXTURE_SHA256 = "cc6c0c016b441c0ebdc2840304f28c69e05a7ddf6eb0a333b343188717eb5581"
W = {"id": "w-1", "name": "W"}


def _data() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_bytes())
    return data


def _want(etype: str, case: Mapping[str, str]) -> str:
    return f"{etype} element id {json.dumps(case['id'], ensure_ascii=False)} cannot be a file name: {case['why']}."


def test_the_cases_file_is_the_pinned_bytes() -> None:
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA256
    data = _data()
    assert data["version"] == 1
    assert len(data["refused"]) == 19
    assert len(data["written"]) == 5


@pytest.mark.parametrize("case", _data()["refused"], ids=lambda c: json.dumps(c["id"]))
def test_a_refused_id_writes_nothing(tmp_path: Path, case: dict[str, str]) -> None:
    out = tmp_path / "out"
    elements = {"character": [{"id": "ok-1", "name": "Fine"}, {"id": case["id"], "name": case["name"]}]}
    with pytest.raises(ValueError, match=f"^{re.escape(_want('character', case))}$"):
        write_folder(out, W, elements)
    assert list(tmp_path.iterdir()) == [], "the target is not made, and no temp folder is left"


def test_an_empty_target_is_left_as_it_was(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ValueError, match="cannot be a file name"):
        write_folder(out, W, {"zone": [{"id": "../../x", "name": ""}]})
    assert out.is_dir() and list(out.iterdir()) == []
    assert list(tmp_path.iterdir()) == [out]


@pytest.mark.parametrize("case", _data()["written"], ids=lambda c: json.dumps(c["id"]))
def test_a_written_id_lands_at_its_path(tmp_path: Path, case: dict[str, str]) -> None:
    out = tmp_path / "out"
    write_folder(out, W, {"character": [{"id": case["id"], "name": case["name"]}]})
    files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    assert files == sorted([case["path"], "world.json"])
    assert json.loads((out / case["path"]).read_bytes())["id"] == case["id"]


def test_the_world_id_names_no_path(tmp_path: Path) -> None:
    out = tmp_path / "out"
    write_folder(out, {"id": "../w", "name": "W"}, {"character": [{"id": "c", "name": "C"}]})
    files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    assert files == ["elements/character/c--c.json", "world.json"]


ESCAPES = ["../../x", "../x"] + (["C:evil", "D:/x"] if sys.platform == "win32" else [])


@pytest.mark.parametrize("eid", ESCAPES)
def test_the_second_guard_alone_refuses_a_path_outside_the_type_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, eid: str
) -> None:
    """With the character rule taken out, the containment check still refuses, before anything is written."""
    monkeypatch.setattr(folder, "_unsafe_id_why", lambda _eid: None)
    out = tmp_path / "w" / "out"
    with pytest.raises(ValueError, match="which does not lie inside its type folder"):
        write_folder(out, W, {"character": [{"id": eid, "name": ""}]})
    assert list(tmp_path.iterdir()) == []


def test_the_second_guard_passes_a_plain_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert folder._inside(tmp_path / "out" / "elements" / "character", "v1.2.json")
    assert not folder._inside(tmp_path / "out", "../x.json")
    assert not folder._inside(tmp_path / "out", ".")
    if sys.platform == "win32":
        # A relative folder joined to a drive-relative name is that name alone: a path on drive C, outside.
        monkeypatch.chdir(tmp_path)
        assert not folder._inside(Path("w") / "out" / "elements" / "character", "C:evil.json")
        assert not folder._inside(Path("w") / "out", "D:/x.json")


def test_an_okf_bundle_path_outside_its_folder_is_refused(tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    with pytest.raises(ValueError, match="does not lie inside"):
        write_bundle({"index.md": "# W\n", "../escaped.md": "x"}, out)
    assert list(tmp_path.iterdir()) == []


def test_a_board_record_path_outside_its_folder_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not lie inside"):
        legendkeeper._check_records(tmp_path / "out", {"records/legendkeeper/boards/../../../../x.json": {}})
    legendkeeper._check_records(tmp_path / "out", {"records/legendkeeper/boards/doc-1.json": {}})
    assert list(tmp_path.iterdir()) == []


def test_export_world_refuses_an_id_from_the_server(tmp_path: Path, make_client: Callable[..., Client]) -> None:
    def handler(method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> Response:
        path = urlparse(url).path.removeprefix("/api/v2/")
        if path == "world/":
            return jresp(200, {"id": "w1", "name": "World"})
        if path == "me/":
            return jresp(404, {"error": {"type": "invalid_request_error", "code": "not_found", "message": "no"}})
        if path == "location/":
            rows = [{"id": "../../../escaped", "type": "location", "name": ""}]
            return jresp(200, {"data": rows, "has_more": False, "next_cursor": None})
        return jresp(200, {"data": [], "has_more": False, "next_cursor": None})

    out = tmp_path / "out"
    with pytest.raises(ValueError, match=re.escape('location element id "../../../escaped" cannot be a file name')):
        export_world(out, client=make_client(FakeTransport(handler=handler), attempts=1))
    assert list(tmp_path.iterdir()) == []
