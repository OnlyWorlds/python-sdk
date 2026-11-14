"""find_ow_links: every address in a text, in order, each an AddressFound, read by read_ow_link_at at each place a
prefix starts. The start rule's cases as units (STAGED: ruled 2026-11-14, publishes with a later serial), order and
no overlap, agreement with read_ow_link_at, and six hostile 1 MB texts timed."""

import time
from itertools import pairwise

import pytest

from onlyworlds import AddressFound, find_ow_links, read_ow_link_at

E = "01a1d4ef-0000-7000-8000-000000000084"
F = "01a1d4ef-0000-7000-8000-000000000085"
W = "0193a1c2-7d3e-7f00-8a11-3c5e7b9d2f40"
H = "https://www.onlyworlds.com/w/"


@pytest.mark.parametrize(
    ("name", "before", "n"),
    [
        ("hyphen", "x-", 1),
        ("digit", "3", 1),
        ("letter", "elb", 0),
        ("non-ascii-letter", "café", 0),
        ("combining-mark", "café", 0),
        ("underscore", "_", 0),
        ("astral-letter", "\U0001d49c", 0),
        ("space", "a ", 1),
        ("opening-bracket", "(", 1),
        ("full-stop", "end.", 1),
        ("quote", '"', 1),
        ("start-of-text", "", 1),
    ],
)
def test_the_start_rule_one_unit_each(name: str, before: str, n: int) -> None:
    text = f"{before}ow://object/{E} then"
    got = find_ow_links(text)
    assert len(got) == n, name
    if n:
        at = read_ow_link_at(text, len(before))
        assert at is not None
        assert got[0] == AddressFound(len(before), len(before) + 48, at.reading), name


def test_every_address_in_order_none_overlapping() -> None:
    text = (
        f'Built the gate: elbow://object/{E}. See (ow://object/{E}) and "{H}{W}/event/{F}" '
        f"then ow://{W}/object/{E}@12?lens={F}, ow://ow://object/{F}."
    )
    got = find_ow_links(text)
    assert [text[f.start : f.end] for f in got] == [
        f"ow://object/{E}",
        f"{H}{W}/event/{F}",
        f"ow://{W}/object/{E}@12?lens={F}",
        f"ow://object/{F}",
    ]
    for f in got:
        at = read_ow_link_at(text, f.start)
        assert at is not None and (at.reading, at.end) == (f.reading, f.end)
    assert all(b.start >= a.end for a, b in pairwise(got))


def test_nothing_to_find_and_a_text_that_is_not_a_string() -> None:
    assert find_ow_links("") == []
    assert find_ow_links("no address here") == []
    assert find_ow_links("ow://") == []
    assert find_ow_links(H) == []
    for v in (None, 42, ["ow://x"], b"ow://x"):
        with pytest.raises(TypeError):
            find_ow_links(v)  # type: ignore[arg-type]


def test_linear_on_hostile_texts() -> None:
    mb = 1 << 20

    def fill(unit: str) -> str:
        return unit * (mb // len(unit) + 1)

    shapes = {
        "prefixes alone": fill("ow://"),
        "glued starts": fill(f"elbow://object/{E} "),
        "addresses with a moment": fill(f"ow://object/{E}@123 "),
        "a long run after /w/": H + "a" * mb,
        "many ow:// then one site prefix at the end": fill("ow://x ") + H + W,
        "long paths that never read": fill("ow://" + "object/" * 14 + "x "),
    }
    for name, text in shapes.items():
        t0 = time.perf_counter()
        find_ow_links(text)
        seconds = time.perf_counter() - t0
        assert seconds < 10, f"{name}: {seconds:.1f} s"
