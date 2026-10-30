"""The message profile (schema-dist ``profiles/message.md``, serial 76): every conformance case in
``codegen/schema-dist/profiles/message.fixture.json``, vendored with the distribution, replayed through the
package's readers, dispatched on the case's kind. The npm SDK's readers run the same cases."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import (
    MESSAGE_PAIR,
    NOTE_PAIR,
    READ_MARK_PAIR,
    ROOM_PAIRS,
    EditRead,
    FolderElement,
    SenderRead,
    edited_by,
    has_unseen_recipients,
    is_addressed_to,
    is_message,
    is_note,
    is_sent_by,
    is_to_everyone,
    note_of,
    read_mark_of,
    recipients_of,
    sender_status,
    thread_of,
    unread_for,
)

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "codegen" / "schema-dist" / "profiles" / "message.fixture.json"
KINDS = {
    "pair": 10,
    "addressed": 11,
    "sent_by": 3,
    "sender": 14,
    "unread": 17,
    "mark": 11,
    "thread": 4,
    "unseen": 3,
    "everyone": 3,
    "edited": 4,
    "note": 8,
}

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
    elif kind == "unseen":
        # A case without keyless has a credential.
        expect("is_addressed_to", is_addressed_to(case["message"], case["character"]), case["addressed"])
        expect("has_unseen_recipients", has_unseen_recipients(case["message"]), case["unseen_recipients"])
    elif kind == "everyone":
        keyless = case["keyless"]
        expect("is_to_everyone", is_to_everyone(case["message"], keyless=keyless), case["to_everyone"])
        expect(
            "has_unseen_recipients", has_unseen_recipients(case["message"], keyless=keyless), case["unseen_recipients"]
        )
    elif kind == "edited":
        edit = edited_by(case["message"], members)
        expect("edited_by", (edit.edited, edit.by), (case["edited"], case["edited_by"]))
    elif kind == "note":
        expect("note_of", note_of(case["notes"], case["character"], members), case["line"])
    elif kind == "sent_by":
        expect("is_sent_by", is_sent_by(case["message"], case["character"]), case["sent_by"])
    elif kind == "sender":
        got = sender_status(case["message"], members)
        expect("status", got.status, case["status"])
        expect("claimed", got.claimed, case["claimed"])
        expect("written_by", got.written_by, case.get("written_by"))
    elif kind == "mark":
        # A case without keyless has a credential, or is a folder.
        mark = read_mark_of(case["relations"], case["reader"], members, keyless=case.get("keyless", False))
        expect("read_mark_of", None if mark is None else mark["id"], case["mark"])
    elif kind == "unread":
        got_unread = unread_for(case["messages"], case["reader"], case["read_mark"], members)
        expect("unread_for", ids(got_unread), case["unread"])
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
    assert len(cases) == 88, f"the fixture holds {len(cases)} cases, serial 95 has 88"
    assert Counter(c["kind"] for c in cases) == KINDS


def test_the_pairs_are_the_fixtures_and_the_message_is_a_room_pair() -> None:
    doc = load_fixture()
    assert {"type": MESSAGE_PAIR[0], "supertype": MESSAGE_PAIR[1]} == doc["pair"]
    assert (READ_MARK_PAIR[0], READ_MARK_PAIR[1]) == (doc["read_mark"]["type"], doc["read_mark"]["supertype"])
    assert MESSAGE_PAIR in ROOM_PAIRS
    assert {"type": NOTE_PAIR[0], "supertype": NOTE_PAIR[1]} == doc["note_pair"]
    assert is_note({"type": " Narrative ", "supertype": "NOTE"}) is True
    assert is_note({"type": "narrative", "supertype": "Notes"}) is False
    assert is_note({"type": "narrative", "supertype": "Message"}) is False


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


def test_a_list_the_server_trimmed_is_never_everyone_and_says_someone_unseen_is_addressed() -> None:
    """Every recipient hidden arrives as an empty list with the mark, never everyone."""

    def trimmed(characters: list[str], mark: list[str] | None = None) -> dict[str, Any]:
        return {"characters": characters, "x_served_trimmed": ["characters"] if mark is None else mark}

    assert is_to_everyone(trimmed([])) is False
    assert has_unseen_recipients(trimmed([])) is True
    assert is_addressed_to(trimmed([]), ADA) is False
    assert has_unseen_recipients(trimmed([ADA])) is True
    assert is_addressed_to(trimmed([ADA]), ADA) is True
    assert has_unseen_recipients(trimmed([], ["narrator"])) is False
    assert is_to_everyone(trimmed([], ["narrator"])) is True
    no_mark: tuple[dict[str, Any], ...] = (
        {},
        {"characters": []},
        {"x_served_trimmed": "characters"},
        {"x_served_trimmed": None},
    )
    for m in no_mark:
        assert has_unseen_recipients(m) is False, m
    keyless_bodies: tuple[dict[str, Any], ...] = ({}, {"characters": []}, {"characters": None})
    for m in keyless_bodies:
        assert is_to_everyone(m, keyless=True) is False, m
        assert has_unseen_recipients(m, keyless=True) is None, m
        assert is_to_everyone(m, keyless=False) is True, m
    assert sender_status({"narrator": None, "x_served_trimmed": ["narrator"]}, []) == SenderRead("unseen", None)
    assert sender_status({"narrator": None, "x_served_trimmed": ["characters"]}, []).status == "unverifiable"
    assert sender_status({"narrator": None}, []).status == "unverifiable"


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


def test_no_mark_counts_on_a_keyless_body() -> None:
    """message.md (serial 95): the keyless public reader is served no hands, so a mark there carries neither
    ``created_by`` nor ``changed_by`` because they were taken off, and ``read_mark_of`` with ``keyless=True``
    answers none, whatever the mark carries. ``keyless`` is a keyword, True or False, as ``is_to_everyone``
    takes it."""
    bare: dict[str, Any] = {"id": "m1", "type": "relation", "supertype": "Read", "actor": ADA, "narratives": []}
    members = load_fixture()["members"]
    assert read_mark_of([bare], ADA, None) is bare  # a folder's: no hand to check
    assert read_mark_of([bare], ADA, None, keyless=True) is None
    own = {**bare, "created_by": None, "changed_by": None}
    assert read_mark_of([own], ADA, members) is own
    assert read_mark_of([own], ADA, members, keyless=True) is None
    with pytest.raises(TypeError, match="keyless"):
        read_mark_of([bare], ADA, None, keyless=1)  # type: ignore[arg-type]


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


MEMBERS: list[dict[str, Any]] = [
    {"id": None, "character": ADA},
    {"id": "b2", "character": MARA},
    {"id": "b3", "character": WREN},
    {"id": "b5", "character": None},
]


def read_mark(mid: str, **hands: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"id": mid, "type": "relation", "supertype": "Read", "actor": MARA, "narratives": []}
    return {**body, "updated_at": "2026-10-26T10:00:00Z", **hands}


def test_a_mark_counts_only_when_every_write_on_it_was_its_readers_hand() -> None:
    """What the fixture does not settle about ``changed_by``. The npm SDK's ``readMarkOf`` answers alike."""
    # No changed_by key: the reader cannot see the last writer, so the author check alone decides.
    assert read_mark_of([read_mark("m", created_by="b2")], MARA, MEMBERS) is not None
    # changed_by None is the owner's hand: on a member's mark it is another hand, ignored.
    assert read_mark_of([read_mark("m", created_by="b2", changed_by=None)], MARA, MEMBERS) is None
    # The owner's own mark, made and changed by the owner: None on both, equal.
    owners = {**read_mark("o", created_by=None, changed_by=None), "actor": ADA}
    assert read_mark_of([owners], ADA, MEMBERS) is owners
    assert read_mark_of([{**owners, "changed_by": "b2"}], ADA, MEMBERS) is None
    # changed_by with no created_by beside it does not count, even equal to nothing.
    assert read_mark_of([read_mark("m", changed_by="b2")], MARA, MEMBERS) is None
    assert read_mark_of([read_mark("m", changed_by=None)], MARA, None) is None
    # Equal hands are not enough: the author must still play the reader's Character.
    assert read_mark_of([read_mark("m", created_by="b3", changed_by="b3")], MARA, MEMBERS) is None
    # A folder's mark, with neither key, has no hand to check and counts.
    assert read_mark_of([read_mark("m")], MARA, None) is not None
    # A newer mark another hand changed is ignored, and the reader's own older mark stands.
    own = read_mark("own", created_by="b2", changed_by="b2", updated_at="2026-10-26T08:00:00Z")
    touched = read_mark("touched", created_by="b2", changed_by=None, updated_at="2026-10-26T12:00:00Z")
    assert read_mark_of([touched, own], MARA, MEMBERS) is own
    assert read_mark_of([own, touched], MARA, MEMBERS) is own


