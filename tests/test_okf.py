"""OKF export (onlyworlds.okf) on the example world the vendored dist ships (codegen/schema-dist/example/hyperion).

Ported from schema-dist's walk/test_okf_export.py (branch okf-exporter, 8d0f92f): the same 24 tests,
on the package's reader and generated schema tables. Needs PyYAML (the ``okf`` extra; the dev group has
it); without it the module skips. OKF's reference parser and viewer
(github.com/GoogleCloudPlatform/open-knowledge-format at the commit okf.py pins) run too when importable:
put a checkout's ``src/`` on OKF_REFERENCE_SRC; otherwise those checks skip and say so.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml", reason='onlyworlds.okf needs PyYAML: pip install "onlyworlds[okf]"')

from onlyworlds import okf  # noqa: E402
from onlyworlds._schema import (  # noqa: E402
    BASE_FIELDS,
    EXTENSION_PREFIXES,
    FIELD_KINDS,
    GENERIC_LINKS,
    SCHEMA_VERSION,
    SECTIONS,
    WORLD_FIELDS,
)
from onlyworlds.push import NOT_SENT  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HYPERION = ROOT / "codegen" / "schema-dist" / "example" / "hyperion"
BODY_LINK = re.compile(r"\]\(([^)\s]+\.md)\)")

if os.environ.get("OKF_REFERENCE_SRC"):
    sys.path.insert(0, os.environ["OKF_REFERENCE_SRC"])
try:
    from reference_agent.bundle.document import OKFDocument  # type: ignore[import-not-found]
    from reference_agent.viewer import generate_visualization  # type: ignore[import-not-found]

    REFERENCE = None
except ImportError as e:
    OKFDocument = generate_visualization = None
    REFERENCE = (
        f"OKF reference parser not importable ({e}); set OKF_REFERENCE_SRC "
        f"to the src/ of an open-knowledge-format checkout at {okf.OKF_COMMIT[:7]}"
    )


def run(src: Path, out: Path) -> tuple[int, str]:
    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        code = okf.main([str(src), str(out)])
    return code, err.getvalue()


def tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def copy_world(dst: Path) -> Path:
    shutil.copytree(HYPERION, dst)
    return dst


def split(text: str) -> tuple[dict[str, Any], str]:
    """Frontmatter and body, found the way the reference parser finds them:
    str.splitlines(), so every line break Python knows ends a line."""
    lines = text.splitlines()
    assert lines and lines[0] == "---", "no frontmatter"
    end = lines.index("---", 1)
    return yaml.safe_load("\n".join(lines[1:end])) or {}, "\n".join(lines[end + 1 :])


def heading(name: str) -> str:
    words = name.replace("_", " ")
    return words[:1].upper() + words[1:]


def escape_text(text: str) -> str:
    """The body's text rule: a line markdown would read as a heading is escaped."""
    out = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").strip("\n").split("\n"):
        if re.match(r" {0,3}[#\\]", line) or re.fullmatch(r" {0,3}(=+|-+)[ \t]*", line):
            i = len(line) - len(line.lstrip(" "))
            line = line[:i] + "\\" + line[i:]
        out.append(line)
    return "\n".join(out)


def body_texts(body: str) -> dict[str, str]:
    found = re.finditer(r"^## ([^\n]+)\n\n(.*?)(?=\n\n#{1,2} |\n\n- \*\*|\Z)", body, re.S | re.M)
    return {m.group(1): m.group(2).rstrip("\n") for m in found}


def body_links(body: str) -> dict[str, list[str]]:
    found = re.finditer(r"^- \*\*(\w+)\*\*: (.*)$", body, re.M)
    return {m.group(1): BODY_LINK.findall(m.group(2)) for m in found}


def type_fields(slug: str) -> list[str]:
    return [name for _, names in SECTIONS[slug] for name in names]


def link_kind(slug: str, name: str) -> str | None:
    if name in GENERIC_LINKS.get(slug, {}):
        return "generic"
    kind = FIELD_KINDS[slug].get(name)
    return kind if kind in ("single_link", "multi_link") else None


def link_ids(src: dict[str, Any], slug: str, name: str) -> list[Any]:
    kind = link_kind(slug, name)
    if kind == "single_link":
        return [src[name]] if src.get(name) else []
    if kind == "multi_link":
        return list(src.get(name) or [])
    if kind == "generic":
        id_key = GENERIC_LINKS[slug][name][1]
        return [src[id_key]] if src.get(id_key) else []
    return []


