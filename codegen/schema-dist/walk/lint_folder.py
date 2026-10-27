"""Check a world folder against the decoded schema: `ow lint`, as a walk file.

    python walk/lint_folder.py PATH/TO/WORLD-FOLDER [--schema DIR]

Reads `world.json` and every `elements/<type>/*.json` under the folder and
reports, one line each: a file outside the 22 type folders, a missing or
duplicate UUID `id`, a key that is not a field of its type (the shape one real
world's profile found three hundred of: `creature.characters`,
`event.location`, `event.actor`), a value of the wrong shape for its kind, and
a link that does not resolve inside the folder or resolves to the wrong type.
Server-managed keys (`type`, `created_at`, `updated_at`, `change_seq`,
`created_by`), the folder format's own keys (`local_updated_at`,
`server_updated_at`, `image_media_id`) and extension prefixes (`x_`, `atlas_`,
`shadow_`) pass; nothing else undeclared does. A string field may be null on
disk (read as "", the unset string). A known-of stub (`known_of: true`, folder
spec 4.4) passes with only the keys it keeps; one that writes an unset field
is reported. `records/` (spec 4.5) is not elements and is not read. A `world.json`
whose `format_version` is newer than FORMAT_VERSION below gets one warning line,
never a problem; an older or absent stamp passes. The last line is the count it checked, so an empty
report is a result and not a silence. Exit 0 clean, 1 with problems, 2 when
the folder is not a world folder.

The same function gates the published example world (publish_dist.py), so the
check a stranger runs is the check the dist itself passed. Decoding goes
through schema_walk.py, the one decoder; this file adds no reading of the
YAML of its own, and imports the walk only when run as a command, so a program that imports
`lint_folder()` and decodes the schema itself loads no YAML and gets no sys.path change. `--schema` defaults to the `schema/` directory beside this
file's parent, which is where both keel and the dist keep it.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path

# The folder format's version this lint was written against: the folder spec's
# own version line, the one source. It moves when the spec's version moves, and
# publish_dist.py writes the dist README's version sentence from it.
FORMAT_VERSION = "0.3.19"

# Keys an element body carries that the schema does not declare: the type
# slug and the server-managed fields (elements/serialize.py READONLY_FIELDS
# minus `world`, which bodies never carry). Extension prefixes as served.
BODY_EXTRA_KEYS = {"type", "created_at", "updated_at", "change_seq", "created_by",
                   "changed_by", "changed_via", "changed_client"}
# Keys the folder format itself puts in an element file (folder spec section 5,
# the linked-folder guidance): Atlas's two sync stamps and the media id. A
# linked folder carries them on every edited element; the first run on the
# founder's Atlas folders flagged all 1,669 of one world's elements (2026-10-12).
# `hidden` (folder spec 4.8, 2026-10-23): what the source hid stays hidden in the
# folder; a converter door writes it, a push withholds the element until keel
# takes the mark on a create. Must be a boolean (checked below).
FOLDER_KEYS = {"local_updated_at", "server_updated_at", "image_media_id", "known_of",
               "hidden"}
EXTENSION_PREFIXES = ("x_", "atlas_", "shadow_")
# A known-of stub (folder spec 4.4) keeps these and leaves every unset field out
# (rule 1); a field keel marks public (presentation.json's `public` lists) may also be there, set. The
# lint cannot tell public from not without keel's wrapper, so it flags only
# what rule 1 forbids outright: an unset value written into a stub.
STUB_KEEPS = {"id", "type", "name", "description", "supertype", "subtype", "image_url",
              "created_at", "updated_at", "change_seq"}


class Report:
    """What a lint found: the problems, one line each, and what it looked at."""

    def __init__(self) -> None:
        self.problems: list[str] = []
        self.warnings: list[str] = []  # printed, never counted: the exit code is the problems'
        self.files = 0
        self.types: set[str] = set()

    def add(self, line: str) -> None:
        self.problems.append(line)

    @property
    def summary(self) -> str:
        return (f"checked {self.files} element files in {len(self.types)} types: "
                f"{len(self.problems)} problems")


def is_uuid(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def version_tuple(value) -> tuple[int, ...] | None:
    """`"0.3.19"` -> (0, 3, 19); None for anything that is not dotted integers."""
    if not isinstance(value, str):
        return None
    try:
        return tuple(int(p) for p in value.split("."))
    except ValueError:
        return None


def git_tracks(path: Path) -> bool:
    """True when a git repository tracks `path` (folder spec 4.6 d: a world.json
    that carries an `api` block is a linked folder and is never committed)."""
    try:
        r = subprocess.run(["git", "-C", str(path.parent), "ls-files", "--error-unmatch",
                            path.name], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def lint_folder(src: Path, decoded: dict) -> Report:
    """Check the folder at `src` against `decoded` (decode_schema's output)."""
    report = Report()
    world_path = src / "world.json"
    if not world_path.exists():
        report.add("world.json: missing")
    else:
        try:
            world = json.loads(world_path.read_text(encoding="utf-8"))
        except ValueError as e:
            world = {}
            report.add(f"world.json: not JSON ({e})")
        if not isinstance(world, dict) or not world.get("id") or "name" not in world:
            report.add("world.json: needs `id` and `name`")
        if isinstance(world, dict) and world.get("api") and git_tracks(world_path):
            report.add("world.json: carries an `api` block and git tracks it; a linked "
                       "folder is never committed (folder spec 4.6 d), keep the key "
                       "outside the repository")
        stamp = world.get("format_version") if isinstance(world, dict) else None
        known = version_tuple(FORMAT_VERSION)
        seen = version_tuple(stamp)
        if seen is not None and seen > known:
            report.warnings.append(
                f"world.json: format_version {stamp} is newer than this lint knows "
                f"({FORMAT_VERSION}): update the lint, or read the spec for what changed")

    base = {f["name"]: f for f in decoded["base"] if f["name"] != "world"}
    bodies: dict[str, tuple[str, dict, str]] = {}
    elements = src / "elements"
    for path in sorted(elements.rglob("*.json")) if elements.is_dir() else []:
        rel = path.relative_to(src).as_posix()
        report.files += 1
        slug = path.parent.name
        if slug not in decoded["types"] or path.parent.parent != elements:
            report.add(f"{rel}: not under elements/<one of the 22 types>/")
            continue
        report.types.add(slug)
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as e:
            report.add(f"{rel}: not JSON ({e})")
            continue
        if not isinstance(body, dict):
            report.add(f"{rel}: not a JSON object")
            continue
        if not is_uuid(body.get("id")):
            report.add(f"{rel}: no UUID `id`")
            continue
        if body["id"] in bodies:
            report.add(f"{rel}: duplicate id {body['id']} (also {bodies[body['id']][2]})")
            continue
        bodies[body["id"]] = (slug, body, rel)

    for slug, body, rel in bodies.values():
        fields = dict(base)
        for f in decoded["types"][slug]:
            if f["kind"] == "generic":
                fields[f["type_key"]] = {"kind": "generic_type"}
                fields[f["id_key"]] = {"kind": "generic_id"}
            else:
                fields[f["name"]] = f
        if body.get("type", slug) != slug:
            report.add(f"{rel}: `type` is {body['type']!r}, folder says {slug!r}")
        if "known_of" in body:
            if body["known_of"] is not True:
                report.add(f"{rel}: `known_of` is {body['known_of']!r}; a stub says true, a whole element leaves it out")
            else:
                for key, value in body.items():
                    if key not in STUB_KEEPS and key != "known_of" and value in ("", None, []):
                        report.add(f"{rel}: known-of stub writes unset `{key}`; a stub leaves unset fields out")
        for key, value in body.items():
            if key == "hidden" and not isinstance(value, bool):
                report.add(f"{rel}: `hidden` must be true or false, not {value!r}")
                continue
            # `x_served_trimmed` (folder spec 4.4 rule 6) is kept exactly as served, like
            # `known_of`: the names of the fields keel trimmed for the reader. A folder keeps
            # it and never sends it up; here it must be a list. It starts `x_`, so the
            # extension pass below would wave any shape through: check it first.
            if key == "x_served_trimmed" and not isinstance(value, list):
                report.add(f"{rel}: `x_served_trimmed` must be an array of field names, not {value!r}")
                continue
            if key in BODY_EXTRA_KEYS or key in FOLDER_KEYS \
                    or key.startswith(EXTENSION_PREFIXES):
                continue
            spec = fields.get(key)
            if spec is None:
                report.add(f"{rel}: `{key}` is not a field of {slug}")
                continue
            kind = spec["kind"]
            # A string is "" or content (rulings: string-empty-is-unset); on disk
            # null reads as "" too, since the platform takes null on a write and
            # serves "" back. Atlas writes null for an empty text field.
            if kind == "scalar_str" and value is not None and not isinstance(value, str):
                report.add(f"{rel}: `{key}` should be a string")
            elif kind == "scalar_int" and value is not None and (
                    not isinstance(value, int) or isinstance(value, bool)):
                report.add(f"{rel}: `{key}` should be an integer or null")
            elif kind == "single" and value is not None:
                _check_link(report, rel, key, value, spec["target"], bodies)
            elif kind == "multi":
                if not isinstance(value, list):
                    report.add(f"{rel}: `{key}` should be an array")
                else:
                    for v in value:
                        _check_link(report, rel, key, v, spec["target"], bodies)
            elif kind == "generic_type" and value not in (None, "") \
                    and value not in decoded["types"]:
                report.add(f"{rel}: `{key}` {value!r} is not a type slug")
            elif kind == "generic_id" and value is not None:
                tkey = next(f["type_key"] for f in decoded["types"][slug]
                            if f["kind"] == "generic" and f["id_key"] == key)
                _check_link(report, rel, key, value, body.get(tkey), bodies)
    return report


def _check_link(report, rel, key, value, target, bodies) -> None:
    if not is_uuid(value):
        report.add(f"{rel}: `{key}` holds {value!r}, not a UUID")
    elif value not in bodies:
        report.add(f"{rel}: `{key}` -> {value} is not in the folder")
    elif target and bodies[value][0] != target:
        report.add(f"{rel}: `{key}` -> a {bodies[value][0]}, expected {target}")


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("folder", type=Path, help="a world folder (holds world.json and elements/)")
    ap.add_argument("--schema", type=Path,
                    default=Path(__file__).resolve().parent.parent / "schema",
                    help="the schema YAML directory (default: the one beside this walk)")
    args = ap.parse_args(argv)
    src = args.folder
    if not src.is_dir() or not (src / "world.json").exists() and not (src / "elements").is_dir():
        print(f"{src}: not a world folder (no world.json, no elements/)")
        return 2
    if not args.schema.is_dir():
        print(f"{args.schema}: no schema directory; pass --schema DIR")
        return 2
    # The walk is imported here, not at the top: importing this file (a package vendors it and calls
    # lint_folder() with its own decode) then has no side effect, puts nothing on sys.path and loads
    # no PyYAML (a top-level insert put this folder first on sys.path for the whole process, so a
    # package that vendors this file saw `import errors` find its own file, 2026-10-25).
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from schema_walk import decode_schema  # noqa: E402
    notes: list[str] = []
    decoded = decode_schema(args.schema, note=notes.append)
    for n in notes:
        print(f"walk note: {n}")
    report = lint_folder(src, decoded)
    for w in report.warnings:
        print(w)
    for p in report.problems:
        print(p)
    print(report.summary)
    return 1 if report.problems else 0


if __name__ == "__main__":
    sys.exit(main())
