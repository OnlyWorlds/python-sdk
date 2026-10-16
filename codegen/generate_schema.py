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


def generic_pairs(walk: Any, types: list[str]) -> dict[str, list[tuple[str, str]]]:
    """type -> [(type column, id column)] for each generic link: keel refuses a write that sets one half."""
    schema = DIST / "schema"
    out: dict[str, list[tuple[str, str]]] = {}
    for t in types:
        pairs = [
            (f"{f['name']}_type", f"{f['name']}_id")
            for f in walk.flatten_fields(walk.load_yaml(schema, t), t, note=lambda _n: None)
            if f["kind"] == "generic"
        ]
        if pairs:
            out[t] = pairs
    return out


def decoded_schema(walk: Any) -> dict[str, Any]:
    """The walk's decode_schema (the shape schema.json ships), with the same notes policy as field_kinds."""
    notes: list[str] = []
    decoded: dict[str, Any] = walk.decode_schema(DIST / "schema", note=notes.append)
    unexpected = [n for n in notes if not n.startswith(EXPECTED_NOTES)]
    if unexpected:
        raise SystemExit(f"the walk raised notes this generator does not know: {unexpected}")
    return decoded


def layout_tables(
    decoded: dict[str, Any],
    types: list[str],
    kinds: dict[str, dict[str, str]],
    pairs: dict[str, list[tuple[str, str]]],
) -> dict[str, Any]:
    """What a reader of whole elements needs beyond FIELD_KINDS: the base and World field names in
    order, each type's fields under their YAML groups, each link's target, each generic link's two
    keys. Cross-checked against FIELD_KINDS and GENERIC_PAIRS, so the tables cannot drift apart."""
    sections: dict[str, list[tuple[str, list[str]]]] = {}
    targets: dict[str, dict[str, str]] = {}
    generic: dict[str, dict[str, tuple[str, str]]] = {}
    for t in types:
        groups: list[tuple[str, list[str]]] = []
        for f in decoded["types"][t]:
            if not groups or groups[-1][0] != f["section"]:
                groups.append((f["section"], []))
            groups[-1][1].append(f["name"])
            if f["kind"] in ("single", "multi"):
                if not f.get("target"):
                    raise SystemExit(f"{t}.{f['name']}: a link with no target from the walk")
                targets.setdefault(t, {})[f["name"]] = f["target"]
            elif f["kind"] == "generic":
                generic.setdefault(t, {})[f["name"]] = (f["type_key"], f["id_key"])
            if f["kind"] != "generic" and f["name"] not in kinds[t]:
                raise SystemExit(f"{t}.{f['name']}: in the walk's sections but not in FIELD_KINDS")
        if len({s for s, _ in groups}) != len(groups):
            raise SystemExit(f"{t}: a section split in two by the walk's order")
        sections[t] = groups
        if sorted(generic.get(t, {}).values()) != sorted(pairs.get(t, [])):
            raise SystemExit(
                f"{t}: the walk's generic keys {generic.get(t)} disagree with GENERIC_PAIRS {pairs.get(t)}"
            )
    return {
        "base": [f["name"] for f in decoded["base"]],
        "world": [f["name"] for f in decoded["world"]],
        "sections": sections,
        "targets": targets,
        "generic": generic,
    }


def extension_prefixes() -> tuple[str, ...]:
    """The extension prefixes as the dist's own folder lint declares them (ruling extension-passthrough)."""
    spec = importlib.util.spec_from_file_location("lint_folder", DIST / "walk" / "lint_folder.py")
    assert spec is not None and spec.loader is not None
    lint = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lint)
    prefixes = tuple(lint.EXTENSION_PREFIXES)
    if not prefixes or not all(isinstance(p, str) and p.endswith("_") for p in prefixes):
        raise SystemExit(f"lint_folder.EXTENSION_PREFIXES is not a tuple of prefixes: {prefixes!r}")
    return prefixes


def element_types(walk: Any) -> list[str]:
    from_walk: list[str] = list(walk.ELEMENT_TYPES)
    from_files = sorted(p.stem for p in (DIST / "schema").glob("*.yaml") if p.stem not in NON_ELEMENT_SCHEMA_FILES)
    if sorted(from_walk) != from_files or len(set(from_walk)) != len(from_walk):
        raise SystemExit(f"the walk's ELEMENT_TYPES {from_walk} disagree with the dist's schema files {from_files}")
    return from_walk


