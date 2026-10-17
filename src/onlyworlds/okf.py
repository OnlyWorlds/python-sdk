"""Export a world folder to an Open Knowledge Format bundle.

    python -m onlyworlds.okf PATH/TO/WORLD-FOLDER OUT-DIR

or ``export_okf(folder, out_dir)``. Needs PyYAML: ``pip install "onlyworlds[okf]"``.

Writes OUT-DIR (which must not exist yet) as a bundle in Google Cloud's Open
Knowledge Format (OKF) v0.2, as specified at one pinned commit:

    repo:   https://github.com/GoogleCloudPlatform/open-knowledge-format
    commit: ad30107c31c06aec8a7d5636e0d1058118604e6f  (SPEC.md "Version 0.2",
            2026-08-21, the ISO 8601 timestamp edit)

The bundle:

    index.md                       root index; frontmatter `okf_version: "0.2"`
    world.md                       the World as a concept (`type: OnlyWorlds
                                   World`), carrying the bundle metadata
    <type>/index.md                one per element type present
    <type>/<name-slug>--<id tail>.md   one concept per element

Each element concept:
  - `type` is the OnlyWorlds type, qualified as OKF's own examples qualify
    theirs (`BigQuery Table`): `OnlyWorlds Character`. `title` is the element's
    name, `description` its description. Never `verified`: an export confirms
    nothing.
  - `generated.by` is this exporter, a machine actor, and `generated.at` the
    element's `updated_at`. OKF §7 asks for a `human:` actor on hand-authored
    content; the words are the world's authors', but the bundle names no
    author (the folder does not say who wrote what) and these files are
    generated, so the machine actor is the true one. Consumers therefore read
    the bundle as unverified (§5.3).
  - scalar fields sit in the frontmatter under their OnlyWorlds names: `id`,
    `supertype`, `subtype`, `image_url` and every integer field. A field
    whose name OKF defines (§4.1, §5, §10: `status` and the like) would be
    written as `ow_<name>`; no frontmatter field needs it today.
  - every link field is in the frontmatter, keyed by its OnlyWorlds field
    name, as bundle-absolute paths (`location: /location/barovia--1a2b3c4d.md`,
    a list for a multi link; `element` for a pin's generic link), so the kind
    of each link survives as a key although OKF links are untyped (§6.1).
    A link to an id the folder does not hold is written `urn:uuid:<id>`.
  - the body holds the type's own text fields under `# <Section>` /
    `## <Field>` headings in schema order, and every link again as a markdown
    link in a bullet (`- **location**: [Barovia](../location/....md)`), so
    viewers that draw the link graph from bodies draw it. Body links are
    relative: the reference viewer at the pinned commit skips `/` links. A
    text line markdown would read as a heading (`#`, or a `===`/`---`
    underline) is escaped with a backslash, so text cannot make a section.
  - unset values (the empty string, null, an empty list) are left out.
    Extension keys (`x_`, `atlas_`, `shadow_`) are carried as they are; the
    server and folder keys the package never pushes (``push.NOT_SENT``) are
    not, except `updated_at` as `generated.at`.

world.md carries the World's schema fields (`time_current` read from
`time_range_current` when only that spelling is present, folder format §5),
its extension keys, `owner_character` (as a link), `format_version`,
`writable` and every `snapshot_*` key. The `api` block is dropped: it is a
credential and a sync switch, not world content (folder format §4.1, the
portable copy).

Nothing is dropped in silence. Each of these is a note (on stderr from the
command line, in ``OkfReport.notes`` from Python): a file the folder reader
skipped (not JSON, not an object, no `id`, a dot-prefixed file: a tool's litter,
not an element, as the folder spec clarifies), a directory that is not a
type directory, an id in both `elements/` and the legacy `spatial/` (the
`elements/` copy is served, folder format v0.3.8), a key that is not a field
of its type, a field kind this exporter does not know, and a link left out
(not an id, a null in a multi link, or an element of the wrong type). A link
to an id the folder does not hold is listed in ``OkfReport.unresolved``.

The folder is read by ``onlyworlds.folder.read_folder``, the package's one
reader; the schema comes from the package's generated tables (``_schema``),
so this module reads no schema YAML.

The output is deterministic: the same folder and the same package give a
byte-identical bundle (UTF-8, LF, no export timestamp). From the command
line: exit 0 written, 1 when world.json cannot be read or one id is in two
files of one layout, 2 on bad arguments (a missing folder, an existing
OUT-DIR).
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError('onlyworlds.okf needs PyYAML: pip install "onlyworlds[okf]"') from exc

from ._schema import (
    BASE_FIELDS,
    ELEMENT_TYPES,
    EXTENSION_PREFIXES,
    FIELD_KINDS,
    GENERIC_LINKS,
    LINK_TARGETS,
    SCHEMA_DIST_SERIAL,
    SCHEMA_VERSION,
    SECTIONS,
    WORLD_FIELDS,
)
from ._version import __version__
from .folder import WIRE_TO_DISK_WORLD_KEYS, WORLD_FILE, Folder, read_folder
from .push import NOT_SENT

__all__ = ["EXPORTER", "OKF_COMMIT", "OKF_VERSION", "FolderError", "OkfReport", "build_bundle", "export_okf", "main"]

EXPORTER = f"onlyworlds-py/{__version__}"
OKF_VERSION = "0.2"
OKF_REPO = "https://github.com/GoogleCloudPlatform/open-knowledge-format"
OKF_COMMIT = "ad30107c31c06aec8a7d5636e0d1058118604e6f"

# Frontmatter keys OKF v0.2 gives a meaning (SPEC §4.1, §5, §10, §12). An
# OnlyWorlds field of the same name is written as `ow_<name>`.
OKF_KEYS = frozenset(
    {
        "type", "title", "description", "resource", "tags", "sources", "usage_window", "generated", "verified",
        "status", "stale_after", "runtime", "parameters", "computation", "executor", "attester", "okf_version",
    }
)  # fmt: skip
# world.json keys the folder format defines beside the schema's (§4.2, §5).
WORLD_FOLDER_KEYS = ("format_version", "writable")
WORLD_DROPPED = ("api", *WIRE_TO_DISK_WORLD_KEYS)
# Every break str.splitlines() honours: the reference parser splits the
# frontmatter on these, so a string holding one is written double-quoted.
LINE_BREAKS = "\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029"

Note = Callable[[str], None]


def _type_name(slug: str) -> str:
    """The OKF `type` of a slug (or the World), qualified: `OnlyWorlds Character`."""
    return f"OnlyWorlds {slug.capitalize()}"


class FolderError(ValueError):
    """The folder cannot be exported: world.json unreadable, or one id in two files of one layout."""


@dataclass
class OkfReport:
    """What an export did. ``notes`` are what it left out or chose, one line each, in order."""

    elements: int = 0
    types: int = 0
    files: int = 0
    links: int = 0
    #: ``<file>: `<field>` -> <id>`` for each link to an id the folder does not hold
    unresolved: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    out: Path | None = None


# --- YAML: block style, line-break-bearing strings double-quoted on one line
# (the breaks escaped), so no frontmatter line can read as the closing `---`.


class _Dumper(yaml.SafeDumper):
    pass


def _str_rep(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    style = '"' if any(c in value for c in LINE_BREAKS) else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _str_rep)


def _frontmatter(data: dict[str, Any]) -> str:
    return str(
        yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, default_flow_style=False, width=1 << 30)
    )


# --- reading the folder: read_folder's report, as notes


def _rel(folder: Folder, path: Path) -> str:
    return path.relative_to(folder.root).as_posix()


def _elements(folder: Folder, note: Note) -> list[tuple[str, dict[str, Any]]]:
    """(type slug, body) for every exportable element, elements/ before spatial/, type order, path order.
    What read_folder skipped or set aside is noted here; a duplicate id in one layout is an error."""
    for s in folder.skipped:
        if s.path.parent == folder.root and s.path.name == WORLD_FILE:
            continue
        note(f"{_rel(folder, s.path)}: {s.reason}; skipped")
    for d in folder.ignored_dirs:
        note(f"{_rel(folder, d)}/: not a type directory; skipped")
    for dup in folder.duplicates:
        raise FolderError(f"{_rel(folder, dup.ignored)}: duplicate id {dup.id} (also {_rel(folder, dup.kept)})")
    for eid in folder.in_both_layouts:
        legacy, served = folder.legacy[eid].path, folder.elements[eid].path
        note(f"{_rel(folder, legacy)}: id {eid} also at {_rel(folder, served)}; served elements/")

    order = {slug: i for i, slug in enumerate(ELEMENT_TYPES)}
    found = sorted(
        folder.all_elements().values(),
        key=lambda e: (e.layout != "elements", order.get(e.path.parent.name.lower(), len(order)), e.path),
    )
    out: list[tuple[str, dict[str, Any]]] = []
    for el in found:
        rel = _rel(folder, el.path)
        if el.type not in ELEMENT_TYPES:
            note(f"{rel}: `type` {el.type!r} is not one of the 22 types; skipped")
        else:
            out.append((el.type, el.body))
    return out


# --- names and links


def _slugify(name: str) -> str:
    """The bundle's own file names (not the folder's: §3.2 filenames are presentation, and so are these)."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text[:60].rstrip("-") or "element"


