"""Published text names no one inside the team and points at nothing the public cannot read.

The maintainers' discussion happens in rooms and trackers that are not public, so a room
or item pointer in the source is noise to a reader. A person named in published text is
Titus, the founder; a ruling is dated, not pointed at (ruled 2026-10-24).

This script holds the patterns in one place. CI and the release workflow both run it.

Usage:
  python scripts/public_words.py            scan the published paths (below)
  python scripts/public_words.py PATH ...   scan these files or directories instead
Exit 1 and one line per finding; exit 0 when the tree is clean.

Not scanned: CHANGELOG.md (the dated record, kept as written), tests/ and their fixtures,
and codegen/schema-dist/ (vendored and hash-verified).
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PUBLISHED = [
    "src",
    "codegen",
    "scripts",
    ".github",
    "README.md",
    "AGENTS.md",
    "SECURITY.md",
    "pyproject.toml",
]
VENDORED = ("codegen/schema-dist/",)

# Each row: a pattern, and what a writer puts instead.
PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bh[0-9]{1,3} #[0-9]+"), "the date of the ruling"),
    (re.compile(r"\bh[0-9]{1,3}(?= [0-9]{4}-[0-9]{2}-[0-9]{2})"), "the date alone"),
    (re.compile(r"\b(?:[Kk]eel|OW [A-Z][a-z]+) #[0-9]+"), "the date, or what changed"),
    (re.compile(r"(?<![\w/.&-])#[0-9]{4,5}\b"), "the date of the ruling"),
    (re.compile(r"\bD[0-9]{2,3}[a-z]?\b"), "nothing: an internal decision id"),
    (re.compile(r"[A-Za-z]:[/\\]Users[/\\]"), "nothing: a path on a maintainer's machine"),
]

# The team's own words, held as the first 12 hex of each word's sha256, so this list does not
# publish what it refuses: one word, or "the" and a word. Case-sensitive, as the words are names.
# The same rows as the npm SDK's scripts/public-words.mjs.
_FOLDER = "nothing, or the thing described plainly: a team folder"
_NAME = "nothing, Titus, or the maintainers"
WORDS: dict[str, str] = {
    "2e786c488b83": "Titus, or the founder",
    "9dd2ca99ffc9": "nothing: an internal surface",
    "271c535631ff": "nothing: an internal surface",
    "4340fc2d9418": "nothing: an internal mailbox",
    **dict.fromkeys(
        ["d97084040035", "b372644b8fec", "0c6874e447ef", "66ada4d485d7",
         "3892e10346fd", "8899ecd1626d", "44e7d4b24846", "0aa91af2ec4c"],
        _FOLDER,
    ),
    **dict.fromkeys(
        ["7d07b8e5c49d", "0ced2c75df2d", "9c2a44c4716d", "d3aaf0e63f73", "9067ae5c5374",
         "fdfd7512f532", "fbee9d8f57c5", "6a6ac8386005", "d5ef0f0e059a", "c62063d665f3",
         "06110f3dd13d"],
        _NAME,
    ),
}
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9]*")

# Lines allowed by their exact text (trimmed; the first 16 hex of its sha256), never by file.
EXEMPT_LINES = {
    "012d30a55f7b2ad2",  # README: the one line that says who maintains the repository
}


def _hash(text: str, n: int) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


def scan_text(text: str, where: str) -> list[str]:
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if _hash(line.strip(), 16) in EXEMPT_LINES:
            continue
        prev, prev_end = None, -1
        for m in _TOKEN.finditer(line):
            words = [m.group(0)]
            if prev == "the" and line[prev_end:m.start()] == " ":
                words.append(f"the {m.group(0)}")
            for w in words:
                instead = WORDS.get(_hash(w, 12))
                if instead:
                    out.append(f"{where}:{n}: {w!r} (write {instead})")
            prev, prev_end = m.group(0), m.end()
        taken: list[tuple[int, int]] = []  # a room pointer is one finding, not two
        for pat, instead in PATTERNS:
            for m in pat.finditer(line):
                if any(a <= m.start() < b for a, b in taken):
                    continue
                taken.append((m.start(), m.end()))
                out.append(f"{where}:{n}: {m.group(0)!r} (write {instead})")
    return out


def tracked(paths: list[str]) -> list[str]:
    res = subprocess.run(
        ["git", "ls-files", "-z", "--", *paths],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    return [p for p in res.stdout.decode("utf-8").split("\0") if p]


def files_for(args: list[str]) -> list[Path]:
    if not args:
        names = [p for p in tracked(PUBLISHED) if not p.startswith(VENDORED)]
        return [ROOT / p for p in names]
    out: list[Path] = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            out.extend(sorted(f for f in p.rglob("*") if f.is_file() and ".git" not in f.parts))
        else:
            out.append(p)
    return out


def main(argv: list[str]) -> int:
    findings: list[str] = []
    files = files_for(argv)
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        where = f.relative_to(ROOT).as_posix() if f.is_relative_to(ROOT) else str(f)
        findings.extend(scan_text(text, where))
    for line in findings:
        print(line)
    print(f"public words: {len(findings)} finding(s) in {len(files)} file(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
