"""The spine profile (schema-dist ``profiles/spine.md``, serial 60): ``read_spine_element`` on every
conformance case in ``codegen/schema-dist/profiles/spine.fixture.json``, vendored with the distribution;
the closed lists against the page; the trim and the fold the room profile defines; the fixture's
calendar steps through the page's calendar config and ``onlyworlds.calendar``."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from onlyworlds import SPINE_KINDS, FolderElement, SpineRead, read_spine_element
from onlyworlds.calendar import format_step, read_calendar_value, weekday_for_step
from onlyworlds.spine import (
    SPINE_ACCESS,
    SPINE_AUDIENCE,
    SPINE_FREE_TYPES,
    SPINE_KEYS,
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


def as_json(value: Any) -> str:
    """One canonical JSON text, so the comparison is JSON's: Python's ``==`` holds ``True == 1`` and
    ``1 == 1.0``, which JSON values do not."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def test_read_spine_element_reads_every_fixture_case_as_its_read_block() -> None:
    cases = load_fixture()["cases"]
    wrong = [
        f"{c['name']}: {c['type']} {c['element']} read {got}, the fixture says {c['read']}"
        for c in cases
        if as_json(got := read_spine_element(c["type"], c["element"]).as_dict()) != as_json(c["read"])
    ]
    assert wrong == []
    assert len(cases) >= 40, f"the fixture holds {len(cases)} cases"  # dist.56's count; a later serial adds cases


def page_calendar() -> dict[str, Any]:
    """The calendar config in the page's Time section: its one json block."""
    text = PAGE.read_text(encoding="utf-8")
    block = re.search(r"\*\*Time\.\*\*.*?```json\s(.*?)```", text, re.S)
    assert block, "no json block in the page's Time section"
    config: dict[str, Any] = json.loads(block.group(1))
    return config


def test_the_calendar_block_reads_through_the_page_config() -> None:
    """Each of the fixture's calendar steps reads, through the page's config and the calendar kernel, as
    written, with its weekday (the npm SDK's kernel, 4.70.0, checked the same steps)."""
    calendar = load_fixture()["calendar"]
    steps = calendar["steps"]
    assert len(steps) == 6
    assert all(set(s) == {"step", "reads", "weekday"} for s in steps)
    assert steps[0] == {"step": 0, "reads": "1 January 2012", "weekday": "Sunday"}
    assert {"step": 5410, "reads": "24 October 2026", "weekday": "Saturday"} in steps
    config = read_calendar_value(page_calendar())
    assert config is not None
    got = [
        {"step": s["step"], "reads": format_step(config, s["step"]), "weekday": weekday_for_step(config, s["step"])}
        for s in steps
    ]
    assert got == steps
    # The page's first drift: 29 February 2100 exists here (no century rule), as the fixture's note says.
    assert format_step(config, 32201) == "29 February 2100"


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


def test_the_thirteen_keys_are_the_pages_key_table() -> None:
    """Serial 60: "thirteen extension keys carry what no schema field holds", x_spine_retires the thirteenth."""
    keys = tuple(m[1] for line in page_lines() if (m := re.match(r"^\| `(x_spine_[a-z_]+)` \|", line)))
    assert keys == SPINE_KEYS
    assert len(SPINE_KEYS) == 13 and "x_spine_retires" in SPINE_KEYS
    assert "thirteen extension keys" in PAGE.read_text(encoding="utf-8")


def test_x_spine_retires_is_read_as_given_and_judges_nothing() -> None:
    """Serial 61's three rulings: the key is stated on any element that carries it (on a Tool too: the
    placement is the audit's); a non-string is not stated and named in dropped; a blank string is not
    stated and drops nothing, any other string is stated as given, untrimmed, its id form unchecked."""
    rid = "0190a1b2-0000-7000-8000-000000000001"
    assert read_spine_element("event", {"supertype": "Retirement", "x_spine_retires": rid}).retires == rid
    assert read_spine_element("object", {"supertype": "Tool", "x_spine_retires": rid}).retires == rid
    assert read_spine_element("event", {"supertype": "Launch", "x_spine_retires": rid}).retires == rid
    for value in (7, ["x"], {"id": rid}, True):
        read = read_spine_element("event", {"supertype": "Retirement", "x_spine_retires": value})
        assert read.retires is None
        assert as_json(read.as_dict()["dropped"]) == as_json([{"key": "x_spine_retires", "value": value}])
    for blank in ("", " ", chr(0x3000) + chr(0x2028)):  # ideographic space, line separator
        read = read_spine_element("event", {"supertype": "Retirement", "x_spine_retires": blank})
        assert read == SpineRead(kind="Retirement")
    for given in (f" {rid} ", "not an id", "\x1c"):
        assert read_spine_element("event", {"supertype": "Retirement", "x_spine_retires": given}).retires == given


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
    assert at("2026-02-30").dropped == ({"key": "x_spine_verified", "value": {"at": "2026-02-30", "by": "t"}},)
    assert at("\u0662\u0660\u0662\u0666-10-24").verified_at is None  # Arabic-Indic digits are not the form's


def test_null_is_not_stated_and_drops_nothing_and_an_empty_depends_on_is_stated() -> None:
    keys = ("address", "truth", "access", "status", "layer", "audience", "depends_on", "probe", "verified", "retires")
    read = read_spine_element("object", {"supertype": "Tool", **{f"x_spine_{k}": None for k in keys}})
    assert read == SpineRead(kind="Tool")
    assert read_spine_element("object", {"supertype": "Tool", "x_spine_depends_on": []}).depends_on == ()


def test_a_dropped_value_is_the_elements_own_value_in_the_pages_key_order() -> None:
    """Serial 56: each entry ``{key, value}``, the value as the element held it (a boolean stays a boolean,
    and is not ``1``), a copy the caller can't reach back through; a non-string truth or probe is named."""
    element: dict[str, Any] = {
        "supertype": "Tool",
        "x_spine_retires": 3,
        "x_spine_verified": {"at": "soon"},
        "x_spine_probe": ["npm", "x"],
        "x_spine_status": True,
        "x_spine_truth": 7,
        "x_spine_address": [False],
    }
    dropped = read_spine_element("object", element).as_dict()["dropped"]
    assert as_json(dropped) == as_json(
        [
            {"key": "x_spine_address", "value": False},
            {"key": "x_spine_truth", "value": 7},
            {"key": "x_spine_status", "value": True},
            {"key": "x_spine_probe", "value": ["npm", "x"]},
            {"key": "x_spine_verified", "value": {"at": "soon"}},
            {"key": "x_spine_retires", "value": 3},
        ]
    )
    dropped[3]["value"].append("y")
    assert element["x_spine_probe"] == ["npm", "x"]
    assert read_spine_element("object", {"supertype": "Tool", "x_spine_truth": 7}).truth is None
    assert read_spine_element("object", {"supertype": "Tool", "x_spine_truth": ""}).dropped == ()  # blank: unstated


def test_the_probe_form_is_syntax() -> None:
    def verb(probe: str) -> str | None:
        return read_spine_element("object", {"supertype": "Tool", "x_spine_probe": probe}).probe

    assert verb("npm @onlyworlds/sdk") == "npm"
    assert verb(" npm @onlyworlds/sdk ") == "npm"  # the outer trim
    assert verb("NPM @onlyworlds/sdk") == "unsupported"
    assert verb("npm  @onlyworlds/sdk") == "unsupported"
    assert verb("http get https://x expect 200") == "unsupported"
