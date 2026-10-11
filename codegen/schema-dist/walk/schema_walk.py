#!/usr/bin/env python3
"""The OnlyWorlds schema walk: the reference decoder of the schema YAMLs.

One walk serves every program that needs to know what the schema means: the
platform's own model generator, the TypeScript, Unity and Python SDKs, and
schema-dist, which publishes this file. Do not fork it. Import it, or vendor it
from schema-dist and verify it against MANIFEST.json; if you need something it
does not return, ask for it upstream.

The walk reads `properties:` and ignores the presentation keys (`family`,
`icon`), which schema-dist publishes in presentation.json. A plain checkout of
the standard (github.com/OnlyWorlds/OnlyWorlds, `schema/`) decodes the same.

Rulings the YAML cannot carry (nullability, empty strings, extension fields)
live in rulings.yaml beside this file, as data, so every language follows one
convention.

Two ways in:
    flatten_fields(doc, slug, note=print)  -> one type's fields, in order
    decode_schema(schema_dir, note=print)  -> the whole schema: base fields,
                                              the 22 types, the World
From a shell, `python schema_walk.py <schema_dir>` prints decode_schema's
result as JSON: the same bytes schema-dist ships as schema.json.

A field spec from flatten_fields:
    {name, kind, target?}   kind in {scalar_str, scalar_int, single, multi, generic}
plus `required`, `desc` and `section` when asked for (all opt-in, so existing
callers get the same output).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable

import yaml

# The 22 element types. world.yaml (the world container, a flat shape) and
# base_properties.yaml (the fields every element shares) are not element types.
ELEMENT_TYPES = [
    "ability", "collective", "character", "construct", "creature", "event",
    "family", "institution", "language", "law", "location", "map", "marker",
    "narrative", "object", "phenomenon", "pin", "relation", "species", "title",
    "trait", "zone",
]

# A link's `category:` (singular TitleCase) -> the type slug used everywhere
# else. Just a lowercase, kept explicit so an unknown category is reported.
KNOWN_CATEGORIES = {t.capitalize(): t for t in ELEMENT_TYPES}
KNOWN_CATEGORIES["World"] = "world"

# Presentation keys some copies of the YAML carry at top level. The walk
# ignores them; schema-dist strips them out into presentation.json.
WRAPPER_KEYS = ("family", "icon")

# What each kind means in element data (on the wire and in a world folder).
# Shipped inside schema.json so a reader of the JSON needs nothing else.
KINDS = {
    "scalar_str": "a string; the empty string means unset",
    "scalar_int": "an integer, or null for unset",
    "single": "one element's id (a UUID string), or null; `target` names its type",
    "multi": "an array of element ids (UUID strings), possibly empty; `target` names their type",
    "generic": "a link to an element of any type, carried as two keys: "
               "`type_key` holds the type's slug, `id_key` the element's id; "
               "both set or both null",
    "list": "an array; `items` gives the kind of each entry (World fields only)",
}


def _noop(msg: str) -> None:  # default note sink; pass your own
    return None


def load_yaml(schema_dir: Path, name: str) -> dict:
    with open(Path(schema_dir) / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def required_names(doc: dict) -> set[str]:
    """Union of every `required:` list in the document, top-level and
    per-group. Names are returned as written in the YAML."""
    req: set[str] = set()
    for r in doc.get("required", []) or []:
        req.add(r)
    for group in (doc.get("properties") or {}).values():
        if isinstance(group, dict):
            for r in group.get("required", []) or []:
                req.add(r)
    return req


def flatten_fields(
    doc: dict,
    type_slug: str,
    note: Callable[[str], None] = _noop,
    include_required: bool = False,
    include_desc: bool = False,
    include_sections: bool = False,
) -> list[dict]:
    """Walk one element type's grouped YAML (sections -> properties -> fields)
    and return its fields as a flat, ordered list of specs:
        {name, kind, target?}  where kind in
        {scalar_str, scalar_int, single, multi, generic}

    Opt-in extras, all off by default:
      include_required -- adds `required` (bool).
      include_desc     -- adds `desc`, the YAML's description, when present.
      include_sections -- adds `section`, the YAML group the field sits in
                          (Constitution, Origins, ...).
    """
    fields: list[dict] = []
    props = doc.get("properties", {})
    for group_name, group in props.items():
        group_props = group.get("properties")
        if group_props is None:
            # A property directly at top level, not inside a group. No element
            # type does this (base_properties.yaml does; decode_schema reads it
            # with _flat_fields instead). Parsed rather than dropped.
            note(
                f"{type_slug}: top-level property `{group_name}` outside a group "
                f"object, parsed directly."
            )
            _collect_field(group_name, group, type_slug, fields, note,
                           include_desc, group_name if include_sections else None)
            continue
        for fname, fspec in group_props.items():
            _collect_field(fname, fspec, type_slug, fields, note,
                           include_desc, group_name if include_sections else None)

    # A field declared in two groups is kept once (the first). A body has one
    # key per name, so a duplicate would be two specs for one key.
    seen: set[str] = set()
    deduped: list[dict] = []
    for f in fields:
        if f["name"] in seen:
            note(
                f"{type_slug}.{f['name']}: field declared more than once across "
                f"groups; kept the first, dropped the duplicate."
            )
            continue
        seen.add(f["name"])
        deduped.append(f)

    if include_required:
        req = required_names(doc)
        for f in deduped:
            f["required"] = f["name"] in req
    return deduped


def _collect_field(
    fname: str,
    fspec: dict,
    type_slug: str,
    out: list[dict],
    note: Callable[[str], None] = _noop,
    include_desc: bool = False,
    section: str | None = None,
) -> None:
    n = len(out)

    def _decorate() -> None:
        """Attach the opt-in extras to whatever this call just appended."""
        for spec in out[n:]:
            if include_desc:
                desc = fspec.get("description")
                if desc is not None:
                    spec["desc"] = desc
            if section is not None:
                spec["section"] = section

    ftype = fspec.get("type")
    if ftype == "string":
        out.append({"name": fname, "kind": "scalar_str"})
    elif ftype == "integer":
        out.append({"name": fname, "kind": "scalar_int"})
    elif ftype == "single-link":
        target = _resolve_target(fname, fspec, type_slug, note)
        out.append({"name": fname, "kind": "single", "target": target})
    elif ftype == "multi-link":
        target = _resolve_target(fname, fspec, type_slug, note)
        out.append({"name": fname, "kind": "multi", "target": target})
    elif ftype == "generic-link":
        # pin.element is the only one.
        type_key = fspec.get("content_type_field_name", "element_type")
        id_key = fspec.get("object_id_field_name", "element_id")
        note(
            f"{type_slug}.{fname}: `generic-link`, a link to an element of any "
            f"type. In data it is two keys, not `{fname}`: `{type_key}` (the "
            f"type's slug, such as \"character\") and `{id_key}` (the element's "
            f"UUID), both set or both null."
        )
        out.append({"name": fname, "kind": "generic"})
    elif ftype == "array":
        # Only world.yaml has arrays, and it is not an element type.
        note(f"{type_slug}.{fname}: unexpected `array` field, skipped.")
    else:
        # The default sink is a no-op, so a vendored older walk meeting a newer
        # schema would drop the new field in silence. The walk cannot choose
        # the policy for every caller (one mid-migration may want to carry on),
        # so it reports and skips; callers pass a sink and decide. See the
        # `unknown-field-types-must-be-surfaced` row in rulings.yaml.
        note(f"{type_slug}.{fname}: unknown YAML type `{ftype}`, skipped.")
        return

    _decorate()


def _resolve_target(
    fname: str,
    fspec: dict,
    type_slug: str,
    note: Callable[[str], None] = _noop,
) -> str | None:
    cat = fspec.get("category")
    if cat is None:
        note(f"{type_slug}.{fname}: link with no `category`, target unresolved.")
        return None
    slug = KNOWN_CATEGORIES.get(cat)
    if slug is None:
        note(f"{type_slug}.{fname}: link category `{cat}` is not a known element type.")
        return cat.lower()
    return slug


_SCALAR_KINDS = {"string": "scalar_str", "integer": "scalar_int"}


def _flat_fields(
    doc: dict,
    owner: str,
    note: Callable[[str], None],
    lowercase: bool,
) -> list[dict]:
    """The flat shape (base_properties.yaml, world.yaml): properties directly
    under `properties:`, no groups, no links."""
    req = {r.lower() if lowercase else r for r in doc.get("required", []) or []}
    out: list[dict] = []
    for raw_name, fspec in (doc.get("properties") or {}).items():
        name = raw_name.lower() if lowercase else raw_name
        ftype = fspec.get("type")
        if ftype in _SCALAR_KINDS:
            spec: dict = {"name": name, "kind": _SCALAR_KINDS[ftype]}
        elif ftype == "array":
            item_type = (fspec.get("items") or {}).get("type")
            if item_type not in _SCALAR_KINDS:
                note(f"{owner}.{name}: array of `{item_type}`, skipped.")
                continue
            spec = {"name": name, "kind": "list", "items": _SCALAR_KINDS[item_type]}
        else:
            note(f"{owner}.{name}: unknown YAML type `{ftype}`, skipped.")
            continue
        spec["required"] = name in req
        if fspec.get("description") is not None:
            spec["desc"] = fspec["description"]
        out.append(spec)
    return out


def decode_schema(
    schema_dir: str | Path,
    note: Callable[[str], None] = _noop,
) -> dict:
    """The whole schema, decoded: what schema-dist ships as schema.json.

        {"kinds": {kind: meaning},
         "base":  [field, ...],          every element's shared fields
         "types": {slug: [field, ...]},  each type's own fields, in YAML order
         "world": [field, ...]}          the World's fields

    Field names are the keys used in element data (on the wire and in a world
    folder). base_properties.yaml capitalises its names (`Id`, `Image_URL`);
    data spells them in lowercase (`id`, `image_url`), so `base` gives them in
    lowercase. Every field carries `required`, and `desc` when the YAML has a
    description; type fields carry `section`; a generic link carries
    `type_key` and `id_key`, the two keys that hold it in data.
    """
    schema_dir = Path(schema_dir)
    base = _flat_fields(load_yaml(schema_dir, "base_properties"),
                        "base_properties", note, lowercase=True)
    types: dict[str, list[dict]] = {}
    for slug in ELEMENT_TYPES:
        doc = load_yaml(schema_dir, slug)
        fields = flatten_fields(doc, slug, note, include_required=True,
                                include_desc=True, include_sections=True)
        for f in fields:
            if f["kind"] == "generic":
                fspec = doc["properties"][f["section"]]["properties"][f["name"]]
                f["type_key"] = fspec.get("content_type_field_name", "element_type")
                f["id_key"] = fspec.get("object_id_field_name", "element_id")
        types[slug] = fields
    world = _flat_fields(load_yaml(schema_dir, "world"), "world", note,
                         lowercase=False)
    return {"kinds": dict(KINDS), "base": base, "types": types, "world": world}


def dumps_schema(decoded: dict) -> str:
    """decode_schema's result as JSON text, exactly as schema.json is written:
    two-space indent, ASCII-escaped, LF, one trailing newline."""
    return json.dumps(decoded, indent=2, ensure_ascii=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        print("usage: python schema_walk.py <schema_dir>   "
              "(prints the decoded schema as JSON; notes go to stderr)")
        return 2

    def to_stderr(msg: str) -> None:
        print(msg, file=sys.stderr)

    text = dumps_schema(decode_schema(argv[0], note=to_stderr))
    sys.stdout.buffer.write(text.encode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
