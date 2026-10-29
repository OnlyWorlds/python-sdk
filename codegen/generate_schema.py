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

It also copies the dist's folder checker (walk/lint_folder.py) and schema.json, byte for
byte, into src/onlyworlds/_walk/, which onlyworlds.lint runs; schema.json is first checked
equal to the walk's own decode_schema output.

Usage:
  python codegen/generate_schema.py          write the module and the vendored checker
  python codegen/generate_schema.py --check  exit 1 if either is stale
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

# Importing the walk and the folder lint from the vendored tree would drop `walk/__pycache__/*.pyc` inside
# a hash-verified directory (the npm SDK's generator turns it off for the same reason).
sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
DIST = HERE / "schema-dist"
PIN = HERE / "schema-pin.json"
OUT = HERE.parent / "src" / "onlyworlds" / "_schema.py"
# The dist's own folder checker and the decoded schema it runs on, copied byte for byte into a folder of
# their own (onlyworlds.lint runs them; nothing else sits beside them). Checked with the module.
VENDORED = {
    DIST / "walk" / "lint_folder.py": HERE.parent / "src" / "onlyworlds" / "_walk" / "lint_folder.py",
    DIST / "schema.json": HERE.parent / "src" / "onlyworlds" / "_walk" / "schema.json",
    # the import map profile's table (profiles/import-map.md), read by the LegendKeeper door
    DIST / "profiles" / "import-map.json": HERE.parent / "src" / "onlyworlds" / "_walk" / "import-map.json",
}

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


def public_fields(types: list[str], layout: dict[str, Any]) -> dict[str, list[str]]:
    """type -> the fields the platform shows on a known-of stub beside the base keys, from the dist's
    presentation.json ``types.<type>.public`` (keel's field tag ``public: true``). Every type
    must list one (``[]`` for none), and each name must be one of that type's own schema fields."""
    presentation: dict[str, Any] = json.loads((DIST / "presentation.json").read_text(encoding="utf-8"))
    by_type = presentation.get("types")
    if not isinstance(by_type, dict) or sorted(by_type) != sorted(types):
        raise SystemExit(f"presentation.json types {sorted(by_type or {})} disagree with ELEMENT_TYPES {types}")
    out: dict[str, list[str]] = {}
    for t in types:
        names = by_type[t].get("public")
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
            raise SystemExit(f"presentation.json types.{t}.public is not a list of field names: {names!r}")
        own = {n for _, fields in layout["sections"][t] for n in fields}
        stray = [n for n in names if n not in own]
        if stray or len(set(names)) != len(names):
            raise SystemExit(f"presentation.json types.{t}.public {names}: not {t}'s own fields, or repeated: {stray}")
        out[t] = names
    return out


def presentation_keys(types: list[str]) -> dict[str, tuple[str, str]]:
    """type -> (colour group, icon), the dist's presentation.json ``types.<type>.family`` (the key keeps its
    name; the value is the colour word) and ``.icon``: the first-party presentation defaults a reader hands a
    tool (the graph's nodes carry them). Every type must have both, each a non-empty string, and each colour
    group one of ``colors.order``."""
    presentation: dict[str, Any] = json.loads((DIST / "presentation.json").read_text(encoding="utf-8"))
    by_type = presentation.get("types")
    if not isinstance(by_type, dict) or sorted(by_type) != sorted(types):
        raise SystemExit(f"presentation.json types {sorted(by_type or {})} disagree with ELEMENT_TYPES {types}")
    groups = (presentation.get("colors") or {}).get("order")
    if not isinstance(groups, list) or not groups:
        raise SystemExit(f"presentation.json colors.order is not a list of colour groups: {groups!r}")
    out: dict[str, tuple[str, str]] = {}
    for t in types:
        group, icon = by_type[t].get("family"), by_type[t].get("icon")
        if group not in groups or not isinstance(icon, str) or not icon:
            raise SystemExit(f"presentation.json types.{t}: colour group {group!r} or icon {icon!r} is not one")
        out[t] = (group, icon)
    return out


ROOM_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|")


