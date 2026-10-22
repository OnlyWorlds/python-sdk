"""The Markdown pack (onlyworlds.pack): a small world built here, packed in memory and on disk, the
caps driven with tiny numbers. The API door runs against a fake reader. Nothing touches the network."""

from __future__ import annotations

import io
import random
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import ELEMENT_TYPES, pack, write_folder
from onlyworlds.pack import KNOWN_OF_LINE, build_pack, pack_api, pack_folder, pack_world

W = "w0000000-0000-7000-8000-000000000000"
L1 = "l0000000-0000-7000-8000-000000000001"
C1 = "c0000000-0000-7000-8000-000000000001"
C2 = "c0000000-0000-7000-8000-000000000002"
S1 = "s0000000-0000-7000-8000-000000000001"
M1 = "m0000000-0000-7000-8000-000000000001"
P1 = "p0000000-0000-7000-8000-000000000001"
N1 = "n0000000-0000-7000-8000-000000000001"
R1 = "r0000000-0000-7000-8000-000000000001"
GHOST = "g0000000-0000-7000-8000-00000000dead"

WORLD: dict[str, Any] = {
    "id": W,
    "name": "Harbor World",
    "description": "A port town.\n# Not a heading",
    "time_range_current": 120,
    "time_basic_unit": "Year",
    "api": {"api_key": "ow_w_SECRET", "world_id": W},
    "x_theme": "sea",
}

Elements = list[tuple[str, dict[str, Any]]]


def world() -> Elements:
    return [
        ("location", {"id": L1, "name": "Harbor", "description": "A port. Busy all year."}),
        (
            "character",
            {
                "id": C1,
                "name": "Ann",
                "supertype": "Human",
                "subtype": "Sailor",
                "description": "A sailor.",
                "background": "Born at sea.\n# Not a heading\nShe sailed.",
                "height": 170,
                "location": L1,
                "friends": [C2, GHOST],
                "species": [S1],
                "x_mood": "calm",
                "updated_at": "2026-10-22T10:00:00Z",
            },
        ),
        ("character", {"id": C2, "name": "Bo", "description": "Seen once.", "known_of": True}),
        ("species", {"id": S1, "name": "Human", "description": "People."}),
        ("map", {"id": M1, "name": "Harbor map"}),
        ("pin", {"id": P1, "name": "Ann's pin", "map": M1, "element_type": "character", "element_id": C1, "x": 3}),
        ("narrative", {"id": N1, "name": "Hello", "supertype": "Message", "x_room_of": W, "story": "Hi."}),
        (
            "relation",
            {"id": R1, "name": "Ann and Bo", "background": "[the captain](ow://character/" + C1 + ") met Bo."},
        ),
    ]


def built(elements: Elements | None = None, **kw: Any) -> tuple[dict[str, str], pack.PackReport]:
    return build_pack(WORLD, world() if elements is None else elements, **kw)


def section(text: str, name: str) -> str:
    """One element's section: from its ``## <name>`` line to the next ``## `` or the end."""
    start = text.index(f"## {name}\n")
    nxt = text.find("\n## ", start + 1)
    return text[start:nxt] if nxt != -1 else text[start:]


# --- the world file


def test_the_world_file_holds_the_worlds_fields_and_the_index() -> None:
    files, report = built()
    assert next(iter(files)) == "00-world.md"
    text = files["00-world.md"]
    assert text.startswith("# Harbor World\n\n*An OnlyWorlds world in Markdown.")
    assert f"**Id:** {W}\n" in text
    assert "**Description:**\nA port town.\n\\# Not a heading\n" in text
    assert "**Time current:** 120\n" in text  # time_range_current, read as the folder reads it
    assert "**Time basic unit:** Year\n" in text
    assert "SECRET" not in text and "world_id" not in text  # the api block is a credential, never written
    assert "x_theme" not in text and report.extensions_left_out == 2  # the world's and Ann's
    index = text.split("## Index\n", 1)[1]
    assert index.index("### Characters") < index.index("### Locations") < index.index("### Relations")
    assert "- **Ann** (Human / Sailor): A sailor.\n" in index
    assert "- **Bo**: Seen once.\n" in index
    assert "- **Harbor**: A port.\n" in index  # the first sentence only
    assert "- **Harbor map**\n" in index  # no description, no colon
    assert "Hello" not in index  # a room element is not indexed


