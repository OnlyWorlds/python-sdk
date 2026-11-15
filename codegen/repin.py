#!/usr/bin/env python3
"""Move the schema pin: vendor schema-dist at a tag into codegen/schema-dist and rewrite codegen/schema-pin.json.

Usage:
  python codegen/repin.py <tag> "<note for the pin this one replaces>" [--schema-dist <checkout>]

The tree is ``git archive`` of the tag in a local checkout of github.com/OnlyWorlds/schema-dist (by default the
directory ``schema-dist`` beside this repository, or ``$OW_SCHEMA_DIST``), written byte for byte. Whatever the
vendored directory held before is removed, so it holds what the tag holds and nothing else.

Nothing is written unless all of these hold:
  - the tag is not the one already pinned;
  - every file in the archive has the sha256 the MANIFEST lists for it, and the MANIFEST lists no other file;
  - the tag ends with the serial the archive's VERSION states;
  - the archive's MANIFEST.json has the sha256 of the file GitHub serves at the tag (a tag moved in the local
    checkout, or on GitHub, stops here).

The pin record keeps the replaced pin first in ``previous_pins`` with the note given. The file keeps its line
endings. Afterwards regenerate and run the repository's checks; this script does neither.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDORED = ROOT / "codegen" / "schema-dist"
PIN = ROOT / "codegen" / "schema-pin.json"
RAW = "https://raw.githubusercontent.com/OnlyWorlds/schema-dist/{tag}/MANIFEST.json"


def _git(checkout: Path, *args: str) -> bytes:
    done = subprocess.run(["git", "-C", str(checkout), *args], capture_output=True, check=False)
    if done.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed in {checkout}: {done.stderr.decode('utf-8', 'replace').strip()}")
    return done.stdout


def read_tag(checkout: Path, tag: str) -> tuple[str, dict[str, bytes]]:
    """The commit the tag names in the checkout, and every file of its tree."""
    commit = _git(checkout, "rev-parse", "--verify", tag + "^{commit}").decode("ascii").strip()
    with tarfile.open(fileobj=io.BytesIO(_git(checkout, "archive", "--format=tar", tag))) as tar:
        files: dict[str, bytes] = {}
        for member in tar.getmembers():
            if member.isfile():
                handle = tar.extractfile(member)
                assert handle is not None
                files[member.name] = handle.read()
    return commit, files


def check(tag: str, files: dict[str, bytes], pinned_tag: str) -> tuple[str, int, str, str]:
    """Refuse a tree that is not the tag GitHub serves. Returns the MANIFEST's sha256, serial, canonical, published."""
    if tag == pinned_tag:
        raise SystemExit(f"{tag} is already the pin")
    if "MANIFEST.json" not in files or "VERSION" not in files:
        raise SystemExit(f"the tree at {tag} has no MANIFEST.json or no VERSION")
    sha = hashlib.sha256(files["MANIFEST.json"]).hexdigest()
    listed: dict[str, str] = json.loads(files["MANIFEST.json"].decode("utf-8"))["files"]
    held = {name: hashlib.sha256(data).hexdigest() for name, data in files.items() if name != "MANIFEST.json"}
    if held != listed:
        wrong = sorted(name for name in held.keys() | listed.keys() if held.get(name) != listed.get(name))
        raise SystemExit(f"the tree at {tag} disagrees with its own MANIFEST.json: {wrong}")
    version = dict(
        line.split(": ", 1) for line in files["VERSION"].decode("utf-8").strip().splitlines() if ": " in line
    )
    serial = int(version["serial"])
    if not tag.endswith(f"-dist.{serial}"):
        raise SystemExit(f"{tag} does not end with the serial its VERSION states, {serial}")
    try:
        with urllib.request.urlopen(RAW.format(tag=tag), timeout=30) as answer:
            served = hashlib.sha256(answer.read()).hexdigest()
    except urllib.error.URLError as err:
        raise SystemExit(f"GitHub served no MANIFEST.json at {tag}: {err}") from err
    if served != sha:
        raise SystemExit(
            f"the MANIFEST.json GitHub serves at {tag} ({served[:12]}) is not the local archive's ({sha[:12]}): "
            "the tag differs between the checkout and GitHub"
        )
    return sha, serial, version["canonical"].strip(), version["published"].strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("tag", help="the schema-dist tag to pin, e.g. v0.34.1-dist.130")
    ap.add_argument("note", help="what the new pin moved, kept beside the pin it replaces")
    ap.add_argument(
        "--schema-dist",
        type=Path,
        default=Path(os.environ.get("OW_SCHEMA_DIST", ROOT.parent / "schema-dist")),
        help="a local checkout of github.com/OnlyWorlds/schema-dist that has the tag",
    )
    args = ap.parse_args()
    if not args.note.strip():
        raise SystemExit("the note is empty: say what the new pin moved")

    raw_pin = PIN.read_bytes()
    pin = json.loads(raw_pin.decode("utf-8"))
    commit, files = read_tag(args.schema_dist, args.tag)
    sha, serial, canonical, published = check(args.tag, files, pin["tag"])

    for entry in VENDORED.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    for name, data in files.items():
        path = VENDORED / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    replaced = {"tag": pin["tag"], "manifest_sha256": pin["manifest_sha256"], "note": args.note}
    pin["previous_pins"] = [replaced, *pin["previous_pins"]]
    pin.update(
        tag=args.tag,
        commit=commit,
        manifest_sha256=sha,
        canonical_version=canonical,
        dist_serial=serial,
        published=published,
        pinned_at=datetime.date.today().isoformat(),
        pinned_by=(
            "The maintainer: tree from `git archive` of the tag in a schema-dist checkout "
            f"({len(files)} files: the {len(files) - 1} the MANIFEST lists, and MANIFEST.json itself); "
            "files re-hashed against MANIFEST.json by verify_dist.py; MANIFEST self-hash matched against "
            "the raw file GitHub serves at the tag, whose ref resolves to the commit above."
        ),
    )
    ending = "\r\n" if b"\r\n" in raw_pin else "\n"
    text = json.dumps(pin, indent=2, ensure_ascii=False) + "\n"
    PIN.write_bytes(text.replace("\n", ending).encode("utf-8"))
    print(
        f"{ROOT.name}: {args.tag} commit {commit[:7]} serial {serial} canonical {canonical} "
        f"manifest {sha[:12]} files {len(files)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