def assign_paths(elements: list[tuple[str, dict[str, Any]]]) -> dict[str, str]:
    """id -> bundle path (`character/the-consul--8b711e25.md`). Names are the slug plus the id's
    last 8 hex digits; a name two elements of one type would share falls back to the full id for
    both, so no order decides it."""
    stems: dict[str, tuple[str, str]] = {}
    for slug, body in elements:
        hexid = re.sub(r"[^0-9a-f]", "", body["id"].lower()) or "0"
        stems[body["id"]] = (slug, f"{_slugify(str(body.get('name') or ''))}--{hexid[-8:]}")
    counts: dict[tuple[str, str], int] = {}
    for key in stems.values():
        counts[key] = counts.get(key, 0) + 1
    paths = {}
    for eid, (slug, stem) in stems.items():
        if counts[(slug, stem)] > 1:
            stem = stem.rsplit("--", 1)[0] + "--" + re.sub(r"[^0-9a-f]", "", eid.lower())
        paths[eid] = f"{slug}/{stem}.md"
    return paths


def _link_text(name: str) -> str:
    text = " ".join(str(name).split()) or "(unnamed)"
    return text.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def _one_line(text: str) -> str:
    return " ".join(str(text).split())


def _heading(name: str) -> str:
    words = name.replace("_", " ")
    return words[:1].upper() + words[1:]