def test_an_index_line_reads_prose_references_as_words_and_is_cut_long() -> None:
    long = " ".join(["word"] * 200) + "."
    elements = [
        ("character", {"id": C1, "name": "Ann", "description": "Ann."}),
        ("character", {"id": C2, "name": "Bo", "description": "Friend of [her](ow://character/" + C1 + "). More."}),
        ("location", {"id": L1, "name": "Harbor", "description": long}),
    ]
    files, report = built(elements)
    assert "- **Bo**: Friend of her (Ann).\n" in files["00-world.md"]
    (line,) = [x for x in files["00-world.md"].splitlines() if x.startswith("- **Harbor**")]
    assert line.endswith(" …") and len(line) < 270
    assert report.unresolved == []


# --- one element


def test_an_element_shows_each_kind_of_field_in_schema_order() -> None:
    files, report = built()
    ann = section(files["01-character.md"], "Ann")
    assert ann == (
        "## Ann\n"
        f"*Character · id {C1} · Human / Sailor*\n"
        "\n**Description:**\nA sailor.\n"
        "\n**Height:** 170\n"
        "\n**Species:** Human (species)\n"
        "\n**Background:**\nBorn at sea.\n\\# Not a heading\nShe sailed.\n"
        "\n**Location:** Harbor (location)\n"
        f"\n**Friends:** Bo (character), {GHOST} (unresolved)\n"
    )
    assert report.unresolved == [f"character Ann ({C1}): `friends` -> {GHOST}"]
    pin = section(files["04-pin.md"], "Ann's pin")
    assert "\n**Map:** Harbor map (map)\n" in pin
    assert "\n**Element:** Ann (character)\n" in pin  # the generic link, with its target's type
    assert "\n**X:** 3\n" in pin
    assert "updated_at" not in files["01-character.md"]


def test_a_hash_line_in_prose_cannot_become_a_heading() -> None:
    elements = [("character", {"id": C1, "name": "Ann", "background": "# Act one\n  ## Scene\n===\nText"})]
    files, _ = built(elements)
    text = files["01-character.md"]
    assert "**Background:**\n\\# Act one\n  \\## Scene\n\\===\nText\n" in text
    assert [line for line in text.splitlines() if line.startswith("#")] == ["# Characters of Harbor World", "## Ann"]


def test_an_unresolved_link_of_each_shape() -> None:
    elements = [
        ("character", {"id": C1, "name": "Ann", "location": GHOST, "background": f"[Lost](ow://character/{GHOST})"}),
        ("pin", {"id": P1, "name": "P", "element_type": "object", "element_id": GHOST}),
    ]
    files, report = built(elements)
    assert f"**Location:** {GHOST} (unresolved)\n" in files["01-character.md"]
    assert f"[Lost](ow://character/{GHOST})" in files["01-character.md"]  # prose stays as written
    assert f"**Element:** {GHOST} (unresolved)\n" in files["02-pin.md"]
    assert report.unresolved == [  # schema order: Origins (background) before World (location)
        f"character Ann ({C1}): `background` (prose) -> {GHOST}",
        f"character Ann ({C1}): `location` -> {GHOST}",
        f"pin P ({P1}): `element` -> {GHOST}",
    ]


def test_a_prose_reference_becomes_its_label_and_names_the_target_when_they_differ() -> None:
    files, _report = built()
    assert "**Background:**\nthe captain (Ann) met Bo.\n" in files["05-relation.md"]
    elements = [
        ("character", {"id": C1, "name": "Ann"}),
        ("character", {"id": C2, "name": "Bo", "background": f"Met [ann](ow://character/{C1})."}),
    ]
    assert "Met ann.\n" in built(elements)[0]["01-character.md"]


def test_a_known_of_stub_says_its_missing_fields_are_unknown() -> None:
    files, report = built()
    bo = section(files["01-character.md"], "Bo")
    assert bo.splitlines()[:3] == ["## Bo", f"*Character · id {C2}*", KNOWN_OF_LINE]
    assert "known_of" not in bo
    assert report.known_of == 1
    assert KNOWN_OF_LINE not in section(files["01-character.md"], "Ann")