class Bundle:
    def __init__(self, out: Path) -> None:
        self.out = out
        self.code, self.err = run(HYPERION, out)
        assert self.code == 0, self.err
        self.files = tree(out)
        self.sources: dict[str, dict[str, Any]] = {
            s["id"]: s
            for s in (
                json.loads(p.read_text(encoding="utf-8")) for p in sorted((HYPERION / "elements").rglob("*.json"))
            )
        }
        self.docs = {
            rel: split(data.decode("utf-8"))
            for rel, data in self.files.items()
            if rel.endswith(".md") and not rel.endswith("index.md") and rel != "world.md"
        }
        self.by_id = {fm["id"]: rel for rel, (fm, _) in self.docs.items()}

    def target_id(self, path: str, base: str | None = None) -> str:
        """The id inside the file a link names (bundle-absolute, or relative to base)."""
        rel = path[1:] if base is None else (Path(base).parent / path).as_posix()
        rel = os.path.normpath(rel).replace("\\", "/")
        assert rel in self.docs, f"link {path} from {base}: no such concept"
        return str(self.docs[rel][0]["id"])


@pytest.fixture(scope="module")
def bundle(tmp_path_factory: pytest.TempPathFactory) -> Bundle:
    return Bundle(tmp_path_factory.mktemp("okf") / "bundle")


# --- Hyperion's bundle


def test_one_file_per_element(bundle: Bundle) -> None:
    assert len(bundle.docs) == len(bundle.sources)
    assert set(bundle.by_id) == set(bundle.sources)


def test_type_title_description(bundle: Bundle) -> None:
    for rel, (fm, _) in bundle.docs.items():
        src = bundle.sources[fm["id"]]
        assert fm["type"] == "OnlyWorlds " + src["type"].capitalize(), rel
        assert fm["title"] == src["name"], rel
        assert fm.get("description", "") == (src.get("description") or ""), rel
        assert "generated" not in fm, rel  # no actor: the folder does not say who wrote what (OKF §7)
        assert "verified" not in fm, rel


def test_scalars_and_extensions_match_source(bundle: Bundle) -> None:
    """Base strings, every integer (0 included) and every extension key."""
    checked = 0
    for rel, (fm, _) in bundle.docs.items():
        src = bundle.sources[fm["id"]]
        for name in ("supertype", "subtype", "image_url"):
            assert fm.get(name, "") == (src.get(name) or ""), f"{rel}: {name}"
        for name in type_fields(src["type"]):
            if FIELD_KINDS[src["type"]].get(name) == "integer":
                assert fm.get(name) == src.get(name), f"{rel}: {name}"
                checked += src.get(name) == 0
        for key, value in src.items():
            if key.startswith(EXTENSION_PREFIXES):
                assert fm.get(key) == value, f"{rel}: {key}"
                checked += 1
    assert checked > 1, "the fixture holds a 0 and an extension key"


def test_text_fields_match_source(bundle: Bundle) -> None:
    checked = 0
    path_of = {fm["id"]: rel for rel, (fm, _) in bundle.docs.items() if "id" in fm}

    def prose(text: str) -> str:  # an in-prose ow:// target becomes the relative path of its concept
        return re.sub(r"\]\(ow://[A-Za-z_]+/([\w-]+)\)", lambda m: f"](../{path_of[m.group(1)]})", text)

    for rel, (fm, body) in bundle.docs.items():
        src = bundle.sources[fm["id"]]
        expected = {
            heading(name): prose(escape_text(src[name]))
            for name in type_fields(src["type"])
            if FIELD_KINDS[src["type"]].get(name) == "text" and src.get(name)
        }
        assert body_texts(body) == expected, rel
        checked += len(expected)
    assert checked > 0