_FAKE_HEADING = re.compile(r" {0,3}#| {0,3}(=+|-+)[ \t]*$")


def escape_text(text: str) -> str:
    """A text field as body markdown: LF, outer blank lines trimmed, and a backslash before any
    line markdown would read as a heading (`# x`, or a `===`/`---` line that would underline the
    line above)."""
    out = []
    for line in str(text).replace("\r\n", "\n").replace("\r", "\n").strip("\n").split("\n"):
        if _FAKE_HEADING.match(line):
            i = len(line) - len(line.lstrip(" "))
            line = line[:i] + "\\" + line[i:]
        out.append(line)
    return "\n".join(out)


def _timestamp(value: Any) -> str | None:
    """An ISO 8601 datetime with an explicit offset (SPEC §5), else None."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if parsed.tzinfo is not None else None


def _unset(value: Any) -> bool:
    return value is None or value == "" or value == []


def _fm_key(name: str) -> str:
    return f"ow_{name}" if name in OKF_KEYS else name


def _generated(body: Mapping[str, Any]) -> dict[str, str]:
    gen = {"by": EXPORTER}
    at = _timestamp(body.get("updated_at"))
    if at:
        gen["at"] = at
    return gen


class _Links:
    """Resolves one file's links: a bundle path and a body link per id, or a note and nothing for
    an id that cannot be exported."""

    def __init__(self, here: str, paths: Mapping[str, str], names: Mapping[str, str], report: OkfReport, note: Note):
        self.here, self.paths, self.names = here, paths, names
        self.report, self.note = report, note

    def one(self, name: str, eid: Any, target: str | None) -> tuple[str, str] | None:
        if not isinstance(eid, str) or not eid:
            self.note(f"{self.here}: `{name}` holds {eid!r}, not an id; left out")
            return None
        if eid not in self.paths:
            self.report.unresolved.append(f"{self.here}: `{name}` -> {eid}")
            return f"urn:uuid:{eid}", f"`{eid}` (not in this bundle)"
        actual = self.paths[eid].split("/", 1)[0]
        if target and actual != target:
            self.note(f"{self.here}: `{name}` -> a {actual}, expected {target}; left out")
            return None
        self.report.links += 1
        rel = "../" + self.paths[eid] if "/" in self.here else self.paths[eid]
        return "/" + self.paths[eid], f"[{_link_text(self.names[eid])}]({rel})"


# --- one element


def element_doc(
    slug: str,
    body: Mapping[str, Any],
    paths: Mapping[str, str],
    names: Mapping[str, str],
    report: OkfReport,
    note: Note,
    *,
    kinds: Mapping[str, Mapping[str, str]] = FIELD_KINDS,
    sections: Mapping[str, tuple[tuple[str, tuple[str, ...]], ...]] = SECTIONS,
) -> str:
    """One element as an OKF concept. ``kinds`` and ``sections`` default to the generated schema."""
    here = paths[body["id"]]
    links = _Links(here, paths, names, report, note)
    fm: dict[str, Any] = {"type": _type_name(slug)}
    if not _unset(body.get("name")):
        fm["title"] = str(body["name"])
    if not _unset(body.get("description")):
        fm["description"] = str(body["description"])
    fm["generated"] = _generated(body)
    known = set(NOT_SENT)
    for name in BASE_FIELDS:
        known.add(name)
        if name in ("name", "description", "world"):
            continue
        if not _unset(body.get(name)):
            fm[_fm_key(name)] = body[name]

    blocks: list[tuple[str, str]] = []  # (kind, text): kind "text" or "link"
    current: str | None = None

    def open_section(name: str) -> None:
        nonlocal current
        if current != name:
            current = name
            blocks.append(("text", f"# {name}"))

    def add_links(section: str, name: str, found: list[tuple[str, str]], many: bool) -> None:
        if not found:
            return
        fm[_fm_key(name)] = [p for p, _ in found] if many else found[0][0]
        open_section(section)
        blocks.append(("link", f"- **{name}**: " + ", ".join(s for _, s in found)))

    generic = GENERIC_LINKS.get(slug, {})
    targets = LINK_TARGETS.get(slug, {})
    for section, field_names in sections[slug]:
        for name in field_names:
            if name in generic:
                type_key, id_key = generic[name]
                known.update((type_key, id_key))
                eid, target = body.get(id_key), body.get(type_key)
                if _unset(eid) and _unset(target):
                    continue
                if not isinstance(target, str) or target not in ELEMENT_TYPES:
                    note(f"{here}: `{name}` names type {target!r}, not a type slug; left out")
                    continue
                hit = links.one(name, eid, target)
                add_links(section, name, [hit] if hit else [], many=False)
                continue
            known.add(name)
            value = body.get(name)
            if _unset(value):
                continue
            kind = kinds[slug].get(name)
            if kind == "text":
                open_section(section)
                blocks.append(("text", f"## {_heading(name)}\n\n{escape_text(str(value))}"))
            elif kind == "integer":
                fm[_fm_key(name)] = value
            elif kind == "single_link":
                hit = links.one(name, value, targets.get(name))
                add_links(section, name, [hit] if hit else [], many=False)
            elif kind == "multi_link":
                if not isinstance(value, list):
                    note(f"{here}: `{name}` is not a list; left out")
                    continue
                hits = [links.one(name, v, targets.get(name)) for v in value]
                add_links(section, name, [h for h in hits if h], many=True)
            else:
                note(f"{here}: `{name}` has kind `{kind}`, which this exporter does not know; left out")

    for key, value in body.items():
        if key.startswith(EXTENSION_PREFIXES):
            fm[key] = value
        elif key not in known:
            note(f"{here}: `{key}` is not a field of {slug}; left out")

    out: list[str] = []
    for i, (kind, text) in enumerate(blocks):
        if i and not (kind == "link" and blocks[i - 1][0] == "link"):
            out.append("\n")
        out.append(text + "\n")
    return f"---\n{_frontmatter(fm)}---\n\n" + "".join(out)


# --- the world and the indexes


def world_doc(
    world: Mapping[str, Any],
    time_current: Any,
    count: int,
    paths: Mapping[str, str],
    names: Mapping[str, str],
    report: OkfReport,
    note: Note,
) -> str:
    """world.md. ``time_current`` is the folder's (``Folder.time_current``: either spelling, §5)."""
    links = _Links("world.md", paths, names, report, note)
    world = dict(world)
    if time_current is not None:
        world["time_current"] = time_current
    fm: dict[str, Any] = {"type": _type_name("world")}
    if not _unset(world.get("name")):
        fm["title"] = str(world["name"])
    if not _unset(world.get("description")):
        fm["description"] = str(world["description"])
    fm["generated"] = _generated(world)
    known = {*WORLD_DROPPED, "owner_character"}
    for name in WORLD_FIELDS:
        known.add(name)
        if name in ("name", "description"):
            continue
        if not _unset(world.get(name)):
            fm[_fm_key(name)] = world[name]
    if not _unset(world.get("owner_character")):
        hit = links.one("owner_character", world["owner_character"], "character")
        if hit:
            fm["owner_character"] = hit[0]
    for key, value in world.items():
        if key in WORLD_FOLDER_KEYS or key.startswith(("snapshot_", *EXTENSION_PREFIXES)):
            fm[_fm_key(key)] = value
        elif key not in known:
            note(f"world.json: `{key}` is not a World field; left out")
    fm["onlyworlds_export"] = {
        "exporter": EXPORTER,
        "schema": SCHEMA_VERSION,
        "schema_dist_serial": SCHEMA_DIST_SERIAL,
        "okf_version": OKF_VERSION,
        "okf_spec": f"{OKF_REPO}/blob/{OKF_COMMIT}/SPEC.md",
        "elements": count,
    }
    return f"---\n{_frontmatter(fm)}---\n"