def test_a_key_that_is_no_field_is_a_note() -> None:
    elements: Elements = [
        ("character", {"id": C1, "name": "Ann", "colour": "red"}),
        ("character", {"id": C2, "colour": 1}),
    ]
    seen: list[str] = []
    files, report = built(elements, note=seen.append)
    assert seen == report.notes == ["character: `colour` is not a field of character; left out (2 elements)"]
    assert "colour" not in files["01-character.md"]
    assert "## (unnamed)\n" in files["01-character.md"]


# --- what is left out unless asked


def test_room_elements_are_left_out_unless_asked() -> None:
    files, report = built()
    assert report.rooms_left_out == 1 and report.elements == 7
    assert not any("narrative" in name for name in files)
    files, report = built(rooms=True)
    assert report.rooms_left_out == 0 and report.elements == 8
    (name,) = [n for n in files if "narrative" in n]
    assert "## Hello\n*Narrative · id " + N1 + " · Message*\n" in files[name]
    assert "x_room_of" not in files[name]  # the mark is an extension: left out without --extensions


def test_extensions_are_left_out_unless_asked() -> None:
    files, report = built()
    assert report.extensions_left_out == 2
    assert "x_mood" not in files["01-character.md"] and "x_theme" not in files["00-world.md"]
    files, report = built(extensions=True)
    assert report.extensions_left_out == 0
    assert "\n**x_mood:** calm\n" in section(files["01-character.md"], "Ann")
    assert "\n**x_theme:** sea\n" in files["00-world.md"]


# --- sizing


def characters(n: int, words: int = 20) -> Elements:
    return [
        ("character", {"id": f"c-{i:03d}", "name": f"Person {i:03d}", "background": " ".join(["word"] * words)})
        for i in range(n)
    ]


def test_the_word_cap_splits_a_type_at_element_boundaries() -> None:
    elements = [*characters(10), ("location", {"id": L1, "name": "Harbor"})]
    files, report = built(elements, words=100)
    parts = [n for n in files if "character" in n]
    assert len(parts) > 1
    assert parts == [f"01-character-{k}.md" for k in range(1, len(parts) + 1)]
    for k, name in enumerate(parts, 1):
        assert files[name].startswith(f"# Characters of Harbor World (part {k} of {len(parts)})\n\n## ")
        assert len(files[name].split()) <= 100
    joined = "".join(files[n] for n in parts)
    assert [joined.count(f"## Person {i:03d}\n") for i in range(10)] == [1] * 10
    assert "02-location.md" in files and report.oversize == [] and not report.files_over


def test_the_world_file_splits_its_index_past_a_cap() -> None:
    elements = [*characters(30, words=1), ("location", {"id": L1, "name": "Harbor", "description": "A port."})]
    files, report = built(elements, words=120)
    heads = [n for n in files if n.startswith("00-world")]
    assert len(heads) > 1 and heads == [f"00-world-{k}.md" for k in range(1, len(heads) + 1)]
    assert list(files)[: len(heads)] == heads
    for k, name in enumerate(heads, 1):
        assert files[name].startswith(f"# Harbor World (part {k} of {len(heads)})\n\n")
        assert len(files[name].split()) <= 120
    assert "**Time current:** 120" in files[heads[0]] and "**Time current:**" not in files[heads[1]]
    assert files[heads[1]].startswith(f"# Harbor World (part 2 of {len(heads)})\n\n## Index (continued)\n\n### ")
    assert "### Characters (continued)\n" in "".join(files[n] for n in heads[1:])
    index = "".join(files[n] for n in heads)
    assert [index.count(f"- **Person {i:03d}**\n") for i in range(30)] == [1] * 30
    assert index.count("- **Harbor**: A port.\n") == 1
    assert report.oversize == []


def test_the_byte_cap_splits_too() -> None:
    files, _report = built(characters(6), bytes_=400)
    parts = [n for n in files if "character" in n]
    assert len(parts) > 1 and all(len(files[n].encode("utf-8")) <= 400 for n in parts)


