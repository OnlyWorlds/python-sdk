"""A line of a report's ``consequences``: the npm SDK's lines table (``tests/fixtures/report/lines.json``, the same
bytes, sha256 held here and there) gives each line, the element its address names (or none) and the words a reader
shows, and each text with the lines it splits into. Every row is compared whole, the address and the words exactly."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import parse_ow_link, read_report_line, read_report_lines

REPO = Path(__file__).resolve().parent.parent
TABLE = REPO / "tests" / "fixtures" / "report" / "lines.json"
TABLE_SHA = "b5a7901f1317b2c1"
BYTES = TABLE.read_bytes()
FX: dict[str, Any] = json.loads(BYTES.decode("utf-8"))
WORLD: str = FX["world"]
ID = "01a1d4ef-0000-7000-8000-000000000084"


def test_the_table_is_the_one_both_packages_hold() -> None:
    assert hashlib.sha256(BYTES).hexdigest()[:16] == TABLE_SHA
    cases = FX["cases"]
    assert any(c["address"] is None for c in cases)
    assert any(c["address"] is not None and c["words"] == c["line"] for c in cases)
    assert any(c["address"] is not None and c["words"] != c["line"] for c in cases)


@pytest.mark.parametrize("case", FX["cases"], ids=[c["kind"] for c in FX["cases"]])
def test_line(case: dict[str, Any]) -> None:
    got = read_report_line(case["line"], world=WORLD)
    assert got.line == case["line"]
    assert got.address == case["address"]
    assert got.words == case["words"]
    if got.address is None:
        assert got.reading is None and got.start is None and got.end is None
    else:
        assert got.start is not None and got.end is not None and got.reading is not None
        assert parse_ow_link(case["line"][got.start : got.end]) == got.reading
        assert f"ow://{got.reading.type}/{got.reading.id}" == case["address"]


@pytest.mark.parametrize("text", FX["texts"], ids=[t["kind"] for t in FX["texts"]])
def test_text(text: dict[str, Any]) -> None:
    got = read_report_lines(text["text"], world=WORLD)
    assert [(g.line, g.address, g.words) for g in got] == [(t["line"], t["address"], t["words"]) for t in text["lines"]]


def test_without_a_world_only_an_address_with_no_world_names_an_element_here() -> None:
    assert read_report_line(f"Built: ow://{WORLD}/object/{ID}").address is None
    assert read_report_line(f"Built: ow://object/{ID}").address == f"ow://object/{ID}"
    assert read_report_line(f"Built: ow://object/{ID}", world=None).words == "Built"


def test_the_world_is_read_as_written() -> None:
    assert read_report_line(f"Built: ow://{WORLD}/object/{ID}", world=WORLD.upper()).address is None


def test_refusals() -> None:
    with pytest.raises(TypeError):
        read_report_line(3)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        read_report_lines(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        read_report_line("x", world=7)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        read_report_line("x", wrold=WORLD)  # type: ignore[call-arg]