def index_entry(title: str, link: str, desc: str) -> str:
    suffix = f" - {_one_line(desc)}" if _one_line(desc) else ""
    return f"* [{_link_text(title)}]({link}){suffix}"


def build_bundle(folder: Folder | str | os.PathLike[str], note: Note | None = None) -> tuple[dict[str, str], OkfReport]:
    """Every bundle file as {bundle path: text}, and the report. Writes nothing.

    ``note`` is called with each note as it is made (they are also in ``report.notes``).
    Raises ``FolderError`` when world.json cannot be read or one id is in two files of one layout.
    """
    report = OkfReport()

    def noted(msg: str) -> None:
        report.notes.append(msg)
        if note is not None:
            note(msg)

    if not isinstance(folder, Folder):
        folder = read_folder(folder)
    if folder.world is None:
        why = [s.reason for s in folder.skipped if s.path.parent == folder.root and s.path.name == WORLD_FILE]
        raise FolderError(why[0] if why else f"{folder.root}: no {WORLD_FILE}")
    elements = _elements(folder, noted)
    paths = assign_paths(elements)
    names = {body["id"]: str(body.get("name") or "") for _, body in elements}
    report.elements = len(elements)
    files: dict[str, str] = {}
    by_type: dict[str, list[tuple[str, str, str]]] = {}
    for slug, body in elements:
        path = paths[body["id"]]
        files[path] = element_doc(slug, body, paths, names, report, noted)
        by_type.setdefault(slug, []).append(
            (names[body["id"]], path.split("/", 1)[1], str(body.get("description") or ""))
        )

    files["world.md"] = world_doc(folder.world, folder.time_current, len(elements), paths, names, report, noted)
    root = [
        f'---\nokf_version: "{OKF_VERSION}"\n---\n',
        "# World\n",
        index_entry(
            str(folder.world.get("name") or "World"),
            "world.md",
            f"The world. OnlyWorlds schema {SCHEMA_VERSION}; OKF {OKF_VERSION} at commit {OKF_COMMIT[:7]}.",
        ),
        "",
        "# Element types\n",
    ]
    for slug in ELEMENT_TYPES:
        if slug not in by_type:
            continue
        entries = sorted(by_type[slug], key=lambda e: (e[0].casefold(), e[1]))
        n = len(entries)
        root.append(index_entry(_type_name(slug), f"{slug}/index.md", f"{n} element{'s' if n != 1 else ''}"))
        lines = [f"# {_type_name(slug)}", ""]
        lines += [index_entry(t, link, d) for t, link, d in entries]
        files[f"{slug}/index.md"] = "\n".join(lines) + "\n"
    files["index.md"] = "\n".join(root) + "\n"
    report.types = len(by_type)
    report.files = len(files)
    return files, report