def message(mid: str, narrator: str | None, minute: int, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"id": mid, "type": "narrative", "supertype": "Message", "characters": []}
    if narrator is not None:
        body["narrator"] = narrator
    return {**body, "created_at": f"2026-10-26T09:{minute:02d}:00Z", **extra}


def test_unread_proves_the_readers_own_messages_on_the_wire_and_trusts_a_folder() -> None:
    """What the fixture does not settle about ``members``. The npm SDK's ``unreadFor`` answers alike."""
    wire = message("w", MARA, 1, created_by="b2")
    # On the wire, a verified own message is read; with no members list, or an empty one, none is proved.
    assert ids(unread_for([wire], MARA, None, MEMBERS)) == []
    assert ids(unread_for([wire], MARA, None)) == ["w"]
    assert ids(unread_for([wire], MARA, None, None)) == ["w"]
    assert ids(unread_for([wire], MARA, None, [])) == ["w"]
    # The author's row plays no Character: unverifiable, so unread for the Character it claims.
    assert ids(unread_for([message("g", MARA, 1, created_by="b5")], MARA, None, MEMBERS)) == ["g"]
    # The owner's hand (created_by None) proves the owner's Character's own message.
    assert ids(unread_for([message("o", ADA, 1, created_by=None)], ADA, None, MEMBERS)) == []
    # Written by Mara's hand under Wren's name: not Mara's own (the claim is Wren's), unread for both.
    forged = message("f", WREN, 1, created_by="b2")
    assert ids(unread_for([forged], MARA, None, MEMBERS)) == ["f"]
    assert ids(unread_for([forged], WREN, None, MEMBERS)) == ["f"]
    # Message by message: one without created_by is trusted even beside others that carry it.
    folder_like = message("x", MARA, 2)
    forged_own = message("y", MARA, 3, created_by="b3")
    assert ids(unread_for([wire, folder_like, forged_own], MARA, None, MEMBERS)) == ["y"]
    assert ids(unread_for([wire, folder_like, forged_own], MARA, None)) == ["w", "y"]
    # A message with no narrator is sent by nobody, so it is unread for every Character it addresses.
    assert ids(unread_for([message("n", None, 1)], MARA, None)) == ["n"]
    # An empty id is no Character: nothing is unread for it, not even a message to everyone.
    assert unread_for([message("e", None, 1)], "", None) == []


