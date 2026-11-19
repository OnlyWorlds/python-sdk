"""The README's examples type-check against the installed package.

Every ```python block of README.md is its own module, checked with ``mypy --strict`` against the package
as installed (the source tree in a plain run, the built wheel in CI's wheel job), so a renamed function, a
dropped keyword or a changed return type turns a block red here before a stranger copies it.

A block often uses what an earlier block made (``client``) or a value the reader brings (``cid``). The
first pass checks each block alone and reads which names it uses without defining them; the second gives
it exactly those, at the top: a name the package exports is imported from it (so the export must exist),
any other is declared with its type from CONTEXT below. A name in neither fails the test by name.
The examples are checked, never run: what they print and what the server answers are not checked here.
Element bodies are ``dict[str, Any]``, so a wrong key or value inside one passes; a function, a keyword,
an attribute and a return type are what this holds.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import onlyworlds

ROOT = Path(__file__).resolve().parent.parent

# What the README's prose says a name is when a block uses it without making it.
CONTEXT = {
    # a client made in an earlier block
    "client": "onlyworlds.Client",
    # ids and words the reader brings
    "cid": "str",  # a Character's id
    "new_id": "str",
    "character_id": "str",
    "element_id": "str",
    "me": "str",  # the reader's own Character id
    "key": "str",  # a LegendKeeper API key
    "text": "str",
    "link": "str",
    # data the reader holds
    "folder": "onlyworlds.Folder",
    "elements": "list[dict[str, Any]]",
    "members": "list[dict[str, Any]]",
    # the feed's position, None before the first walk
    "saved_cursor": "str | None",
}

FREE = re.compile(r'^(b\d+_L(\d+))\.py:(\d+): error: Name "([^"]+)" is (?:not defined|used before definition)')
ERROR = re.compile(r"^(b\d+_L(\d+))\.py:(\d+): error: (.*)$")


def _blocks() -> list[tuple[int, str]]:
    lines = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
    found: list[tuple[int, str]] = []
    i = 0
    while i < len(lines):
        if lines[i] == "```python":
            j = i + 1
            while j < len(lines) and lines[j] != "```":
                j += 1
            assert j < len(lines), f"README line {i + 1}: a python block that never closes"
            found.append((i + 2, "\n".join(lines[i + 1 : j])))
            i = j
        i += 1
    return found


def _mypy(folder: Path, files: dict[str, str]) -> list[str]:
    for name, text in files.items():
        (folder / name).write_text(text, encoding="utf-8")
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--strict",
            "--no-error-summary",
            "--show-error-codes",
            "--cache-dir",
            str(folder / ".mypy_cache"),
            *sorted(files),
        ],
        cwd=folder,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert r.returncode in (0, 1), f"mypy did not run: exit {r.returncode}\n{r.stdout}{r.stderr}"
    out = [line for line in r.stdout.splitlines() if ": error: " in line]
    assert (r.returncode == 0) == (not out), f"mypy's exit and its lines disagree:\n{r.stdout}{r.stderr}"
    return out


def test_every_python_block_in_the_readme_type_checks(tmp_path: Path) -> None:
    exported = set(onlyworlds.__all__)
    blocks = _blocks()
    assert blocks, "the README has no python block: the check would see nothing"
    names = {f"b{n:02d}_L{line}.py": body for n, (line, body) in enumerate(blocks)}

    # Pass 1: each block alone; read the names it uses without making them.
    free: dict[str, set[str]] = {}
    for line in _mypy(tmp_path, {k: v + "\n" for k, v in names.items()}):
        m = FREE.match(line)
        if m:
            free.setdefault(m.group(1) + ".py", set()).add(m.group(4))

    # Pass 2: the same blocks, each with exactly its free names imported or declared at the top.
    unknown: list[str] = []
    full: dict[str, str] = {}
    offset: dict[str, int] = {}
    for file, body in names.items():
        used = sorted(free.get(file, set()))
        from_pkg = [x for x in used if x in exported]
        declared = [x for x in used if x not in exported]
        unknown += [f"README line {file.split('_L')[1][:-3]}: `{x}`" for x in declared if x not in CONTEXT]
        head = ["from typing import Any", "import onlyworlds"]
        if from_pkg:
            head.append(f"from onlyworlds import {', '.join(from_pkg)}")
        head += [f"{x}: {CONTEXT[x]}" for x in declared if x in CONTEXT]
        head.append("_ = (Any, onlyworlds)")
        offset[file] = len(head)
        full[file] = "\n".join(head) + "\n" + body + "\n"
    assert unknown == [], "a block uses a name no earlier block makes, the package lacks and CONTEXT does not type"

    shown: list[str] = []
    for line in _mypy(tmp_path, full):
        m = ERROR.match(line)
        assert m, f"an error line outside the README's blocks: {line}"
        readme_line = int(m.group(2)) + int(m.group(3)) - offset[m.group(1) + ".py"] - 1
        shown.append(f"README line {readme_line}: {m.group(4)}")
    assert shown == [], "README examples that do not type-check"
