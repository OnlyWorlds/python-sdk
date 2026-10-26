"""The message profile (schema-dist ``profiles/message.md``, serial 73): every conformance case in
``codegen/schema-dist/profiles/message.fixture.json``, vendored with the distribution, replayed through the
package's readers, dispatched on the case's kind. The npm SDK's readers run the same cases."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from onlyworlds import (
    MESSAGE_PAIR,
    READ_MARK_PAIR,
    ROOM_PAIRS,
    FolderElement,
    SenderRead,
    is_addressed_to,
    is_message,
    is_sent_by,
    is_to_everyone,
    read_mark_of,
    recipients_of,
    sender_status,
    thread_of,
    unread_for,
)

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "codegen" / "schema-dist" / "profiles" / "message.fixture.json"
KINDS = {"pair": 9, "addressed": 8, "sent_by": 2, "sender": 9, "unread": 8, "mark": 5, "thread": 2}

ADA = "019a3b10-0000-7000-8000-0000000000a1"
MARA = "019a3b10-0000-7000-8000-0000000000a2"
WREN = "019a3b10-0000-7000-8000-0000000000a3"


def load_fixture() -> dict[str, Any]:
    assert FIXTURE.is_file(), f"no message fixture at {FIXTURE}"
    doc: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert doc["profile"] == "message"
    return doc


def ids(elements: list[Any]) -> list[Any]:
    return [e["id"] for e in elements]


def replay(case: dict[str, Any], doc: dict[str, Any]) -> list[str]:
    """What the package answers that the case does not, as one line each (empty: the case passes)."""
    kind, name = case["kind"], case["name"]
    members = case.get("members", doc["members"])
    wrong: list[str] = []

    def expect(what: str, got: Any, want: Any) -> None:
        if got != want:
            wrong.append(f"{name}: {what} gave {got!r}, the fixture says {want!r}")

    if kind == "pair":
        expect("is_message", is_message(case["element"]), case["is_message"])
    elif kind == "addressed":
        expect("is_addressed_to", is_addressed_to(case["message"], case["character"]), case["addressed"])
    elif kind == "sent_by":
        expect("is_sent_by", is_sent_by(case["message"], case["character"]), case["sent_by"])
    elif kind == "sender":
        got = sender_status(case["message"], members)
        expect("status", got.status, case["status"])
        expect("claimed", got.claimed, case["claimed"])
        expect("written_by", got.written_by, case.get("written_by"))
    elif kind == "mark":
        mark = read_mark_of(case["relations"], case["reader"], members)
        expect("read_mark_of", None if mark is None else mark["id"], case["mark"])
    elif kind == "unread":
        expect("unread_for", ids(unread_for(case["messages"], case["reader"], case["read_mark"])), case["unread"])
    elif kind == "thread":
        expect("thread_of", ids(thread_of(case["messages"], case["root"])), case["thread"])
    else:
        wrong.append(f"{name}: a kind this test does not know: {kind!r}")
    return wrong


def test_every_fixture_case_is_answered_as_the_fixture_says() -> None:
    doc = load_fixture()
    cases = doc["cases"]
    wrong = [line for case in cases for line in replay(case, doc)]
    assert wrong == []
    assert len(cases) == 43, f"the fixture holds {len(cases)} cases, serial 73 has 43"
    assert Counter(c["kind"] for c in cases) == KINDS


def test_the_pairs_are_the_fixtures_and_the_message_is_a_room_pair() -> None:
    doc = load_fixture()
    assert {"type": MESSAGE_PAIR[0], "supertype": MESSAGE_PAIR[1]} == doc["pair"]
    assert (READ_MARK_PAIR[0], READ_MARK_PAIR[1]) == (doc["read_mark"]["type"], doc["read_mark"]["supertype"])
    assert MESSAGE_PAIR in ROOM_PAIRS


def test_the_pair_is_trimmed_and_folded_as_the_room_profile() -> None:
    long_s = chr(0x17F)  # simple-folds to "s"
    assert is_message({"type": "NARRATIVE", "supertype": f"{chr(0x3000)}Me{long_s}{long_s}age\t"}) is True
    # U+001C is stripped by str.strip() but is not White_Space; a byte order mark stays.
    assert is_message({"type": "narrative", "supertype": f"{chr(0x1C)}Message"}) is False
    assert is_message({"type": "narrative", "supertype": f"{chr(0xFEFF)}Message"}) is False
    assert is_message({"supertype": "Message"}) is False


def test_a_folder_element_is_a_message_by_its_directory_type() -> None:
    body = {"id": "0192a000-aaaa-7bbb-8ccc-000000000001", "name": "a letter", "supertype": "Message"}
    path = Path("elements/narrative/a-letter.json")
    element = FolderElement(
        id=body["id"], type="narrative", type_inferred=True, body=body, path=path, layout="elements"
    )
    assert is_message(element) is True


def test_recipients_keep_their_order_and_a_malformed_list_is_not_everyone() -> None:
    """The same answers as the npm SDK's test of the same name: a malformed list addresses nobody."""
    assert recipients_of({"characters": [MARA, ADA]}) == [MARA, ADA]
    assert recipients_of({}) == [] and recipients_of({"characters": ADA}) == []
    for characters in (ADA, [""], [5], {"0": ADA}):
        assert is_addressed_to({"characters": characters}, ADA) is False, characters
    no_recipients: tuple[list[str], None] = ([], None)
    for everyone in no_recipients:
        assert is_addressed_to({"characters": everyone}, ADA) is True, everyone
    assert is_addressed_to({}, ADA) is True
    assert is_addressed_to({"characters": []}, "") is False
    for not_everyone in (ADA, [""], [5], [ADA]):
        assert is_to_everyone({"characters": not_everyone}) is False, not_everyone
    everyone_bodies: tuple[dict[str, Any], ...] = ({}, {"characters": None}, {"characters": []})
    for m in everyone_bodies:
        assert is_to_everyone(m) is True, m