def test_every_link_names_the_right_element(bundle: Bundle) -> None:
    """Frontmatter paths and body links, field by field, each target read by
    the id in its file: single, multi and generic, none missing, none extra."""
    checked = 0
    for rel, (fm, body) in bundle.docs.items():
        src = bundle.sources[fm["id"]]
        bullets = body_links(body)
        for name in type_fields(src["type"]):
            kind = link_kind(src["type"], name)
            if kind is None:
                continue
            want = link_ids(src, src["type"], name)
            if not want:
                assert name not in fm, rel
                assert name not in bullets, rel
                continue
            value = fm.get(name)
            assert value is not None, f"{rel}: {name} missing"
            paths = value if kind == "multi_link" else [value]
            assert [bundle.target_id(p) for p in paths] == want, f"{rel}: {name}"
            assert [bundle.target_id(p, rel) for p in bullets.get(name, [])] == want, f"{rel}: body {name}"
            checked += len(want)
    assert checked == 53


def test_indexes(bundle: Bundle) -> None:
    root = bundle.files["index.md"].decode("utf-8")
    assert root.startswith('---\nokf_version: "0.2"\n---\n')
    assert "* [OnlyWorlds Character](character/index.md) - 3 elements" in root
    assert bundle.files["character/index.md"].startswith(b"# OnlyWorlds Character\n")
    listed = []
    for rel, data in bundle.files.items():
        if rel.endswith("/index.md"):
            assert not data.startswith(b"---"), f"{rel}: frontmatter in an index"
            for link in BODY_LINK.findall(data.decode("utf-8")):
                listed.append(bundle.target_id(link, rel))
    assert sorted(listed) == sorted(bundle.sources)


def test_world_metadata(bundle: Bundle) -> None:
    fm, _ = split(bundle.files["world.md"].decode("utf-8"))
    meta = fm["onlyworlds_export"]
    assert fm["type"] == "OnlyWorlds World"
    assert fm["title"] == "Hyperion"
    assert fm["time_current"] == 0
    assert meta["schema"] == SCHEMA_VERSION
    assert okf.OKF_COMMIT in meta["okf_spec"]
    assert meta["elements"] == len(bundle.sources)


def test_rerun_is_byte_identical(bundle: Bundle, tmp_path: Path) -> None:
    code, _ = run(HYPERION, tmp_path / "bundle")
    assert code == 0
    assert tree(tmp_path / "bundle") == bundle.files


def test_lf_utf8(bundle: Bundle) -> None:
    for rel, data in bundle.files.items():
        assert b"\r" not in data, rel
        data.decode("utf-8")


def test_refuses_existing_out_dir(tmp_path: Path) -> None:
    assert run(HYPERION, tmp_path)[0] == 2
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(REFERENCE is not None, reason=REFERENCE or "")
def test_reference_parser_and_viewer(bundle: Bundle, tmp_path: Path) -> None:
    """OKF's own code at the pinned commit: every concept parses and has a
    type, indexes carry no frontmatter but the root's okf_version, and the
    viewer draws one edge per distinct linked pair."""
    for rel, data in bundle.files.items():
        doc = OKFDocument.parse(data.decode("utf-8"))
        if rel.endswith("index.md"):
            allowed = {"okf_version"} if rel == "index.md" else set()
            assert set(doc.frontmatter) <= allowed, rel
        else:
            doc.validate()
    pairs = {
        (s["id"], t)
        for s in bundle.sources.values()
        for name in type_fields(s["type"])
        for t in link_ids(s, s["type"], name)
        if t != s["id"]
    }
    stats = generate_visualization(bundle.out, tmp_path / "viz.html")
    assert stats["concepts"] == len(bundle.sources) + 1
    assert stats["edges"] == len(pairs)


# --- the legacy layout


def test_legacy_spatial_folder_exports_the_same_bundle(tmp_path: Path) -> None:
    """Map, pin, zone and marker under the legacy spatial/, one zone also in
    elements/ under another name: the bundle is Hyperion's, byte for byte,
    with the elements/ copy served."""
    src = copy_world(tmp_path / "world")
    (src / "spatial").mkdir()
    for slug in ("map", "pin", "zone", "marker"):
        shutil.move(str(src / "elements" / slug), str(src / "spatial" / slug))
    zone = next((src / "spatial" / "zone").glob("*.json"))
    (src / "elements" / "zone").mkdir()
    shutil.copy(zone, src / "elements" / "zone" / zone.name)
    old = json.loads(zone.read_text(encoding="utf-8"))
    zone.write_text(json.dumps(dict(old, name="Swamps (stale copy)")), encoding="utf-8")
    code, err = run(src, tmp_path / "bundle")
    assert code == 0, err
    assert "served elements/" in err
    assert run(HYPERION, tmp_path / "plain")[0] == 0
    assert tree(tmp_path / "bundle") == tree(tmp_path / "plain")


