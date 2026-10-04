#!/usr/bin/env python3
"""The OnlyWorlds schema walk — THE official reader of the schema YAMLs.

Extracted 2026-07-28 from generate_models.py (Skeld) so that one walk serves
every consumer: keel's Django emitter, the npm SDK's TypeScript emitter, the
Unity SDK's C# emitter, and schema-dist (which publishes this file). Twelve
programs have needed to know what the schema *means*; ten stale copies were
deleted on 2026-07-28. This module is the one decoder. Do not copy it — import
it, or vendor it via schema-dist and verify against MANIFEST.json.

The walk is wrapper-agnostic: it reads `properties:` (canonical semantics) and
ignores presentation keys (`family`, `icon`), which live in presentation.json.
Pointing it at a plain canonical checkout gives correct answers.

Semantic rulings that emitters must honor live in rulings.yaml beside this
file — data, not prose, so three languages inherit one convention instead of
re-deriving it (see the collective.equipment drift, 2026-07-23).

Field spec shape returned by flatten_fields():
    {name, kind, target?, required?}   kind in
    {scalar_str, scalar_int, single, multi, generic}
`required` is only present when include_required=True (opt-in so existing
emitters' output stays byte-identical until they choose to read it).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import yaml

# The 22 element types. world.yaml is the world container (hand-built model, flat
# schema shape) and base_properties.yaml supplies the shared header — neither is a
# generated element type.
ELEMENT_TYPES = [
    "ability", "collective", "character", "construct", "creature", "event",
    "family", "institution", "language", "law", "location", "map", "marker",
    "narrative", "object", "phenomenon", "pin", "relation", "species", "title",
    "trait", "zone",
]

# category (YAML link target, singular TitleCase) → the type slug used everywhere
# else. Just a lowercase, but kept explicit so an odd category surfaces loudly.
KNOWN_CATEGORIES = {t.capitalize(): t for t in ELEMENT_TYPES}
KNOWN_CATEGORIES["World"] = "world"

# Presentation wrapper keys (keel-only, never canonical). The walk ignores them;
# publish_dist.py strips them into presentation.json.
WRAPPER_KEYS = ("family", "icon")


def _noop(msg: str) -> None:  # default note sink — emitters pass their own
    return None


def load_yaml(schema_dir: Path, name: str) -> dict:
    with open(Path(schema_dir) / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def required_names(doc: dict) -> set[str]:
    """Union of every `required:` list in the document — top-level (the
    base_properties shape) and per-group (the pin/marker shape). Names are
    returned as written in the YAML; callers compare against field names,
    which are lowercase in the grouped element files."""
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
    """Walk the grouped YAML (Constitution/Origins/... → properties → fields) and
    return a flat, ordered list of field specs. Each spec:
        {name, kind, target?}  where kind in
        {scalar_str, scalar_int, single, multi, generic}

    Opt-in extras, all defaulting OFF so existing emitters get byte-identical
    output (the same shape as include_required):
      include_desc     — adds `desc` from the YAML's description, when present.
                         353 of 355 fields carry one; they are the source of the
                         SDK's JSDoc and of SCHEMA.md, the package's AI-legibility
                         artifact. Requested by Kael 2026-07-28: without this the
                         one-decoder rule would have forced him to either delete
                         ~365 JSDoc lines or run a second parser over the same
                         YAML, i.e. re-create the copy we just deleted ten of.
      include_sections — adds `section`, the YAML group a field came from
                         (Constitution, Origins, ...). Same rationale: the SDK
                         exports ELEMENT_SECTIONS and gates it with tests.
    """
    fields: list[dict] = []
    props = doc.get("properties", {})
    for group_name, group in props.items():
        group_props = group.get("properties")
        if group_props is None:
            # A property sitting directly at top level (not inside a group object).
            # None of the 22 element YAMLs do this, but handle it rather than drop.
            note(
                f"{type_slug}: top-level property `{group_name}` outside a group "
                f"object — parsed directly."
            )
            _collect_field(group_name, group, type_slug, fields, note,
                           include_desc, group_name if include_sections else None)
            continue
        for fname, fspec in group_props.items():
            _collect_field(fname, fspec, type_slug, fields, note,
                           include_desc, group_name if include_sections else None)

    # Dedupe by field name (keep first). relation.yaml declares `events` in BOTH
    # the Nature and Involves groups — a YAML irregularity. A field maps to one
    # column; a duplicate would produce two identical columns + a colliding index.
    seen: set[str] = set()
    deduped: list[dict] = []
    for f in fields:
        if f["name"] in seen:
            note(
                f"{type_slug}.{f['name']}: field declared more than once across "
                f"groups (YAML irregularity) — kept first, dropped duplicate."
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
        # pin.element only. ContentType + UUID in production; the spike stores the
        # UUID plus a type discriminator, both opaque UUIDField/CharField.
        note(
            f"{type_slug}.{fname}: `generic-link` (link to any element type). "
            f"Emitted as element_id UUIDField + element_type CharField pair; the "
            f"target is resolved at the application layer, not a fixed category."
        )
        out.append({"name": fname, "kind": "generic"})
    elif ftype == "array":
        # world.yaml only (time_format_*). Not an element type — should never hit.
        note(f"{type_slug}.{fname}: unexpected `array` scalar — skipped.")
    else:
        # ⚑ THE SILENT-DROP PATH (Kael, 2026-07-28): the default sink is _noop, so
        # a VENDORED older walk meeting a NEWER schema drops the new field with no
        # signal at all — the failure that does not fail loudly, which is the shape
        # of every bug this week. A consumer pinning an old dist and never passing
        # `note` is exactly the case. The walk cannot decide the policy (an emitter
        # mid-migration may legitimately want to continue), so it stays a note —
        # but the README now tells vendors to pass a sink, and rulings.yaml carries
        # the row. Raising here unilaterally would break emitters on a schema bump,
        # which trades a silent failure for a hard one at the worst moment.
        note(f"{type_slug}.{fname}: unknown YAML type `{ftype}` — skipped.")
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
        note(f"{type_slug}.{fname}: link with no `category` — target unresolved.")
        return None
    slug = KNOWN_CATEGORIES.get(cat)
    if slug is None:
        note(f"{type_slug}.{fname}: link category `{cat}` not a known element type.")
        return cat.lower()

    # collective.equipment drift RESOLVED 2026-07: v1 (which implemented Construct)
    # is decommissioned; keel is production and serves per YAML (Object), settled
    # by dump data (1 row). Special-case warnings removed 2026-07-23.
    return slug