# The shared edge cases: inputs the fixture leaves open, the same file byte for byte as the npm SDK's
# test/fixtures/message-edges.json (both suites hold its sha256), answers written by hand.
EDGES_FILE = REPO / "tests" / "fixtures" / "message-edges.json"
EDGES_SHA256 = "48fffaf28bced5faa49024f7d541a195938e03ebde4f2a71d21099c1d10a1980"


def _edge_answer(e: dict[str, Any]) -> Any:
    reader = e["reader"]
    if reader == "recipients":
        return recipients_of(e["message"])
    if reader == "addressed":
        return is_addressed_to(e["message"], e["character"])
    if reader == "everyone":
        return is_to_everyone(e["message"], keyless=e["keyless"])
    if reader == "unseen":
        return has_unseen_recipients(e["message"], keyless=e["keyless"])
    if reader == "unread":
        return ids(unread_for(e["messages"], e["reader_id"], None, e["members"]))
    if reader == "thread":
        return ids(thread_of(e["messages"], e["root"]))
    if reader == "edited":
        edit = edited_by(e["message"], e["members"])
        return {"edited": edit.edited, "by": edit.by}
    if reader == "note":
        return note_of(e["notes"], e["character"], e["members"])
    raise AssertionError(f"an edge of unknown reader {reader!r}")


def test_the_shared_edge_cases_notes_on_every_reader_the_created_at_rule_the_edit_the_line() -> None:
    raw = EDGES_FILE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EDGES_SHA256
    edges: list[dict[str, Any]] = json.loads(raw.decode("utf-8"))
    wrong = []
    for e in edges:
        got = _edge_answer(e)
        if got != e["want"] or type(got) is not type(e["want"]):
            wrong.append(f"{e['name']}: gave {got!r}, want {e['want']!r}")
    assert wrong == []
    assert len(edges) == 26


def test_keyless_is_a_boolean() -> None:
    not_bools: tuple[Any, ...] = ("yes", 1, None)
    for bad in not_bools:
        with pytest.raises(TypeError):
            is_to_everyone({"characters": []}, keyless=bad)
        with pytest.raises(TypeError):
            has_unseen_recipients({"characters": []}, keyless=bad)
    assert edited_by({"changed_by": "b2"}, None) == EditRead(True, None)