def room_pairs(types: list[str]) -> list[tuple[str, str]]:
    """The room profile's (type, supertype) pairs (dist serial 44 on, profiles/room.md), the npm SDK's
    ROOM_PAIRS. Emitted from the fixture's ``pairs``, the machine-readable copy, and checked against the
    page's own table: the two must name the same pairs in the same order, or generation fails instead of
    picking one."""
    fixture_path, page_path = DIST / "profiles" / "room.fixture.json", DIST / "profiles" / "room.md"
    fixture: dict[str, Any] = json.loads(fixture_path.read_text(encoding="utf-8"))
    raw = fixture.get("pairs")
    if not isinstance(raw, list) or not raw:
        raise SystemExit(f"{fixture_path}: `pairs` is {raw!r}, expected a list of {{type, supertype}}")
    pairs: list[tuple[str, str]] = []
    for p in raw:
        if not isinstance(p, dict) or set(p) != {"type", "supertype"}:
            raise SystemExit(f"{fixture_path}: a pair is {p!r}, expected {{type, supertype}}")
        t, s = p["type"], p["supertype"]
        if t not in types or not isinstance(s, str) or not s or s != s.strip() or '"' in s or "\\" in s:
            raise SystemExit(f"{fixture_path}: pair {p!r}: not an element type, or a supertype this emitter refuses")
        pairs.append((t, s))
    if len({(t.lower(), s.lower()) for t, s in pairs}) != len(pairs):
        raise SystemExit(f"{fixture_path}: pairs repeat one another without regard to case: {pairs!r}")
    lines = page_path.read_text(encoding="utf-8").splitlines()
    table = [(m[1], m[2]) for m in map(ROOM_ROW.match, lines) if m]
    if table != pairs:
        raise SystemExit(f"the room profile's two copies disagree: room.md's table {table}, the fixture's {pairs}")
    return pairs


def room_mark() -> str:
    """The room profile's mark (dist serial 45 on): the extension field the parlor writes on every room element
    beside the pair. From the fixture's ``mark.field``; it must sit under the profile's reserved prefix ``x_room_``
    and be named in room.md, or generation fails."""
    fixture: dict[str, Any] = json.loads((DIST / "profiles" / "room.fixture.json").read_text(encoding="utf-8"))
    mark = (fixture.get("mark") or {}).get("field")
    if not isinstance(mark, str) or not re.fullmatch(r"x_room_[a-z0-9_]+", mark):
        raise SystemExit(f"room.fixture.json: mark.field is {mark!r}, expected an extension key under x_room_")
    if f"`{mark}`" not in (DIST / "profiles" / "room.md").read_text(encoding="utf-8"):
        raise SystemExit(f"room.md does not name the fixture's mark `{mark}`")
    return mark


def reading_aids(types: list[str]) -> tuple[list[tuple[str, str]], str]:
    """The reading aids (dist serial 82 on, profiles/lens.md rule 4 and profiles/room.md): the charter, its guide
    and its domains, each a (type, supertype) pair, and the mark that tells one from lore; the npm SDK's
    READING_AID_PAIRS and READING_AID_MARK. Emitted from the lens fixture's ``reading_aid_pairs`` (each word
    ``type/supertype``) and ``reading_aid_mark.field``; each pair and the mark must be named on lens.md, and the
    mark on room.md, or generation fails. No fallback: emitting "no aids" would read every charter as lore."""
    fixture_path = DIST / "profiles" / "lens.fixture.json"
    fixture: dict[str, Any] = json.loads(fixture_path.read_text(encoding="utf-8"))
    raw = fixture.get("reading_aid_pairs")
    if not isinstance(raw, list) or not raw or not all(isinstance(w, str) and w.count("/") == 1 for w in raw):
        raise SystemExit(f"{fixture_path}: `reading_aid_pairs` is {raw!r}, expected a list of 'type/supertype' words")
    pairs: list[tuple[str, str]] = []
    for w in raw:
        t, s = w.split("/")
        if t not in types or not s or s != s.strip() or '"' in s or "\\" in s:
            raise SystemExit(
                f"{fixture_path}: reading aid {w!r}: not an element type, or a supertype this emitter refuses"
            )
        pairs.append((t, s))
    if len({(t.lower(), s.lower()) for t, s in pairs}) != len(pairs):
        raise SystemExit(f"{fixture_path}: reading aid pairs repeat one another without regard to case: {pairs!r}")
    mark = (fixture.get("reading_aid_mark") or {}).get("field")
    if not isinstance(mark, str) or not re.fullmatch(r"x_[a-z0-9_]+", mark):
        raise SystemExit(f"{fixture_path}: reading_aid_mark.field is {mark!r}, expected an extension key")
    page = (DIST / "profiles" / "lens.md").read_text(encoding="utf-8")
    room = (DIST / "profiles" / "room.md").read_text(encoding="utf-8")
    missing = [f"`{w}`" for w in raw if f"`{w}`" not in page] + [
        f"`{mark}`" for t in (page, room) if f"`{mark}`" not in t
    ]
    if missing:
        raise SystemExit(f"the lens and room pages do not name the fixture's reading aids {missing}")
    return pairs, mark