def test_the_file_cap_merges_small_adjacent_types() -> None:
    elements = [(t, {"id": f"{t}-1", "name": t.title()}) for t in ("character", "location", "object", "ability")]
    files, report = built(elements, files=3)
    assert len(files) == 3 and not report.files_over
    assert all(n.split("-", 1)[0].isdigit() for n in files)
    merged = [n for n in files if n.count("-") > 1]
    assert merged, files.keys()
    for name in files:
        if name != "00-world.md":
            for slug in name[3:-3].split("-"):
                assert f"# {pack.PLURALS[slug]} of Harbor World\n" in files[name]
    assert sorted(files) == list(files)


def test_a_merged_name_past_four_types_names_the_first_and_last() -> None:
    types = ("character", "species", "location", "object", "ability", "event")
    elements = [(t, {"id": f"{t}-1", "name": t.title()}) for t in types]
    files, report = built(elements, files=2)
    present = [t for t in ELEMENT_TYPES if t in types]
    assert list(files) == ["00-world.md", f"01-{present[0]}-to-{present[-1]}.md"]
    assert not report.files_over


def test_a_split_type_is_never_merged_and_files_over_is_reported() -> None:
    elements = [*characters(10), ("location", {"id": L1, "name": "Harbor"}), ("object", {"id": "o1", "name": "Oar"})]
    files, report = built(elements, words=150, files=2)
    assert report.files_over
    assert [n for n in files if "character" not in n] == ["00-world.md", "02-location-object.md"]
    joined = "".join(files.values())
    assert all(f"## Person {i:03d}\n" in joined for i in range(10))  # nothing dropped to meet the cap


def test_one_element_past_a_cap_is_written_alone_and_whole() -> None:
    elements = [*characters(2), ("character", {"id": "c-big", "name": "Big", "background": " ".join(["w"] * 500)})]
    files, report = built(elements, words=100)
    alone = [n for n in files if "## Big\n" in files[n]]
    assert len(alone) == 1 and report.oversize == alone
    assert files[alone[0]].count("\n## ") == 1  # alone
    assert files[alone[0]].split("**Background:**\n", 1)[1].split() == ["w"] * 500  # whole
    assert any(alone[0] in note and "Big" in note for note in report.notes)


# --- determinism and the files


def test_the_same_world_gives_the_same_bytes(tmp_path: Path) -> None:
    a = pack_world(WORLD, world(), tmp_path / "a")
    shuffled = world()
    random.Random(7).shuffle(shuffled)
    b = pack_world(dict(reversed(list(WORLD.items()))), shuffled, tmp_path / "b")
    assert a.files == b.files
    for name in a.files:
        data = (tmp_path / "a" / name).read_bytes()
        assert data == (tmp_path / "b" / name).read_bytes()
        assert b"\r" not in data
    assert sorted(p.name for p in (tmp_path / "a").iterdir()) == a.files
    assert a.words == sum(len((tmp_path / "a" / n).read_text(encoding="utf-8").split()) for n in a.files)
    assert a.bytes == sum((tmp_path / "a" / n).stat().st_size for n in a.files)


def test_elements_sharing_a_name_go_by_id() -> None:
    elements = [("character", {"id": "c-2", "name": "Ann"}), ("character", {"id": "c-1", "name": "Ann"})]
    text = built(elements)[0]["01-character.md"]
    assert text.index("id c-1") < text.index("id c-2")


def test_pack_world_never_writes_over_a_directory(tmp_path: Path) -> None:
    (tmp_path / "out").mkdir()
    with pytest.raises(FileExistsError):
        pack_world(WORLD, world(), tmp_path / "out")
    with pytest.raises(ValueError, match="words"):
        build_pack(WORLD, world(), words=0)


# --- the folder door and the command line


def folder(tmp_path: Path) -> Path:
    by_type: dict[str, list[dict[str, Any]]] = {}
    for slug, body in world():
        by_type.setdefault(slug, []).append(body)
    root = tmp_path / "world"
    write_folder(root, {k: v for k, v in WORLD.items() if k != "api"}, by_type)
    return root


