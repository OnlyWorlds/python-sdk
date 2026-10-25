"""The lint: a world folder's shape against the schema, by schema-dist's own checker.

::

    python -m onlyworlds.lint PATH/TO/WORLD-FOLDER

One line per problem: a file outside the 22 type folders, a missing or duplicate ``id``, a key
that is not a field of its type, a value of the wrong shape for its kind, a link that does not
resolve inside the folder or resolves to the wrong type. A ``world.json`` stamped with a newer
folder format than the checker knows gets one warning line, never a problem. The last line is the
count it checked, so an empty report is a result and not a silence. Exit 0 clean, 1 with problems,
2 when the folder is not a world folder.

The checker is schema-dist's ``walk/lint_folder.py``, copied byte for byte at this package's pin
into ``_walk/`` beside the dist's ``schema.json``, and run on that file: the check this command
makes is the one the dist itself passes, and it needs no PyYAML. ``codegen/generate_schema.py
--check`` holds both copies to the verified dist.

One line is this runner's own: the checker reports a linked folder's ``world.json`` that git tracks
(a linked folder is never committed, folder spec 4.6), and says nothing when git is not installed;
here that case is a warning that the line went unchecked.

The doctor reads what a world says; the lint reads its shape. Neither writes.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

_WALK = Path(__file__).resolve().parent / "_walk"


def _checker() -> ModuleType:
    """The vendored ``lint_folder.py``, loaded by path: no import path changes, no PyYAML."""
    spec = importlib.util.spec_from_file_location("onlyworlds._walk.lint_folder", _WALK / "lint_folder.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load the vendored checker at {_WALK / 'lint_folder.py'}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def schema() -> dict[str, Any]:
    """The decoded schema the checker runs on: schema-dist's ``schema.json`` at this package's pin."""
    decoded: dict[str, Any] = json.loads((_WALK / "schema.json").read_text(encoding="utf-8"))
    return decoded


def format_version() -> str:
    """The folder format version the vendored checker was written against."""
    return str(_checker().FORMAT_VERSION)


def lint(folder: str | Path) -> Any:
    """Check the folder; returns the checker's report (``problems``, ``warnings``, ``summary``)."""
    src = Path(folder)
    report = _checker().lint_folder(src, schema())
    if shutil.which("git") is None and _linked(src):
        report.warnings.append(
            "world.json: carries an `api` block; whether git tracks it went unchecked (git is not installed)"
        )
    return report


def _linked(src: Path) -> bool:
    try:
        world = json.loads((src / "world.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(world, dict) and bool(world.get("api"))


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m onlyworlds.lint", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("folder", type=Path, help="a world folder (holds world.json and elements/)")
    args = ap.parse_args(argv)
    src: Path = args.folder
    # The checker's own command line's test for a world folder (its precedence, parenthesized).
    if not src.is_dir() or (not (src / "world.json").exists() and not (src / "elements").is_dir()):
        print(f"{src}: not a world folder (no world.json, no elements/)")
        return 2
    report = lint(src)
    for w in report.warnings:
        print(w)
    for p in report.problems:
        print(p)
    print(report.summary)
    return 1 if report.problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
