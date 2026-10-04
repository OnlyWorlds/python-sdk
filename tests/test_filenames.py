from __future__ import annotations

import itertools

import pytest

from onlyworlds.folder import element_filename, element_filename_full_id, id_tail, resolve_filenames, slugify

UUID = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("The Territory", "the-territory"),
        ("José", "jose"),  # NFKD + combining marks removed before the alnum pass
        ("Ünïcödé Ñame", "unicode-name"),
        ("Συρακοῦσαι", ""),  # no ASCII survives: unsluggable
        ("Dragon 🐉 Lair", "dragon-lair"),
        ("---", ""),
        ("", ""),
        (None, ""),
        ("ﬁre ½", "fire-1-2"),  # NFKD compatibility forms
        ("\uff26\uff35\uff2c\uff2c", "full"),
        ("a" * 39 + " b", "a" * 39),  # cap lands on the separator: trailing '-' re-trimmed
        ("x" * 60, "x" * 40),
    ],
)
def test_slugify(name: str | None, slug: str) -> None:
    assert slugify(name) == slug


def test_filename_forms() -> None:
    assert element_filename(UUID, "The Border") == "the-border--456789abcd.json".replace("456789abcd", UUID[-8:])
    assert UUID[-8:] == "6789abcd"
    assert element_filename(UUID, "") == f"{UUID}.json"  # §3.2: the full id, never a placeholder word
    assert element_filename(UUID, "Συρακοῦσαι") == f"{UUID}.json"
    assert element_filename_full_id(UUID, "The Border") == f"the-border--{UUID}.json"
    assert id_tail("short") == "short"
    assert id_tail("abcdefgh--xyz") == "defghxyz"  # raw tail would carry the separator: compacted
    assert id_tail("abcdefgh-ijklmno") == "hijklmno"  # raw tail "-ijklmno" starts with '-': compacted
    assert id_tail("abcdefgh-ijklmnop") == "ijklmnop"  # raw tail has no '-': kept as is


def test_collision_rule_is_id_ascending_and_order_independent() -> None:
    a = "00000000-0000-7000-8000-00000000aaaa"
    b = "11111111-0000-7000-8000-00000000aaaa"  # same tail as a
    c = "22222222-0000-7000-8000-00000000cccc"
    els = [(b, "Twin"), (a, "Twin"), (c, "Twin")]
    for perm in itertools.permutations(els):
        got = resolve_filenames(perm)
        assert got[a] == "twin--0000aaaa.json"  # lowest id keeps the short form
        assert got[b] == f"twin--{b}.json"
        assert got[c] == "twin--0000cccc.json"  # different tail: no collision


def test_collision_is_case_folded() -> None:
    a = "000000000000000000000000AAAAAAAA"
    b = "111111111111111111111111aaaaaaaa"  # tails differ only in case: one file on NTFS/APFS
    got = resolve_filenames([(b, "X"), (a, "X")])
    assert got[a] == "x--AAAAAAAA.json"
    assert got[b] == f"x--{b}.json"


def test_duplicate_id_is_refused() -> None:
    with pytest.raises(ValueError):
        resolve_filenames([(UUID, "a"), (UUID, "b")])
