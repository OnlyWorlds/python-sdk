"""The spine profile (schema-dist ``profiles/spine.md``, serial 55): ``read_spine_element`` on every
conformance case in ``codegen/schema-dist/profiles/spine.fixture.json``, vendored with the distribution;
the closed lists against the page; the trim and the fold the room profile defines. The fixture's
calendar steps are the npm SDK kernel's to check: this package has no calendar kernel."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from onlyworlds import SPINE_KINDS, FolderElement, SpineRead, read_spine_element
from onlyworlds.spine import (
    SPINE_ACCESS,
    SPINE_AUDIENCE,
    SPINE_FREE_TYPES,
    SPINE_LAYERS,
    SPINE_PROBE_VERBS,
    SPINE_STATUSES,
)

REPO = Path(__file__).resolve().parent.parent
PROFILES = REPO / "codegen" / "schema-dist" / "profiles"
FIXTURE = PROFILES / "spine.fixture.json"
PAGE = PROFILES / "spine.md"


def load_fixture() -> dict[str, Any]:
    assert FIXTURE.is_file(), f"no spine fixture at {FIXTURE}"
    doc: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert doc["profile"] == "spine"
    return doc


def page_lines() -> list[str]:
    return PAGE.read_text(encoding="utf-8").splitlines()


def test_read_spine_element_reads_every_fixture_case_as_its_read_block() -> None:
    cases = load_fixture()["cases"]
    wrong = [
        f"{c['name']}: {c['type']} {c['element']} read {got}, the fixture says {c['read']}"
        for c in cases
        if (got := read_spine_element(c["type"], c["element"]).as_dict()) != c["read"]
    ]
    assert wrong == []
    assert len(cases) >= 34, f"the fixture holds {len(cases)} cases"  # dist.55's count; a later serial adds cases


def test_the_calendar_block_is_there_with_its_six_steps_and_is_not_checked_here() -> None:
    """The steps read the page's calendar config through a calendar-profile kernel; the npm SDK's (4.70.0)
    checks them. This package has none, so it only holds that the block it would hand on is whole."""
    calendar = load_fixture()["calendar"]
    steps = calendar["steps"]
    assert len(steps) == 6
    assert all(set(s) == {"step", "reads", "weekday"} for s in steps)
    assert steps[0] == {"step": 0, "reads": "1 January 2012", "weekday": "Sunday"}
    assert {"step": 5410, "reads": "24 October 2026", "weekday": "Saturday"} in steps


def test_spine_kinds_are_the_pages_table() -> None:
    rows = [line for line in page_lines() if re.match(r"^\| [A-Z][a-z]+ \| `", line)]
    table = {
        cells[1].strip().lower(): tuple(re.findall(r"`([^`]+)`", cells[2]))
        for cells in (row.split("|") for row in rows)
    }
    assert table == SPINE_KINDS
    row_kinds = sum(len(SPINE_KINDS[t]) for t in ("object", "location", "construct")) + 2 + 1  # Law less Charter
    assert row_kinds == 25  # the page: "the 25 a picture draws as marks", plus Charter


def test_the_value_lists_are_the_pages_key_rows() -> None:
    def words(key: str) -> tuple[str, ...]:
        (row,) = [line for line in page_lines() if line.startswith(f"| `{key}` |")]
        return tuple(dict.fromkeys(re.findall(r"`([^`]+)`", row.split("|")[2])))

    assert words("x_spine_access") == SPINE_ACCESS
    assert words("x_spine_status") == SPINE_STATUSES
    assert words("x_spine_layer") == SPINE_LAYERS
    assert words("x_spine_audience") == SPINE_AUDIENCE
    (line,) = [line for line in page_lines() if line.startswith("**The probe form**")]
    forms = re.findall(r"`([^`]+)`", line.split("**No credential")[0])
    assert len(forms) == len(SPINE_PROBE_VERBS)
    assert all(form.startswith(verb + " ") for verb, form in zip(SPINE_PROBE_VERBS, forms, strict=True))
    assert "A Character, an Institution and a Collective take any supertype" in PAGE.read_text(encoding="utf-8")
    assert SPINE_FREE_TYPES == ("character", "institution", "collective")


# Unicode's White_Space property, the 25 code points (PropList.txt), typed here apart from the room module's
# constant so the sweep below checks one against the other.
WHITE_SPACE = {
    *range(0x09, 0x0E),
    0x20,
    0x85,
    0xA0,
    0x1680,
    *range(0x2000, 0x200B),
    0x2028,
    0x2029,
    0x202F,
    0x205F,
    0x3000,
}


def test_the_trim_strips_exactly_white_space_over_the_whole_bmp() -> None:
    """Trimmed as the room profile defines it: White_Space at both ends and nothing else, so a byte order
    mark, a zero width space and U+001C (which ``str.strip()`` would take) all stay."""
    stripped = {
        cp
        for cp in range(0x10000)
        if read_spine_element("object", {"supertype": f"{chr(cp)}Tool{chr(cp)}"}).kind == "Tool"
    }
    assert stripped == WHITE_SPACE
    assert read_spine_element("object", {"supertype": "Tool", "x_spine_status": "\x1clive"}).status is None
    assert read_spine_element("object", {"supertype": "Tool", "x_spine_status": "\u3000Live\u2029"}).status == "live"
    assert read_spine_element("object", {"supertype": "Tool", "x_spine_truth": "\u3000 \u2028"}).truth is None
    assert read_spine_element("object", {"supertype": "Tool", "x_spine_probe": " npm\xa0x "}).probe == "unsupported"


def test_the_fold_is_unicode_simple_case_folding_not_casefold() -> None:
    assert read_spine_element("title", {"supertype": "\u017feat"}).kind == "Seat"  # long s simple-folds to s
    assert read_spine_element("object", {"supertype": "HOO\u212a"}).kind == "Hook"  # the Kelvin sign to k
    # U+FB01 (the fi ligature) full-folds to "fi", which str.casefold() would match; simple folding keeps it.
    assert "Pro\ufb01le".casefold() == "profile"
    assert read_spine_element("construct", {"supertype": "Pro\ufb01le"}).kind == "off-list"
    assert read_spine_element(" OBJECT ", {"supertype": "tool"}).kind == "Tool"


def test_a_folder_element_is_read_by_its_body() -> None:
    body = {"id": "0192a000-aaaa-7bbb-8ccc-000000000001", "name": "Atlas", "supertype": "Tool"}
    path = Path("elements/object/atlas.json")
    el = FolderElement(id=body["id"], type="object", type_inferred=True, body=body, path=path, layout="elements")
    assert read_spine_element(el.type, el) == SpineRead(kind="Tool")


def test_verified_at_must_be_a_day_on_the_calendar() -> None:
    def at(value: str) -> SpineRead:
        return read_spine_element("object", {"supertype": "Tool", "x_spine_verified": {"at": value, "by": "t"}})

    assert at(" 2026-10-24 ").verified_at == "2026-10-24"
    assert at("2026-10-24T10:00:00Z").verified_at == "2026-10-24T10:00:00Z"
    assert at("2026-02-30").verified_at is None
    assert at("2026-02-30").dropped == ('x_spine_verified: {"at": "2026-02-30", "by": "t"}',)
    assert at("\u0662\u0660\u0662\u0666-10-24").verified_at is None  # Arabic-Indic digits are not the form's


def test_null_is_not_stated_and_drops_nothing_and_an_empty_depends_on_is_stated() -> None:
    keys = ("address", "truth", "access", "status", "layer", "audience", "depends_on", "probe", "verified")
    read = read_spine_element("object", {"supertype": "Tool", **{f"x_spine_{k}": None for k in keys}})
    assert read == SpineRead(kind="Tool")
    assert read_spine_element("object", {"supertype": "Tool", "x_spine_depends_on": []}).depends_on == ()