# --- hard cases


def test_awkward_cases(tmp_path: Path) -> None:
    """A frontmatter-breaking description, a name with brackets, two elements of one type
    sharing a name and id tail, and a link to an element the folder does not hold."""
    src = copy_world(tmp_path / "world")
    chars = src / "elements" / "character"
    consul_path = next(chars.glob("the-consul--*.json"))
    consul = json.loads(consul_path.read_text(encoding="utf-8"))
    consul["name"] = "The [Consul]"
    consul["description"] = "line one\n---\nline: three"
    consul["friends"] = ["00000000-0000-4000-8000-000000000001"]
    consul_path.write_text(json.dumps(consul), encoding="utf-8")
    twin = dict(consul, id="11111111-1111-4111-8111-1111" + consul["id"][-8:])
    twin["friends"] = []
    (chars / "twin.json").write_text(json.dumps(twin), encoding="utf-8")

    out = tmp_path / "bundle"
    code, err = run(src, out)
    assert code == 0
    assert "unresolved link" in err
    twins = sorted(p.name for p in (out / "character").glob("the-consul--*.md"))
    assert twins == sorted(f"the-consul--{i.replace('-', '')}.md" for i in (consul["id"], twin["id"]))
    docs = [split((out / "character" / n).read_text(encoding="utf-8"))[0] for n in twins]
    assert docs[0]["description"] == "line one\n---\nline: three"
    assert docs[0]["title"] == "The [Consul]"
    index = (out / "character" / "index.md").read_text(encoding="utf-8")
    assert "* [The \\[Consul\\]](" in index
    dangling = next(d for d in docs if "friends" in d)
    assert dangling["friends"] == ["urn:uuid:00000000-0000-4000-8000-000000000001"]


# --- Kael's review of the branch (h29 #6371), one test per finding


class World:
    def __init__(self, root: Path) -> None:
        self.src = copy_world(root / "world")
        self.out = root / "bundle"

    def edit(self, rel_glob: str, change: Callable[[dict[str, Any]], Any]) -> dict[str, Any]:
        path = next(self.src.glob(rel_glob))
        body: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        change(body)
        path.write_text(json.dumps(body), encoding="utf-8")
        return body

    def doc(self, rel_glob: str) -> tuple[dict[str, Any], str]:
        return split(next(self.out.glob(rel_glob)).read_text(encoding="utf-8"))

    def run(self) -> tuple[int, str]:
        return run(self.src, self.out)


@pytest.fixture
def world(tmp_path: Path) -> Iterator[World]:
    yield World(tmp_path)


def test_2_2_every_line_break_is_quoted(world: World) -> None:
    """U+2028, U+2029, NEL and the other breaks str.splitlines() knows."""
    text = "one\u2028---\u2028two\u2029---\x85---\x0b---\x0c---\x1c---\x1d---\x1e---"
    world.edit("elements/character/the-consul--*.json", lambda b: b.update(description=text, name="A ---"))
    code, err = world.run()
    assert code == 0, err
    fm, _ = world.doc("character/a--*.md")
    assert (fm["description"], fm["title"]) == (text, "A ---")
    if OKFDocument:
        doc = OKFDocument.parse(next(world.out.glob("character/a--*.md")).read_text(encoding="utf-8"))
        assert doc.frontmatter["description"] == text


def test_2_3_unreadable_files_are_noted_and_skipped(world: World) -> None:
    chars = world.src / "elements" / "character"
    (chars / ".atlas-cache.json").write_text("[]", encoding="utf-8")
    (chars / "no-id.json").write_text('{"name": "Nobody"}', encoding="utf-8")
    (chars / "broken.json").write_text("{not json", encoding="utf-8")
    (chars / "list.json").write_text("[1, 2]", encoding="utf-8")
    code, err = world.run()
    assert code == 0, err
    for name in (".atlas-cache.json", "no-id.json", "broken.json", "list.json"):
        assert f"elements/character/{name}" in err
    assert len(list((world.out / "character").glob("*--*.md"))) == 3