def run_main(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = pack.main(argv)
    return code, out.getvalue(), err.getvalue()


def test_pack_folder_reads_a_world_folder(tmp_path: Path) -> None:
    report = pack_folder(folder(tmp_path), tmp_path / "out")
    same = build_pack(WORLD, world())[1]
    assert report.files == same.files and report.words == same.words and report.bytes == same.bytes
    assert (tmp_path / "out" / "00-world.md").read_text(encoding="utf-8").count("**Time current:** 120") == 1


def test_the_command_line(tmp_path: Path) -> None:
    root = folder(tmp_path)
    code, out, err = run_main([str(root), str(tmp_path / "out")])
    assert code == 0
    written = sorted((tmp_path / "out").iterdir())
    n_words = sum(len(p.read_text(encoding="utf-8").split()) for p in written)
    n_kb = round(sum(p.stat().st_size for p in written) / 1000)
    assert len(written) == 7 and n_kb == 2
    assert out == (
        f"packed 7 elements in 6 types to {tmp_path / 'out'}: 7 files, {n_words} words, 2 KB; "
        "1 room element left out; 2 extension fields left out; 1 known of; 1 unresolved link\n"
    )
    assert f"note: unresolved link: character Ann ({C1}): `friends` -> {GHOST}\n" in err
    assert run_main([str(root), str(tmp_path / "out")])[0] == 2  # OUT exists
    assert run_main([str(root)])[0] == 2  # no OUT
    assert run_main([str(root), str(tmp_path / "o2"), "--api"])[0] == 2  # two sources
    assert run_main([])[0] == 2
    assert run_main([str(tmp_path / "nowhere"), str(tmp_path / "o3")])[0] == 2
    assert run_main([str(root), str(tmp_path / "o4"), "--words", "0"])[0] == 2
    assert run_main([str(root), str(tmp_path / "o5"), "--nonsense"])[0] == 2
    assert not (tmp_path / "o2").exists() and not (tmp_path / "o4").exists()


def test_the_command_line_exits_1_when_the_files_are_over_the_cap(tmp_path: Path) -> None:
    code, out, err = run_main([str(folder(tmp_path)), str(tmp_path / "out"), "--files", "1", "--rooms"])
    assert code == 1
    assert "more than --files 1: every element was written" in err
    assert len(list((tmp_path / "out").iterdir())) == 2
    assert out.startswith("packed 8 elements in 7 types")


# --- the API door


class FakeReader:
    """Client's read methods over fixed data, in pages of two; every write method raises."""

    def __init__(self, elements: Elements):
        self.elements = elements
        self.calls: list[str] = []

    def me(self) -> dict[str, Any]:
        return {"world": W, "role": "owner", "kind": "owner"}

    def get_world(self) -> dict[str, Any]:
        self.calls.append("get_world")
        return {k: v for k, v in WORLD.items() if k != "api"}

    def list_page(self, element_type: str, *, limit: int | None = None, cursor: str | None = None) -> dict[str, Any]:
        self.calls.append(f"list_page {element_type}")
        data = [{**b, "type": t} for t, b in self.elements if t == element_type]
        at = int(cursor or 0)
        nxt = at + 2
        return {"data": data[at:nxt], "has_more": nxt < len(data), "next_cursor": str(nxt)}

    def changes(self, *, since: str | None = None, limit: int | None = None) -> dict[str, Any]:
        raise AssertionError("the pack reads no feed")

    def _write(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the pack wrote")

    create = upsert = patch = delete = edit_links = bulk = patch_world = _write


def test_pack_api_reads_the_world_through_a_reader(tmp_path: Path) -> None:
    reader = FakeReader(world() + characters(3))
    report = pack_api(reader, tmp_path / "out")
    assert reader.calls.count("list_page character") == 3  # five characters, pages of two
    text = (tmp_path / "out" / "01-character.md").read_text(encoding="utf-8")
    assert "## Ann\n" in text and "## Person 002\n" in text
    assert report.elements == 10 and report.rooms_left_out == 1


def test_the_api_command_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, str | None, str]] = []

    def make(key: str, pin: str | None = None, *, base_url: str = "") -> FakeReader:
        seen.append((key, pin, base_url))
        return FakeReader(world())

    monkeypatch.setattr(pack, "Client", make)
    for name in ("OW_API_KEY", "OW_API_PIN", "ONLYWORLDS_API_KEY", "ONLYWORLDS_API_PIN"):
        monkeypatch.delenv(name, raising=False)
    assert run_main(["--api", str(tmp_path / "out")])[0] == 2  # no key
    monkeypatch.setenv("ONLYWORLDS_API_KEY", "ow_r_toolkit")
    code, out, _ = run_main(["--api", str(tmp_path / "out"), "--base-url", "https://example.test/api/v2/"])
    assert code == 0 and out.startswith("packed 7 elements in 6 types")
    assert seen == [("ow_r_toolkit", None, "https://example.test/api/v2/")]
    assert run_main(["--api"])[0] == 2  # no OUT