def render(
    pin: dict[str, object],
    types: list[str],
    kinds: dict[str, dict[str, str]],
    pairs: dict[str, list[tuple[str, str]]],
    layout: dict[str, Any],
    prefixes: tuple[str, ...],
) -> str:
    def strs(names: list[str]) -> str:
        return "(" + ", ".join(f'"{n}"' for n in names) + ("," if len(names) == 1 else "") + ")"

    def wrapped(head: str, names: list[str], tail: str) -> list[str]:
        """``head(names)tail`` on one line, or the names packed onto lines within ruff's 120."""
        if len(head + strs(names) + tail) <= 120:
            return [head + strs(names) + tail]
        indent = " " * (len(head) - len(head.lstrip()))
        out, cur = [head + "("], ""
        for piece in (f'"{n}",' for n in names):
            if cur and len(indent) + 4 + len(cur) + 1 + len(piece) > 120:
                out.append(indent + "    " + cur)
                cur = ""
            cur = f"{cur} {piece}" if cur else piece
        return [*out, indent + "    " + cur, indent + ")" + tail]

    lines = [
        "# GENERATED by codegen/generate_schema.py from the vendored schema distribution. Do not hand-edit.",
        "# Regenerate: python codegen/generate_schema.py  (CI/test: --check)",
        f"# Source: {pin['repo']} @ {pin['tag']} ({pin['commit']})",
        "",
        '"""Schema provenance, the 22 element types and their fields, from the pinned schema distribution."""',
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
    lines += [
        "}",
        "",
        "# type -> ((type column, id column), ...): each generic link's two halves. A write sets both or neither.",
        "GENERIC_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {",
        *[f'    "{t}": ({", ".join(f'("{a}", "{b}")' for a, b in pairs[t])},),' for t in types if t in pairs],
        "}",
        "",
        "# Every element's shared fields (base_properties.yaml), in schema order, as data spells them.",
        *wrapped("BASE_FIELDS: tuple[str, ...] = ", layout["base"], ""),
        "",
        "# The World's fields (world.yaml), in schema order.",
        *wrapped("WORLD_FIELDS: tuple[str, ...] = ", layout["world"], ""),
        "",
        "# type -> ((section, (field, ...)), ...): each type's own fields in schema order, under the YAML",
        "# group that holds them. A generic link is listed by its own name (pin's `element`); GENERIC_LINKS",
        "# names the two keys that hold it in data.",
        "SECTIONS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {",
    ]
    for t in types:
        lines.append(f'    "{t}": (')
        for s, names in layout["sections"][t]:
            lines.extend(wrapped(f'        ("{s}", ', names, "),"))
        lines.append("    ),")
    lines += [
        "}",
        "",
        "# type -> {link field: the type it links to}, for every single and multi link.",
        "LINK_TARGETS: dict[str, dict[str, str]] = {",
    ]
    for t in types:
        if t in layout["targets"]:
            lines.append(f'    "{t}": {{')
            lines.extend(f'        "{name}": "{target}",' for name, target in layout["targets"][t].items())
            lines.append("    },")
    lines += [
        "}",
        "",
        "# type -> {generic link field: (type key, id key)}: the walk's names for the two keys that hold it.",
        "GENERIC_LINKS: dict[str, dict[str, tuple[str, str]]] = {",
        *[
            f'    "{t}": {{{", ".join(f'"{n}": ("{a}", "{b}")' for n, (a, b) in layout["generic"][t].items())}}},'
            for t in types
            if t in layout["generic"]
        ],
        "}",
        "",
        "# Prefixes of the extension keys a tool may add to any element (dist walk/lint_folder.py).",
        f"EXTENSION_PREFIXES: tuple[str, ...] = {strs(list(prefixes))}",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    pin = verify_dist()
    walk = load_walk()
    types = element_types(walk)
    kinds, pairs = field_kinds(walk, types), generic_pairs(walk, types)
    layout = layout_tables(decoded_schema(walk), types, kinds, pairs)
    text = render(pin, types, kinds, pairs, layout, extension_prefixes())
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