def write_bundle(files: Mapping[str, str], out: str | os.PathLike[str]) -> None:
    """Write ``files`` under ``out``, which must not exist (``FileExistsError``)."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    for rel in sorted(files):
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(files[rel].encode("utf-8"))


def export_okf(
    folder: str | os.PathLike[str], out_dir: str | os.PathLike[str], *, note: Note | None = None
) -> OkfReport:
    """Export the world folder at ``folder`` as an OKF bundle at ``out_dir`` (which must not exist).

    Returns the report: counts, the unresolved links and the notes (``note`` is also called with
    each as it is made). Raises ``FileExistsError`` if ``out_dir`` exists, ``FolderError`` if the
    folder cannot be exported. Nothing is written unless the whole bundle was built.
    """
    out = Path(out_dir)
    if out.exists():
        raise FileExistsError(f"{out}: already exists; give a new directory")
    files, report = build_bundle(folder, note)
    write_bundle(files, out)
    report.out = out
    return report


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m onlyworlds.okf", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("folder", type=Path, help="a world folder (holds world.json and elements/)")
    ap.add_argument("out", type=Path, help="the bundle directory to create; must not exist")
    args = ap.parse_args(argv)
    if not (args.folder / WORLD_FILE).is_file():
        print(f"{args.folder}: not a world folder (no world.json)", file=sys.stderr)
        return 2
    if args.out.exists():
        print(f"{args.out}: already exists; give a new directory", file=sys.stderr)
        return 2

    def note(msg: str) -> None:
        print(f"note: {msg}", file=sys.stderr)

    try:
        report = export_okf(args.folder, args.out, note=note)
    except FolderError as e:
        print(f"{e}", file=sys.stderr)
        return 1
    for line in report.unresolved:
        print(f"unresolved link: {line}", file=sys.stderr)
    print(
        f"exported {report.elements} elements in {report.types} types to {args.out}: "
        f"{report.files} files, {report.links} links, {len(report.unresolved)} unresolved"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