def test_the_api_command_line_when_nothing_can_be_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Refused(FakeReader):
        def get_world(self) -> dict[str, Any]:
            raise ConnectionError("no answer")

    monkeypatch.setattr(pack, "Client", lambda key, pin=None, **kw: Refused([]))
    monkeypatch.setenv("OW_API_KEY", "ow_r_bad")
    code, _, err = run_main(["--api", str(tmp_path / "out")])
    assert code == 2 and "nothing could be read: no answer" in err
    assert not (tmp_path / "out").exists()


# --- the label line: which kind of key made the pack (h58 #10628, #10631)


def test_the_world_file_says_which_kind_of_key_made_the_pack() -> None:
    owner = {"kind": "owner", "role": "owner", "character": None}
    member = {"kind": "member", "role": "co_builder", "character": None}
    named = {"kind": "character", "role": "guest", "character": {"id": C1, "name": "Ann"}}
    unnamed = {"kind": "character", "role": "guest", "character": None}
    assert pack.made_by_line(owner) == "*Made with the owner's key: the whole world.*"
    assert pack.made_by_line(member) == "*Made with a member's key (co-builder): that member's view of the world.*"
    assert pack.made_by_line(named) == "*Made as the Character Ann: that Character's view, not the whole world.*"
    assert pack.made_by_line(unnamed) == "*Made as a Character: that Character's view, not the whole world.*"
    assert pack.made_by_line(None) is None and pack.made_by_line({"kind": "elsewhere"}) is None
    files, _ = built(exported_as=owner)
    text = files["00-world.md"]
    assert "*Made with the owner's key: the whole world.*\n\n**Id:**" in text
    assert "**Description:**" in text  # the fields follow it
    plain, _ = built()
    assert "Made with" not in plain["00-world.md"]  # no slice known: no line, never a guess
    assert "ow_" not in text  # a kind, never a key


def test_a_folder_with_an_exported_as_line_packs_it_and_the_api_asks_me(tmp_path: Path) -> None:
    meta = {k: v for k, v in WORLD.items() if k != "api"} | {
        "exported_as": {"kind": "member", "role": "contributor", "character": None}
    }
    root = tmp_path / "w"
    by_type: dict[str, list[dict[str, Any]]] = {}
    for t, b in world():
        by_type.setdefault(t, []).append(dict(b))
    write_folder(root, meta, by_type)
    out = tmp_path / "pack"
    pack_folder(root, out)
    assert "*Made with a member's key (contributor): that member's view of the world.*" in (
        out / "00-world.md"
    ).read_text(encoding="utf-8")

    class Reader:
        def me(self) -> dict[str, Any]:
            return {"kind": "person", "role": "guest", "membership": "m1", "character": C1}

        def get_world(self) -> dict[str, Any]:
            return dict(WORLD)

        def list_page(self, element_type: str, **kw: Any) -> dict[str, Any]:
            data = [dict(b) for t, b in world() if t == element_type]
            return {"data": data, "has_more": False, "next_cursor": None}

    out2 = tmp_path / "pack-api"
    pack_api(Reader(), out2)
    assert "*Made as the Character Ann: that Character's view, not the whole world.*" in (
        out2 / "00-world.md"
    ).read_text(encoding="utf-8")