def message_pairs(
    types: list[str], room: list[tuple[str, str]]
) -> tuple[tuple[str, str], tuple[str, str], tuple[str, str]]:
    """The message profile's three pairs (dist serial 72 on, profiles/message.md): the message (``pair``), the
    reader's read mark (``read_mark``) and (serial 76 on) the Note (``note_pair``), each (type, supertype), from
    the fixture. The message's pair must be one of the room profile's (the page: "the pair the room profile
    lists as a line in the room"), and every supertype must be named on the page, or generation fails."""
    fixture_path, page_path = DIST / "profiles" / "message.fixture.json", DIST / "profiles" / "message.md"
    fixture: dict[str, Any] = json.loads(fixture_path.read_text(encoding="utf-8"))
    page = page_path.read_text(encoding="utf-8")
    out: list[tuple[str, str]] = []
    for key in ("pair", "read_mark", "note_pair"):
        p = fixture.get(key)
        if not isinstance(p, dict):
            raise SystemExit(f"{fixture_path}: `{key}` is {p!r}, expected {{type, supertype, ...}}")
        t, s = p.get("type"), p.get("supertype")
        if t not in types or not isinstance(s, str) or not s or s != s.strip() or '"' in s or "\\" in s:
            raise SystemExit(f"{fixture_path}: {key} {p!r}: not an element type, or a supertype this emitter refuses")
        if f"supertype `{s}`" not in page:
            raise SystemExit(f"message.md does not name the fixture's {key} supertype `{s}`")
        out.append((t, s))
    if out[0] not in room:
        raise SystemExit(f"message.fixture.json's pair {out[0]} is not one of the room profile's pairs {room}")
    return out[0], out[1], out[2]


SPINE_ROW = re.compile(r"^\|\s*([A-Z][a-z]+)\s*\|((?:\s*`[^`]+`\s*,?)+)\|\s*$")
SPINE_WORD = re.compile(r"`([^`]+)`")