def test_2_4_world_keys_carried(world: World) -> None:
    world_path = world.src / "world.json"
    data = json.loads(world_path.read_text(encoding="utf-8"))
    del data["time_current"]
    consul = next((world.src / "elements" / "character").glob("the-consul--*.json"))
    consul_id = json.loads(consul.read_text(encoding="utf-8"))["id"]
    data.update(
        time_range_current=7,
        x_calendar={"months": 12},
        atlas_style="dark",
        owner_character=consul_id,
        snapshot_label="ch05",
        snapshot_counts={"character": 3},
        writable=False,
        api={"world_id": "w", "api_key": "secret"},
    )
    world_path.write_text(json.dumps(data), encoding="utf-8")
    code, err = world.run()
    assert code == 0, err
    fm, _ = split((world.out / "world.md").read_text(encoding="utf-8"))
    assert fm["time_current"] == 7
    assert "time_range_current" not in fm
    for key in ("x_calendar", "atlas_style", "snapshot_label", "snapshot_counts", "writable", "format_version"):
        assert fm[key] == data[key], key
    assert fm["owner_character"] == "/character/" + consul.stem + ".md"
    assert "api" not in fm
    assert "secret" not in (world.out / "world.md").read_text(encoding="utf-8")


def test_2_4_time_current_preferred(world: World) -> None:
    world_path = world.src / "world.json"
    data = json.loads(world_path.read_text(encoding="utf-8"))
    data.update(time_current=3, time_range_current=9)
    world_path.write_text(json.dumps(data), encoding="utf-8")
    assert world.run()[0] == 0
    assert split((world.out / "world.md").read_text(encoding="utf-8"))[0]["time_current"] == 3


def test_2_5_undeclared_keys_are_noted(world: World) -> None:
    world.edit(
        "elements/character/the-consul--*.json",
        lambda b: b.update(birthplace_old="somewhere", local_updated_at="2026-01-01T00:00:00Z"),
    )
    code, err = world.run()
    assert code == 0, err
    assert "`birthplace_old`" in err
    assert "local_updated_at" not in err  # a folder key: push.NOT_SENT
    fm, _ = world.doc("character/the-consul--*.md")
    assert "birthplace_old" not in fm


def test_2_5_unknown_kind_is_noted() -> None:
    kinds = {**FIELD_KINDS, "character": {**FIELD_KINDS["character"], "aura": "float"}}
    sections = {**SECTIONS, "character": (*SECTIONS["character"], ("Constitution", ("aura",)))}
    notes: list[str] = []
    consul = next((HYPERION / "elements" / "character").glob("the-consul--*.json"))
    body = dict(json.loads(consul.read_text(encoding="utf-8")), aura=0.5)
    paths = okf.assign_paths([("character", body)])
    okf.element_doc(
        "character", body, paths, {body["id"]: "x"}, okf.OkfReport(), notes.append, kinds=kinds, sections=sections
    )
    assert any("aura" in n and "float" in n for n in notes), notes


def test_nit_wrong_type_and_null_links_are_noted_and_left_out(world: World) -> None:
    chars = world.src / "elements" / "character"
    steinway = json.loads(next(chars.glob("mr-steinway--*.json")).read_text(encoding="utf-8"))
    world.edit(
        "elements/character/the-consul--*.json",
        lambda b: b.update(location=steinway["id"], objects=[None, *b["objects"]]),
    )
    world.edit("elements/pin/*.json", lambda b: b.update(element_type="location"))
    code, err = world.run()
    assert code == 0, err
    fm, body = world.doc("character/the-consul--*.md")
    assert "location" not in fm
    assert "**location**" not in body
    assert len(fm["objects"]) == 2
    assert "None" not in body + json.dumps(fm)
    pin, pin_body = world.doc("pin/*--*.md")
    assert "element" not in pin
    assert "**element**" not in pin_body
    assert "`location`" in err
    assert "`objects`" in err
    assert "`element`" in err


def test_nit_text_cannot_make_a_section(world: World) -> None:
    world.edit(
        "elements/character/the-consul--*.json",
        lambda b: b.update(background="# Fake section\n  ## Fake too\nplain\n===\n---"),
    )
    assert world.run()[0] == 0
    _, body = world.doc("character/the-consul--*.md")
    assert "\\# Fake section\n  \\## Fake too\nplain\n\\===\n\\---" in body
    assert "\n# Fake" not in body


