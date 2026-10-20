"""Check a world folder against the decoded schema: `ow lint`, as a walk file.

    python walk/lint_folder.py PATH/TO/WORLD-FOLDER [--schema DIR]

Reads `world.json` and every `elements/<type>/*.json` under the folder and
reports, one line each: a file outside the 22 type folders, a missing or
duplicate UUID `id`, a key that is not a field of its type (the shape Simmer's
PROFILE found three hundred of in one world: `creature.characters`,
`event.location`, `event.actor`), a value of the wrong shape for its kind, and
a link that does not resolve inside the folder or resolves to the wrong type.
Server-managed keys (`type`, `created_at`, `updated_at`, `change_seq`,
`created_by`), the folder format's own keys (`local_updated_at`,
`server_updated_at`, `image_media_id`) and extension prefixes (`x_`, `atlas_`,
`shadow_`) pass; nothing else undeclared does. A string field may be null on
disk (read as "", the unset string). The last line is the count it checked, so an empty
report is a result and not a silence. Exit 0 clean, 1 with problems, 2 when
the folder is not a world folder.

The same function gates the published example world (publish_dist.py), so the
check a stranger runs is the check the dist itself passed. Decoding goes
through schema_walk.py, the one decoder; this file adds no reading of the
YAML of its own. `--schema` defaults to the `schema/` directory beside this
file's parent, which is where both keel and the dist keep it.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema_walk import decode_schema  # noqa: E402

# Keys an element body carries that the schema does not declare: the type
# slug and the server-managed fields (elements/serialize.py READONLY_FIELDS
# minus `world`, which bodies never carry). Extension prefixes as served.
BODY_EXTRA_KEYS = {"type", "created_at", "updated_at", "change_seq", "created_by",
                   "changed_by", "changed_via"}
# Keys the folder format itself puts in an element file (folder spec section 5,
# the linked-folder guidance): Atlas's two sync stamps and the media id. A
# linked folder carries them on every edited element; Kael's first run on the
# Captain's Atlas folders flagged all 1,669 of one world's elements (2026-10-12).
FOLDER_KEYS = {"local_updated_at", "server_updated_at", "image_media_id"}
EXTENSION_PREFIXES = ("x_", "atlas_", "shadow_")


class Report:
    """What a lint found: the problems, one line each, and what it looked at."""

    def __init__(self) -> None:
        self.problems: list[str] = []
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
        for key, value in body.items():
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
    notes: list[str] = []
    decoded = decode_schema(args.schema, note=notes.append)
    for n in notes:
        print(f"walk note: {n}")
    report = lint_folder(src, decoded)
    for p in report.problems:
        print(p)
    print(report.summary)
    return 1 if report.problems else 0


if __name__ == "__main__":
    sys.exit(main())
