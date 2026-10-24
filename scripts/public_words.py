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
SELF = "scripts/public_words.py"  # its patterns would match themselves

# Each row: a pattern, and what a writer puts instead.
PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bh[0-9]{1,3} #[0-9]+"), "the date of the ruling"),
    (re.compile(r"\bh[0-9]{1,3}(?= [0-9]{4}-[0-9]{2}-[0-9]{2})"), "the date alone"),
    (re.compile(r"\b(?:[Kk]eel|OW [A-Z][a-z]+) #[0-9]+"), "the date, or what changed"),
    (re.compile(r"(?<![\w/.&-])#[0-9]{4,5}\b"), "the date of the ruling"),
    (re.compile(r"\bD[0-9]{2,3}[a-z]?\b"), "nothing: an internal decision id"),
    (re.compile(r"\bCaptain\b"), "Titus, or the founder"),
    (re.compile(r"\bthe Deck\b"), "nothing: an internal surface"),
    (re.compile(r"\bCarrier\b"), "nothing: an internal surface"),
    (re.compile(r"allthecarriercrew"), "nothing: an internal mailbox"),
    (
        re.compile(r"\b(?:Orrery|Hatchery|Armature|Hangar|Bridge|Forge|Assembly|Studio)\b"),
        "nothing, or the thing described plainly: a team folder",
    ),
    (
        re.compile(r"\b(?:Kael|Skeld|Temper|Seethe|Quillon|Nucleus|Simmer|Boss|TC|Claudette|Vesper)\b"),
        "nothing, Titus, or the maintainers",
    ),
    (re.compile(r"[A-Za-z]:[/\\]Users[/\\]"), "nothing: a path on a maintainer's machine"),
]

# Lines allowed by their exact text (stripped), never by file.
EXEMPT_LINES = {
    # README: the one line that says who maintains the repository.
    "**Who writes this repository.** The package is maintained by Kael, one of a crew of AI "
    "minds working with the OnlyWorlds founder, who answers for it. Kael reads and answers its "
    "issues and pull requests; until the crew posts from an identity of its own, those replies "
    "post from the founder's account, so a reply from `tmoosting` may be Kael's. `CHANGELOG.md` "
    "is the crew's record as it was written: its crew names, room references and keel items "
    "(keel #519, the API server's own tracker) point at records outside this repository.",
    # release.yml: the changelog-entry check's own list of the words it refuses.
    "if grep -nE 'h[0-9]{1,3} #[0-9]+|\\b([Kk]eel|OW [A-Z][a-z]+) #[0-9]+|\\bCaptain\\b|"
    "\\bthe Deck\\b|\\bCarrier\\b|Armature|Orrery|Hangar|Hatchery|allthecarriercrew' entry.md; then",
}


def scan_text(text: str, where: str) -> list[str]:
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if line.strip() in EXEMPT_LINES:
            continue
        taken: list[tuple[int, int]] = []  # "h37 #3053" is one finding, not two
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
        names = [p for p in tracked(PUBLISHED) if not p.startswith(VENDORED) and p != SELF]
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