def spine_kinds(types: list[str]) -> dict[str, list[str]]:
    """The spine profile's kinds (dist serial 55 on, profiles/spine.md): each listed type's closed list of
    supertypes, in the page's order and spelling. The page's table is the only copy (the fixture names no
    list), so it is checked against the fixture's cases instead: every kind a case reads must be on its
    type's list, and every type on the list must be one of the 22, or generation fails."""
    page_path, fixture_path = DIST / "profiles" / "spine.md", DIST / "profiles" / "spine.fixture.json"
    kinds: dict[str, list[str]] = {}
    for line in page_path.read_text(encoding="utf-8").splitlines():
        m = SPINE_ROW.match(line)
        if not m:
            continue
        t, words = m[1].lower(), SPINE_WORD.findall(m[2])
        if t not in types or t in kinds:
            raise SystemExit(f"spine.md: a kinds row for {m[1]!r}, not an element type or named twice")
        if any(not w or w != w.strip() or '"' in w or "\\" in w for w in words):
            raise SystemExit(f"spine.md: {m[1]}'s kinds {words}: a supertype this emitter refuses")
        if len({w.lower() for w in words}) != len(words):
            raise SystemExit(f"spine.md: {m[1]}'s kinds repeat one another without regard to case: {words}")
        kinds[t] = words
    if not kinds:
        raise SystemExit("spine.md: no kinds table found")
    fixture: dict[str, Any] = json.loads(fixture_path.read_text(encoding="utf-8"))
    for case in fixture.get("cases") or []:
        t, kind = case.get("type"), (case.get("read") or {}).get("kind")
        if kind not in ("off-list", "free") and kind not in kinds.get(t, []):
            raise SystemExit(f"spine.fixture.json: case {case.get('name')!r} reads {kind!r}, not on {t}'s list")
    return kinds


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
    public: dict[str, list[str]],
    shown: dict[str, tuple[str, str]],
    room: list[tuple[str, str]],
    mark: str,
    message: tuple[tuple[str, str], tuple[str, str], tuple[str, str]],
    spine: dict[str, list[str]],
    aids: tuple[list[tuple[str, str]], str],
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
        "# type -> the fields the platform shows on a known-of stub (``known_of: true``) beside its name,",
        "# description, supertype, subtype and picture: presentation.json ``types.<type>.public`` (keel's field",
        "# tag). For display; what a stub holds is what the server sent (folder.known_of_for_disk).",
        "PUBLIC_FIELDS: dict[str, tuple[str, ...]] = {",
        *[line for t in types for line in wrapped(f'    "{t}": ', public[t], ",")],
        "}",
        "",
        "# type -> its colour group (the colour word: blue, green, pink or amber) and its icon name:",
        "# presentation.json ``types.<type>.family`` and ``.icon``, the first-party presentation defaults (not the",
        "# standard; a tool may override them). A key for drawing the 22, never a label. Colour stays the tool's.",
        "ELEMENT_GROUPS: dict[str, str] = {",
        *[f'    "{t}": "{shown[t][0]}",' for t in types],
        "}",
        "ELEMENT_ICONS: dict[str, str] = {",
        *[f'    "{t}": "{shown[t][1]}",' for t in types],
        "}",
        "",
        "# Prefixes of the extension keys a tool may add to any element (dist walk/lint_folder.py).",
        f"EXTENSION_PREFIXES: tuple[str, ...] = {strs(list(prefixes))}",
        "",
        "# The room profile (profiles/room.md): the (type, supertype) pairs a parlor puts in a world, each",
        "# matched trimmed and without regard to case, together with the mark ROOM_MARK (room.is_room_element).",
        "# From room.fixture.json's pairs, checked against the page's table. A convention on the 22 types.",
        "ROOM_PAIRS: tuple[tuple[str, str], ...] = (",
        *[f'    ("{t}", "{s}"),' for t, s in room],
        ")",
        "",
        "# The room profile's mark: the extension field the parlor writes on every room element, the id of the",
        "# world or sitting the room belongs to (room.fixture.json's mark.field, checked against room.md).",
        f'ROOM_MARK = "{mark}"',
        "",
        "# The reading aids (profiles/lens.md rule 4, profiles/room.md): the charter, its guide and its domains, each",
        "# matched by its (type, supertype) pair, trimmed and without regard to case as ROOM_PAIRS, AND the mark",
        "# READING_AID_MARK, the id of the world the aid belongs to (room.is_charter_element). From",
        "# lens.fixture.json's reading_aid_pairs, as it writes them, and reading_aid_mark, checked against the pages.",
        "READING_AID_PAIRS: tuple[tuple[str, str], ...] = (",
        *[f'    ("{t}", "{s}"),' for t, s in aids[0]],
        ")",
        f'READING_AID_MARK = "{aids[1]}"',
        "",
        "# The message profile (profiles/message.md): the (type, supertype) pair of a message between a world's",
        "# members, and of a reader's read mark, each matched trimmed and without regard to case as ROOM_PAIRS",
        "# (message.is_message, message.read_mark_of). From message.fixture.json's pair and read_mark.",
        f'MESSAGE_PAIR: tuple[str, str] = ("{message[0][0]}", "{message[0][1]}")',
        f'READ_MARK_PAIR: tuple[str, str] = ("{message[1][0]}", "{message[1][1]}")',
        "# The Note (message.is_note, message.note_of): a member's own line in the world, never a message. From",
        "# message.fixture.json's note_pair, matched as MESSAGE_PAIR is.",
        f'NOTE_PAIR: tuple[str, str] = ("{message[2][0]}", "{message[2][1]}")',
        "",
        "# The spine profile (profiles/spine.md): each listed type's closed list of supertypes (its kinds), in",
        "# the page's order and spelling, compared trimmed and without regard to case (spine.read_spine_element).",
        "# From the page's table, checked against spine.fixture.json's cases. A convention on the 22 types.",
        "SPINE_KINDS: dict[str, tuple[str, ...]] = {",
        *[line for t, words in spine.items() for line in wrapped(f'    "{t}": ', words, ",")],
        "}",
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
    decoded = decoded_schema(walk)
    if json.loads((DIST / "schema.json").read_text(encoding="utf-8")) != decoded:
        raise SystemExit(
            "the dist's schema.json is not the walk's decode_schema output: onlyworlds.lint would run on another schema"
        )
    layout = layout_tables(decoded, types, kinds, pairs)
    room = room_pairs(types)
    text = render(
        pin,
        types,
        kinds,
        pairs,
        layout,
        extension_prefixes(),
        public_fields(types, layout),
        presentation_keys(types),
        room,
        room_mark(),
        message_pairs(types, room),
        spine_kinds(types),
        reading_aids(types),
    )
    if args.check:
        current = OUT.read_bytes().decode("utf-8") if OUT.is_file() else ""
        stale = [OUT] if current != text else []
        stale += [dst for src, dst in VENDORED.items() if not dst.is_file() or dst.read_bytes() != src.read_bytes()]
        for path in stale:
            print(f"STALE: {path} does not match what the pinned dist generates", file=sys.stderr)
        if stale:
            return 1
        print(f"ok: {OUT.name} and the vendored checker match {pin['tag']}")
        return 0
    OUT.write_bytes(text.encode("utf-8"))  # bytes: LF on every platform
    for src, dst in VENDORED.items():
        dst.parent.mkdir(exist_ok=True)
        dst.write_bytes(src.read_bytes())
    print(f"wrote {OUT} and the vendored checker ({pin['tag']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