# --- a world's own words for the types (the names profile, schema-dist profiles/names.md, dist.48)

NAMES: dict[str, Any] = {
    "version": 1,
    "types": {
        "character": {"one": "Employee", "many": "Employees"},
        "location": {"one": "Office", "many": "Offices"},
    },
    "supertypes": {"character": {"human": {"one": "Crew member", "many": "Crew"}}},
}


def digest(files: dict[str, str]) -> str:
    import hashlib

    h = hashlib.sha256()
    for name, text in files.items():
        h.update(name.encode() + b"\0" + text.encode("utf-8") + b"\0")
    return h.hexdigest()


def test_without_a_names_map_the_pack_is_byte_for_byte_as_before() -> None:
    # Digests of this test world's pack as 0.30.0 wrote it, before the pack read names maps.
    named = {"kind": "character", "role": "guest", "character": {"id": C1, "name": "Ann"}}
    assert digest(built()[0]) == "294c32a58994d3784071b07ca317fcda1bf9bec9c2f92aa7390f393c93754256"
    everything = built(rooms=True, extensions=True, exported_as=named)[0]
    assert digest(everything) == "d1bd968860a0249d2fed4342abcb884b3a7dccb5ee0e539258e626c8de8d8c41"
    refused = {**WORLD, "x_names": {**NAMES, "version": 2}}  # not a names map: the standard's names
    assert build_pack(refused, world())[0] == built()[0]


def test_a_names_map_prints_the_worlds_word_first_and_the_standards_in_brackets(tmp_path: Path) -> None:
    by_type: dict[str, list[dict[str, Any]]] = {}
    for slug, body in world():
        by_type.setdefault(slug, []).append(body)
    root = tmp_path / "world"
    write_folder(root, {k: v for k, v in WORLD.items() if k != "api"} | {"x_names": NAMES}, by_type)
    report = pack_folder(root, tmp_path / "out")
    assert report.files == built()[1].files  # file names keep the standard's slugs
    read = {n: (tmp_path / "out" / n).read_text(encoding="utf-8") for n in report.files}

    index = read["00-world.md"].split("## Index\n", 1)[1]
    assert "\n### Employees (Character)\n" in index and "\n### Offices (Location)\n" in index
    assert "\n### Species\n" in index  # no entry: the standard's name, as ever
    assert read["01-character.md"].startswith("# Employees (Character) of Harbor World\n")
    assert read["02-location.md"].startswith("# Offices (Location) of Harbor World\n")
    # an element's own line knows its supertype: Ann's (Human, matched without regard to case) has a word
    assert section(read["01-character.md"], "Ann").splitlines()[1] == (
        f"*Crew member (Character, Human) · id {C1} · Human / Sailor*"
    )
    assert section(read["01-character.md"], "Bo").splitlines()[1] == f"*Employee (Character) · id {C2}*"
    assert section(read["02-location.md"], "Harbor").splitlines()[1] == f"*Office (Location) · id {L1}*"
    assert "*Species · id " in read["06-species.md"]

    assert "x_names" not in read["00-world.md"] and report.extensions_left_out == 2  # the map is no field
    pack_folder(root, tmp_path / "out-x", extensions=True)
    with_x = (tmp_path / "out-x" / "00-world.md").read_text(encoding="utf-8")
    assert "\n**x_theme:** sea\n" in with_x  # other extension keys still print when asked
    assert "x_names" not in with_x and "Crew member" not in with_x


def test_the_label_line_says_a_characters_view_in_the_worlds_word() -> None:
    mapped = {**WORLD, "x_names": NAMES}
    named = {"kind": "character", "role": "guest", "character": {"id": C1, "name": "Ann"}}
    unnamed = {"kind": "character", "role": "guest", "character": None}
    assert pack.made_by_line(named, mapped) == (
        "*Made as the Employee (Character) Ann: that Employee's view, not the whole world.*"
    )
    assert pack.made_by_line(unnamed, mapped) == (
        "*Made as one Employee (Character): that Employee's view, not the whole world.*"
    )
    assert "*Made as the Employee (Character) Ann:" in build_pack(mapped, world(), exported_as=named)[0]["00-world.md"]
