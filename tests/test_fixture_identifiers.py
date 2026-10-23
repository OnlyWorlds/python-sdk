"""No account identifier of a real export in any fixture or test file, checked by hash.

The fixtures are real exports scrubbed by Boss's script (OW Market h40 #11420, #11430, #11434;
Skeld's doctrine, #11415: a fixture carries no account identifier). The identifiers themselves stay
out of the package: only their sha256 hex digests are here, and every word-start window of each
file's text, lowercased, of each identifier's length is hashed and compared (so an identifier is
found inside a longer word too, such as a file name). A zip is read member by member, names and
bytes; a gzip (LegendKeeper's ``.lk``) decompressed. The World Anvil handle has its own check in
``test_worldanvil.py``.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import zipfile
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent

#: what must appear in no fixture and no test file: (sha256 of the lowercased identifier, its length)
FORBIDDEN = {
    "the Kanka export account's username": ("18153dcfa045066c9c1cba7888d0be826f55b0d47b86765a39f9c51708a9b3b1", 16),
    "the LegendKeeper account's id": ("fceeab8b4d7652711e65241ff1c880b3bbb28fb71e63ca5815b278d7acc74156", 25),
    "the LegendKeeper account's map image asset id": (
        "d04851f3065f8a3cc2d7624db15d65a8ca528f0d1978dd5f2af89c3cb21e27fe",
        36,
    ),
}

FILES = sorted(
    [p for p in (TESTS / "fixtures").rglob("*") if p.is_file()]
    + [p for p in TESTS.rglob("*.py") if "__pycache__" not in p.parts]
)


def texts(name: str, raw: bytes) -> list[str]:
    """What a file says: its text, a zip's member names and texts, a gzip's decompressed text."""
    if raw[:4] == b"PK\x03\x04":
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            out = [name]
            for info in zf.infolist():
                out.append(info.filename)
                out += texts(info.filename, zf.read(info))
            return out
    if raw[:2] == b"\x1f\x8b":
        return texts(name, gzip.decompress(raw))
    return [raw.decode("utf-8", errors="replace")]


def found(text: str, digest: str, length: int) -> list[str]:
    """The windows of ``text`` (lowercased) of ``length`` characters starting a word whose sha256 is ``digest``."""
    low = text.lower()
    hits = []
    for i in range(len(low) - length + 1):
        if (i == 0 or not low[i - 1].isalnum()) and low[i].isalnum():
            window = low[i : i + length]
            if hashlib.sha256(window.encode("utf-8")).hexdigest() == digest:
                hits.append(window)
    return hits


def test_the_fixtures_are_all_read() -> None:
    names = {p.relative_to(TESTS).as_posix() for p in FILES}
    assert {
        "fixtures/kanka/quay-export-world_20261023_074706.zip",
        "fixtures/legendkeeper/the-quay-world.lk",
        "fixtures/legendkeeper/the-quay-world-3.json",
        "test_kanka.py",
        "test_legendkeeper_file.py",
        "test_fixture_identifiers.py",
    } <= names


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.relative_to(TESTS).as_posix())
def test_no_account_identifier(path: Path) -> None:
    said = texts(path.name, path.read_bytes())
    for what, (digest, length) in FORBIDDEN.items():
        assert not any(found(t, digest, length) for t in said), f"{path.name}: {what}"


def test_the_check_flags_a_planted_identifier() -> None:
    """The check, run over the digest of a stand-in: any case, inside a longer word, in a zip and a gzip."""
    digest = hashlib.sha256(b"planted-user").hexdigest()
    assert found("by Planted-User's world", digest, 12) == ["planted-user"]
    assert found("planted-users-world_20261023.zip", digest, 12) == ["planted-user"]
    assert found("by someone-planted-user", digest, 12) == ["planted-user"]  # a word after a hyphen starts one
    assert found("by xplanted-user", digest, 12) == []
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("campaign.json", '{"name": "planted-user\'s world"}')
        zf.writestr("planted-user/notes.json", "{}")
    said = texts("x.zip", buf.getvalue())
    assert sum(len(found(t, digest, 12)) for t in said) == 2
    said = texts("x.lk", gzip.compress(b'{"createdBy": "planted-user"}'))
    assert [h for t in said for h in found(t, digest, 12)] == ["planted-user"]