def test_the_read_mark_supertype_is_folded_and_a_mark_with_no_members_list_has_no_hand() -> None:
    mark: dict[str, Any] = {
        "id": "m1",
        "type": "Relation",
        "supertype": " read ",
        "actor": ADA,
        "narratives": [],
        "created_by": None,
    }
    assert read_mark_of([mark], ADA, load_fixture()["members"]) is mark
    assert read_mark_of([mark], ADA, None) is None  # created_by exists but cannot be checked
    assert read_mark_of([{**mark, "supertype": "Reads"}], ADA, load_fixture()["members"]) is None


def test_a_thread_whose_parents_loop_ends() -> None:
    loop: list[Mapping[str, Any]] = [
        {"id": "a", "parent_narrative": "b", "created_at": "2026-10-26T09:00:00Z"},
        {"id": "b", "parent_narrative": "a", "created_at": "2026-10-26T09:01:00Z"},
        {"id": "c", "parent_narrative": "a", "created_at": "2026-10-26T09:02:00Z"},
    ]
    assert ids(thread_of(loop, "r")) == []
    assert ids(thread_of(loop, "a")) == ["a", "b", "c"]


def test_sender_read_carries_the_claim() -> None:
    got = sender_status({"narrator": WREN, "created_by": None}, load_fixture()["members"])
    assert got == SenderRead("mismatch", WREN, ADA)


def test_the_newest_read_mark_wins_wherever_it_stands_in_the_list() -> None:
    """The fixture's ``mark-newest-updated-at-wins`` lists the newer mark first, so a reader that kept the
    first mark that counts would pass it. Here the newest stands last; a readable time beats an unreadable
    one, and equal times keep the first in the list. The npm SDK asserts the same."""

    def mark(mid: str, updated_at: str | None) -> dict[str, Any]:
        body: dict[str, Any] = {"id": mid, "type": "relation", "supertype": "Read", "actor": ADA, "narratives": []}
        if updated_at is not None:
            body["updated_at"] = updated_at
        return body

    older, newer = mark("old", "2026-10-26T08:00:00Z"), mark("new", "2026-10-26T11:00:00Z")
    undated, twin = mark("undated", None), mark("twin", "2026-10-26T11:00:00Z")
    assert read_mark_of([older, newer], ADA, None) is newer
    assert read_mark_of([undated, older, newer], ADA, None) is newer
    assert read_mark_of([older, undated], ADA, None) is older
    assert read_mark_of([newer, twin], ADA, None) is newer
    # The fixture's own case, its relations reversed: the owner's hand, checked on the members list.
    doc = load_fixture()
    case = next(c for c in doc["cases"] if c["name"] == "mark-newest-updated-at-wins")
    got = read_mark_of(list(reversed(case["relations"])), case["reader"], doc["members"])
    assert got is not None and got["id"] == case["mark"]


def test_no_character_is_no_sender_and_no_reader_as_in_the_npm_sdk() -> None:
    """An id that is empty or not a string names no Character: no message is sent by it and no read mark
    is its, even a message with no ``narrator`` or a folder's mark with no ``actor``. The npm SDK's
    ``isSentBy`` and ``readMarkOf`` answer the same."""
    nobody: Any = None
    assert is_sent_by({"narrator": ADA}, ADA) is True
    assert is_sent_by({}, nobody) is False
    assert is_sent_by({"narrator": None}, nobody) is False
    assert is_sent_by({"narrator": ""}, "") is False
    assert is_sent_by({}, "") is False
    blank: dict[str, Any] = {"id": "m1", "type": "relation", "supertype": "Read", "actor": "", "narratives": []}
    no_actor: dict[str, Any] = {"id": "m2", "type": "relation", "supertype": "Read", "narratives": []}
    assert read_mark_of([blank], "", None) is None
    assert read_mark_of([no_actor], nobody, None) is None
    assert read_mark_of([{**blank, "actor": ADA}], ADA, None) is not None


def test_a_thread_walks_only_string_ids_as_in_the_npm_sdk() -> None:
    """A message whose id is not a string is in no thread, even when its parent is the root, and a root
    that is empty or not a string has no thread. The npm SDK's ``threadOf`` answers the same."""
    root: dict[str, Any] = {"id": "r", "created_at": "2026-10-26T09:00:00Z"}
    reply: dict[str, Any] = {"id": "s", "parent_narrative": "r", "created_at": "2026-10-26T09:01:00Z"}
    odd: list[dict[str, Any]] = [
        {"id": None, "parent_narrative": "r"},
        {"parent_narrative": "r"},
        {"id": 5, "parent_narrative": "r"},
        {"id": ["x"], "parent_narrative": "r"},
    ]
    assert ids(thread_of([root, *odd, reply], "r")) == ["r", "s"]
    nobody: Any = None
    assert thread_of([{"id": "", "parent_narrative": "x"}], "") == []
    no_ids: list[dict[str, Any]] = [{"parent_narrative": "x"}, {"id": None}]
    assert thread_of(no_ids, nobody) == []