def test_nit_an_escaped_line_reads_back(world: World) -> None:
    """A line that already begins with a backslash gets one more, so `# x` and `\\# x` stay apart."""
    world.edit(
        "elements/character/the-consul--*.json",
        lambda b: b.update(background="# x\n\\# x\n  \\ y\n    \\ z"),
    )
    assert world.run()[0] == 0
    _, body = world.doc("character/the-consul--*.md")
    assert "\\# x\n\\\\# x\n  \\\\ y\n    \\ z" in body


def test_nit_hyperion_run_is_quiet(world: World) -> None:
    assert run(HYPERION, world.out) == (0, "")


def test_nit_only_stderr_redirected(world: World) -> None:
    out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    with redirect_stdout(out), redirect_stderr(io.StringIO()):
        code = okf.main([str(HYPERION), str(world.out)])
    assert code == 0


def test_in_prose_ow_links_point_into_the_bundle(bundle: Bundle) -> None:
    """Hyperion's one-sentence narrative links three elements in its story as ow://: each becomes a
    relative link to that element's concept, and no ow:// target is left in any body."""
    rel, (_, body) = next((r, d) for r, d in bundle.docs.items() if r.startswith("narrative/a-world-in-a-sentence--"))
    targets = re.findall(r"\]\(([^)]+)\)", body)
    for t in ("../title/", "../institution/", "../character/"):
        hit = [x for x in targets if x.startswith(t)]
        assert hit and all((bundle.out / "narrative" / x).resolve().is_file() for x in hit), (rel, t)
    assert not any("](ow://" in b for _, b in bundle.docs.values())


def test_nit_an_ow_link_to_an_absent_id_stays_and_is_listed(world: World) -> None:
    ghost = "00000000-0000-7000-8000-000000000000"
    world.edit(
        "elements/character/the-consul--*.json",
        lambda b: b.update(background=f"See [nobody](ow://character/{ghost})."),
    )
    assert world.run()[0] == 0
    _, body = world.doc("character/the-consul--*.md")
    assert f"[nobody](ow://character/{ghost})" in body


# Frontmatter keys an OnlyWorlds field takes as `ow_<name>`, because OKF gives that name a meaning.
# None today; a schema bump that adds one fails the test below until it is added here and the
# CHANGELOG says how that field is written (#360: decided, not found by a reader).
OKF_RENAMED: frozenset[str] = frozenset()


def test_no_frontmatter_field_takes_an_okf_key_unannounced() -> None:
    """Every field the exporter writes into frontmatter (not text: that goes in the body) against
    the keys OKF defines."""
    frontmatter = (
        {n for kinds in FIELD_KINDS.values() for n, kind in kinds.items() if kind != "text"}
        | (set(BASE_FIELDS) - {"name", "description", "world"})
        | (set(WORLD_FIELDS) - {"name", "description"})
        | {n for links in GENERIC_LINKS.values() for n in links}
    )
    assert len(frontmatter) > 100, "the schema tables read as empty"
    assert frontmatter & okf.OKF_KEYS == OKF_RENAMED


def test_nit_no_actor_is_explained() -> None:
    assert "human:" in (okf.__doc__ or "")


def test_world_names_no_actor_and_the_exporter_once(bundle: Bundle) -> None:
    fm, _ = split(bundle.files["world.md"].decode("utf-8"))
    assert "generated" not in fm
    assert fm["onlyworlds_export"]["exporter"] == okf.EXPORTER


# --- the package's conditions


def test_core_import_does_not_load_yaml() -> None:
    """`import onlyworlds` stays dependency-free: PyYAML is only the okf extra's."""
    r = subprocess.run(
        [sys.executable, "-c", "import sys, onlyworlds; assert 'yaml' not in sys.modules, 'yaml imported'"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr


def test_known_keys_cover_the_dist_lint() -> None:
    """The server and folder keys the exporter passes in silence (push.NOT_SENT) include every
    key the pinned dist's folder lint passes, and the extension prefixes are the lint's."""
    spec = importlib.util.spec_from_file_location(
        "lint_folder", ROOT / "codegen" / "schema-dist" / "walk" / "lint_folder.py"
    )
    assert spec is not None and spec.loader is not None
    lint = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lint)
    assert set(lint.BODY_EXTRA_KEYS) | set(lint.FOLDER_KEYS) <= NOT_SENT
    assert tuple(lint.EXTENSION_PREFIXES) == EXTENSION_PREFIXES
