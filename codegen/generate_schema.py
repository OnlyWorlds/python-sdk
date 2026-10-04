#!/usr/bin/env python3
"""Generate src/onlyworlds/_schema.py from the vendored schema distribution.

Build-time only: needs PyYAML (the walk imports it). The generated module has no
dependencies, so the published package does not need PyYAML at runtime.

The type list comes from THE walk (codegen/schema-dist/walk/schema_walk.py),
imported, never re-implemented. A second witness is checked on every run: the
walk's list must equal the dist's schema/*.yaml stems minus the two non-element
files (base_properties, world). If they ever disagree, generation fails instead
of picking one.

Order of checks matters: the dist is authenticated (MANIFEST.json against the
pin) and its contents verified (every file against MANIFEST.json) BEFORE the
walk is imported, because importing unverified code to answer a question about
the verified tree would be the complicit-manifest case.

Usage:
  python codegen/generate_schema.py          write the module
  python codegen/generate_schema.py --check  exit 1 if the committed module is stale
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DIST = HERE / "schema-dist"
PIN = HERE / "schema-pin.json"
OUT = HERE.parent / "src" / "onlyworlds" / "_schema.py"

NON_ELEMENT_SCHEMA_FILES = {"base_properties", "world"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_dist() -> dict[str, object]:
    """Authenticate the vendored tree. Returns the pin record. Raises SystemExit on failure."""
    pin: dict[str, object] = json.loads(PIN.read_text(encoding="utf-8"))
    manifest = DIST / "MANIFEST.json"
    got = _sha256(manifest)
    if got != pin["manifest_sha256"]:
        raise SystemExit(
            f"schema-dist MANIFEST.json sha256 {got} != pinned {pin['manifest_sha256']} "
            "(moved tag, or a re-vendor without a re-pin)"
        )
    files: dict[str, str] = json.loads(manifest.read_text(encoding="utf-8"))["files"]
    bad = [f for f, h in sorted(files.items()) if not (DIST / f).is_file() or _sha256(DIST / f) != h]
    if bad:
        raise SystemExit(f"schema-dist files do not match MANIFEST.json: {bad}")
    version = dict(
        line.split(": ", 1) for line in (DIST / "VERSION").read_text(encoding="utf-8").splitlines() if ": " in line
    )
    if version.get("canonical") != pin["canonical_version"] or int(version.get("serial", -1)) != pin["dist_serial"]:
        raise SystemExit(f"schema-dist VERSION {version} disagrees with the pin record")
    return pin


# The walk's kinds -> the wire vocabulary the npm SDK's FIELD_SCHEMA uses.
KIND_NAMES = {"scalar_str": "text", "scalar_int": "integer", "single": "single_link", "multi": "multi_link"}
# Notes the walk is known to emit on this pin. Any OTHER note fails generation
# (rulings.yaml: unknown-field-types-must-be-surfaced): silence is how a newer
# schema meets an older decoder and drops a field.
EXPECTED_NOTES = ("pin.element: `generic-link`", "relation.events: field declared more than once")


def load_walk() -> Any:
    spec = importlib.util.spec_from_file_location("schema_walk", DIST / "walk" / "schema_walk.py")
    assert spec is not None and spec.loader is not None
    walk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(walk)
    return walk


def field_kinds(walk: Any, types: list[str]) -> dict[str, dict[str, str]]:
    """type -> {wire field name: kind}. Base fields by a DECLARED mapping (the SDK's):
    base_properties.yaml names lowercased; `Id` and `World` dropped (identity, and a
    field the API rejects in bodies). The generic link (pin.element) is served as
    the pair element_type (text) + element_id (single_link), as the SDK emits it."""
    schema = DIST / "schema"
    base_doc = walk.load_yaml(schema, "base_properties")
    base = {
        name.lower(): "text"
        for name, spec in base_doc["properties"].items()
        if name.lower() not in ("id", "world") and spec.get("type") == "string"
    }
    notes: list[str] = []
    out: dict[str, dict[str, str]] = {}
    for t in types:
        kinds = dict(base)
        for f in walk.flatten_fields(walk.load_yaml(schema, t), t, note=notes.append):
            if f["kind"] == "generic":
                kinds[f"{f['name']}_type"] = "text"
                kinds[f"{f['name']}_id"] = "single_link"
            elif f["kind"] in KIND_NAMES:
                kinds[f["name"]] = KIND_NAMES[f["kind"]]
            else:
                raise SystemExit(f"{t}.{f['name']}: unknown kind {f['kind']!r} from the walk")
        out[t] = kinds
    unexpected = [n for n in notes if not n.startswith(EXPECTED_NOTES)]
    if unexpected:
        raise SystemExit(f"the walk raised notes this generator does not know: {unexpected}")
    return out


def element_types(walk: Any) -> list[str]:
    from_walk: list[str] = list(walk.ELEMENT_TYPES)
    from_files = sorted(p.stem for p in (DIST / "schema").glob("*.yaml") if p.stem not in NON_ELEMENT_SCHEMA_FILES)
    if sorted(from_walk) != from_files or len(set(from_walk)) != len(from_walk):
        raise SystemExit(f"the walk's ELEMENT_TYPES {from_walk} disagree with the dist's schema files {from_files}")
    return from_walk


def render(pin: dict[str, object], types: list[str], kinds: dict[str, dict[str, str]]) -> str:
    lines = [
        "# GENERATED by codegen/generate_schema.py from the vendored schema distribution. Do not hand-edit.",
        "# Regenerate: python codegen/generate_schema.py  (CI/test: --check)",
        f"# Source: {pin['repo']} @ {pin['tag']} ({pin['commit']})",
        "",
        '"""Schema provenance and the 22 element types, generated from the pinned schema distribution."""',
        "",
        f'SCHEMA_DIST_TAG = "{pin["tag"]}"',
        f'SCHEMA_VERSION = "{pin["canonical_version"]}"',
        f"SCHEMA_DIST_SERIAL = {pin['dist_serial']}",
        f'SCHEMA_MANIFEST_SHA256 = "{pin["manifest_sha256"]}"',
        "",
        "# Canonical order, as the walk declares it.",
        "ELEMENT_TYPES: tuple[str, ...] = (",
        *[f'    "{t}",' for t in types],
        ")",
        "",
        "# type -> {wire field name: text | integer | single_link | multi_link}. Schema fields only:",
        "# anything else on a body is server-managed, a tool's extension, or unknown.",
        "FIELD_KINDS: dict[str, dict[str, str]] = {",
    ]
    for t in types:
        lines.append(f'    "{t}": {{')
        lines.extend(f'        "{name}": "{kind}",' for name, kind in kinds[t].items())
        lines.append("    },")
    lines += ["}", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    pin = verify_dist()
    walk = load_walk()
    types = element_types(walk)
    text = render(pin, types, field_kinds(walk, types))
    if args.check:
        current = OUT.read_bytes().decode("utf-8") if OUT.is_file() else ""
        if current != text:
            print(f"STALE: {OUT} does not match what the pinned dist generates", file=sys.stderr)
            return 1
        print(f"ok: {OUT.name} matches {pin['tag']}")
        return 0
    OUT.write_bytes(text.encode("utf-8"))  # bytes: LF on every platform
    print(f"wrote {OUT} ({pin['tag']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
