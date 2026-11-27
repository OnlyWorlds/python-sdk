"""Hold the package to its promise: a patch fixes, a minor adds, and neither removes or renames a public name.

A name that will go is marked deprecated first, says since which release and that it leaves in onlyworlds 1.0
(the next major), stays at least six months, and goes only in a major. Three rules, read from the source with
`ast` (the package is never imported) against the names file `scripts/public-names.json`:

1. Marks. Every deprecation mark in a public module (one whose dotted name has no part with a leading
   underscore) says since when and where it leaves. A mark is a docstring or a `#:` comment that says
   "deprecated", or a function that calls `warnings.warn(..., DeprecationWarning)`. The owner's docstring
   (the function's or class's own; for a `#:` comment, the class or module that holds the name) says
   `Deprecated since X.Y.Z` and `onlyworlds N.0` with N above the current major. A warning's text also
   names `onlyworlds N.0` and its replacement, a public name of the package. A class docstring that says
   "deprecated" while a `#:` comment in its body marks one of its keys is read as that key's mark.
2. Names. Each public module's names are its `__all__` when it has one, else its top-level public `def`,
   `class` and assigned names. Within the major the file was read at, a listed name gone from the source
   fails, and so does a public name, or a mark, the file does not hold.
3. Six months. When the major has moved, a listed name gone from the source must have been marked, and the
   release its mark names (a CHANGELOG.md heading `## x.y.z (YYYY-MM-DD)`) must be at least six months
   before today.

Not held: whether a mark's words are true, and a change of behaviour under an unchanged name.

Usage:
  python scripts/verify_promise.py           check the source against the names file
  python scripts/verify_promise.py --write   add new names and update the marks; a name is removed only
                                             when the major moved and its removal keeps rule 3
Exit 0 when the promise holds, 1 and one line per failure (module, name, rule), 2 when a file could not be
read (a module that does not parse, an `__all__` that is not a literal list, no version): never a pass.
"""

from __future__ import annotations

import argparse
import ast
import calendar
import datetime
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = "onlyworlds"
SOURCE = ROOT / "src" / PACKAGE
VERSION_FILE = SOURCE / "_version.py"
CHANGELOG = ROOT / "CHANGELOG.md"
NAMES_FILE = ROOT / "scripts" / "public-names.json"

SAYS_DEPRECATED = re.compile(r"\bdeprecated\b", re.IGNORECASE)
SINCE = re.compile(r"\b[Dd]eprecated since (\d+\.\d+\.\d+)\b")
LEAVES = re.compile(r"\bonlyworlds (\d+)\.0\b")
HEADING = re.compile(r"^## (\d+\.\d+\.\d+) \((\d{4}-\d{2}-\d{2})\)$", re.MULTILINE)
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
MODULE_SELF = "(module)"  # the key a module's own deprecation is recorded under
ABOUT = (
    "The public names of the onlyworlds package, read by scripts/verify_promise.py: each public module's names, "
    "the deprecated ones with the release that marked them and the major they leave in, and the version they "
    "were read at. Run the script with --write after adding names; it never removes one within a major."
)


class Unseen(Exception):
    """A file the check needs could not be read: exit 2, never a pass."""


@dataclass
class Mark:
    """One deprecated name: where its words are, and what they say."""

    texts: list[str] = field(default_factory=list)  # the mark's own words (docstring or `#:` comment)
    owner_doc: str = ""  # the docstring that must say since when and where it leaves
    warnings: list[str] = field(default_factory=list)  # each DeprecationWarning's text
    line: int = 0


@dataclass
class Module:
    name: str
    path: Path
    names: set[str]
    quals: set[str]  # every class, def and class-level assignment, dotted from the module
    marks: dict[str, Mark]


@dataclass(frozen=True)
class Failure:
    module: str
    name: str
    rule: str
    text: str
    kind: str  # "mark", "gone", "unlisted", "record", "early"

    def line(self) -> str:
        return f"{self.module}: {self.name}: {self.rule}: {self.text}"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise Unseen(f"{path.relative_to(ROOT).as_posix()}: {exc}") from exc


def parse(path: Path) -> tuple[ast.Module, list[str]]:
    text = read_text(path)
    try:
        return ast.parse(text, filename=str(path)), text.splitlines()
    except SyntaxError as exc:
        raise Unseen(f"{path.relative_to(ROOT).as_posix()}: does not parse: {exc.msg} (line {exc.lineno})") from exc


def read_version() -> str:
    tree, _ = parse(VERSION_FILE)
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and re.fullmatch(r"\d+\.\d+\.\d+", node.value.value)
        ):
            return node.value.value
    raise Unseen(f'{VERSION_FILE.relative_to(ROOT).as_posix()}: no __version__ = "X.Y.Z"')


def major_of(version: str) -> int:
    return int(version.split(".", 1)[0])


def public_modules() -> dict[str, Path]:
    if not SOURCE.is_dir():
        raise Unseen(f"{SOURCE.relative_to(ROOT).as_posix()}: not a folder")
    found: dict[str, Path] = {}
    for path in sorted(SOURCE.rglob("*.py")):
        parts = path.relative_to(SOURCE).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if any(part.startswith("_") for part in parts):
            continue
        found[".".join((PACKAGE, *parts))] = path
    if PACKAGE not in found:
        raise Unseen(f"{SOURCE.relative_to(ROOT).as_posix()}/__init__.py: missing")
    return found


def is_public(name: str) -> bool:
    return not name.startswith("_")


def string_of(node: ast.expr) -> str | None:
    """The literal text of a message: a string, an f-string's fixed parts, or a sum of those."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = string_of(node.left), string_of(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def is_deprecation_warn(call: ast.Call) -> bool:
    func = call.func
    named_warn = (isinstance(func, ast.Attribute) and func.attr == "warn") or (
        isinstance(func, ast.Name) and func.id == "warn"
    )
    if not named_warn:
        return False
    category = call.args[1] if len(call.args) > 1 else None
    for keyword in call.keywords:
        if keyword.arg == "category":
            category = keyword.value
    return (isinstance(category, ast.Name) and category.id == "DeprecationWarning") or (
        isinstance(category, ast.Attribute) and category.attr == "DeprecationWarning"
    )


def warn_texts(nodes: list[ast.stmt], where: str) -> list[str]:
    texts: list[str] = []
    for stmt in nodes:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call) and is_deprecation_warn(node):
                message = node.args[0] if node.args else None
                for keyword in node.keywords:
                    if keyword.arg == "message":
                        message = keyword.value
                text = string_of(message) if message is not None else None
                if text is None:
                    raise Unseen(f"{where} (line {node.lineno}): a DeprecationWarning whose text is not a literal")
                texts.append(text)
    return texts


def comment_above(lines: list[str], node: ast.stmt) -> str:
    """The `#:` comment that documents an assignment: the lines just above it, or the end of its own line."""
    found: list[str] = []
    index = node.lineno - 2
    while index >= 0 and lines[index].strip().startswith("#:"):
        found.insert(0, lines[index].strip()[2:].strip())
        index -= 1
    own = lines[node.lineno - 1]
    if "#:" in own:
        found.append(own.split("#:", 1)[1].strip())
    return " ".join(found)


def assigned_names(node: ast.stmt) -> list[str]:
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]
    elif isinstance(node, ast.TypeAlias):
        targets = [node.name]
    names: list[str] = []
    while targets:
        target = targets.pop(0)
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            targets.extend(target.elts)
        elif isinstance(target, ast.Starred):
            targets.append(target.value)
    return names


def flat_body(body: list[ast.stmt]) -> list[ast.stmt]:
    """A body's statements, with the bodies of top-level `if`, `try` and `with` blocks taken in."""
    out: list[ast.stmt] = []
    for node in body:
        if isinstance(node, ast.If):
            out.extend(flat_body(node.body + node.orelse))
        elif isinstance(node, (ast.Try, ast.TryStar)):
            inner = node.body + node.orelse + node.finalbody
            for handler in node.handlers:
                inner += handler.body
            out.extend(flat_body(inner))
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            out.extend(flat_body(node.body))
        else:
            out.append(node)
    return out


def read_module(name: str, path: Path) -> Module:
    tree, lines = parse(path)
    where = path.relative_to(ROOT).as_posix()
    body = flat_body(tree.body)
    module = Module(name, path, set(), set(), {})

    declared = [n for n in body if isinstance(n, (ast.Assign, ast.AnnAssign)) and "__all__" in assigned_names(n)]
    if declared:
        value = declared[-1].value
        if not (
            isinstance(value, (ast.List, ast.Tuple))
            and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in value.elts)
        ):
            raise Unseen(f"{where} (line {declared[-1].lineno}): __all__ is not a literal list of strings")
        module.names = {e.value for e in value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    if any(isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name) and n.target.id == "__all__" for n in body):
        raise Unseen(f"{where}: __all__ is extended in place, not one literal list")

    tied: set[int] = set()  # the lines of `#:` comments tied to a name

    def tie(node: ast.stmt) -> None:
        index = node.lineno - 2
        while index >= 0 and lines[index].strip().startswith("#:"):
            tied.add(index + 1)
            index -= 1
        tied.add(node.lineno)

    def walk(statements: list[ast.stmt], prefix: str, owner: ast.Module | ast.ClassDef) -> None:
        owner_doc = ast.get_docstring(owner, clean=False) or ""
        for node in statements:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = prefix + node.name
                module.quals.add(qual)
                doc = ast.get_docstring(node, clean=False) or ""
                warned = warn_texts(node.body, f"{where}: {qual}") if not isinstance(node, ast.ClassDef) else []
                if SAYS_DEPRECATED.search(doc) or warned:
                    module.marks[qual] = Mark([doc] if doc else [], doc, warned, node.lineno)
                if isinstance(node, ast.ClassDef):
                    walk(flat_body(node.body), qual + ".", node)
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.TypeAlias)):
                comment = comment_above(lines, node)
                tie(node)
                for target in assigned_names(node):
                    qual = prefix + target
                    module.quals.add(qual)
                    if comment and SAYS_DEPRECATED.search(comment):
                        module.marks[qual] = Mark([comment], owner_doc, [], node.lineno)
        # A class whose keys carry the deprecation: its docstring's "deprecated" is theirs, not its own.
        if isinstance(owner, ast.ClassDef):
            own = prefix[:-1]
            keys = [q for q in module.marks if q.startswith(prefix) and "." not in q[len(prefix) :]]
            keyed = [q for q in keys if module.marks[q].owner_doc == owner_doc and q != own]
            if own in module.marks and keyed and not module.marks[own].warnings:
                del module.marks[own]

    walk(body, "", tree)
    module_doc = ast.get_docstring(tree, clean=False) or ""
    top_warned = warn_texts(
        [n for n in body if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))], where
    )
    if SAYS_DEPRECATED.search(module_doc) or top_warned:
        module.marks[MODULE_SELF] = Mark([module_doc], module_doc, top_warned, 1)

    for number, text in enumerate(lines, start=1):
        if text.strip().startswith("#:") and SAYS_DEPRECATED.search(text) and number not in tied:
            module.marks[f"(line {number})"] = Mark([text.strip()], "", [], number)

    if not declared:
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                module.names.add(node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.TypeAlias)):
                module.names.update(assigned_names(node))
        module.names = {n for n in module.names if is_public(n)}
    return module


def leaves_above(text: str, major: int) -> int | None:
    above = sorted(int(m) for m in LEAVES.findall(text) if int(m) > major)
    return above[0] if above else None


def judge_marks(
    module: Module, major: int, every_name: set[str]
) -> tuple[dict[str, dict[str, str | None]], list[Failure]]:
    """Rule 1: each mark says since when and where it leaves; a warning names its replacement and that major."""
    recorded: dict[str, dict[str, str | None]] = {}
    failures: list[Failure] = []
    for qual, mark in sorted(module.marks.items()):
        if any(not is_public(part) for part in qual.split(".")) and qual != MODULE_SELF:
            continue

        def fail(text: str, qual: str = qual) -> None:
            failures.append(Failure(module.name, qual, "marks", text, "mark"))

        if not mark.owner_doc and qual.startswith("(line"):
            fail("a #: comment says deprecated but documents no assignment")
            continue
        own = " ".join(mark.texts)
        sinces = sorted(set(SINCE.findall(own))) or sorted(set(SINCE.findall(mark.owner_doc)))
        whose = "its docstring" if mark.texts and mark.texts[0] == mark.owner_doc else "its owner's docstring"
        since: str | None = None
        if not sinces:
            fail(f'{whose} says no "Deprecated since X.Y.Z"')
        elif len(sinces) > 1:
            fail(f"{whose} names more than one release ({', '.join(sinces)}): say which in the mark")
        else:
            since = sinces[0]
        leaves = leaves_above(own, major) or leaves_above(mark.owner_doc, major)
        if leaves is None:
            fail(f'{whose} says no "onlyworlds {major + 1}.0", the major it leaves in')
        for text in mark.warnings:
            if leaves_above(text, major) is None:
                fail(f'its DeprecationWarning text says no "onlyworlds {major + 1}.0": {text!r}')
            own_name = qual.rsplit(".", 1)[-1]
            named = [t for t in IDENTIFIER.findall(text) if t != own_name and t != PACKAGE and t in every_name]
            if not named:
                fail(f"its DeprecationWarning text names no replacement (a public name of the package): {text!r}")
        recorded[qual] = {"since": since, "leaves": f"{leaves}.0" if leaves is not None else None}
    return recorded, failures


def said(mark: dict[str, str | None] | None) -> str:
    """A recorded mark in words, for a line that says the source and the names file differ."""
    if mark is None:
        return "no mark"
    return f"deprecated since {mark.get('since') or '(none)'}, leaving in onlyworlds {mark.get('leaves') or '(none)'}"


def changelog_dates() -> dict[str, datetime.date]:
    return {v: datetime.date.fromisoformat(d) for v, d in HEADING.findall(read_text(CHANGELOG))}


def six_months_after(day: datetime.date) -> datetime.date:
    month = day.month + 6
    year, month = day.year + (month - 1) // 12, (month - 1) % 12 + 1
    return datetime.date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def load_names_file(writing: bool) -> dict[str, Any] | None:
    if not NAMES_FILE.exists():
        if writing:
            return None
        raise Unseen(f"{NAMES_FILE.relative_to(ROOT).as_posix()}: missing (run with --write to make it)")
    try:
        data = json.loads(read_text(NAMES_FILE))
    except json.JSONDecodeError as exc:
        raise Unseen(f"{NAMES_FILE.relative_to(ROOT).as_posix()}: not JSON: {exc}") from exc
    if not (
        isinstance(data, dict)
        and isinstance(data.get("version"), str)
        and re.fullmatch(r"\d+\.\d+\.\d+", data["version"])
        and isinstance(data.get("modules"), dict)
        and all(isinstance(v, list) and all(isinstance(n, str) for n in v) for v in data["modules"].values())
        and isinstance(data.get("deprecated"), dict)
        and all(isinstance(v, dict) for v in data["deprecated"].values())
    ):
        raise Unseen(f"{NAMES_FILE.relative_to(ROOT).as_posix()}: not the names file's shape")
    return data


def run(writing: bool, today: datetime.date) -> int:
    version = read_version()
    major = major_of(version)
    modules = {name: read_module(name, path) for name, path in public_modules().items()}
    every_name: set[str] = set()
    for module in modules.values():
        short = module.name.removeprefix(PACKAGE + ".")
        every_name |= module.names | module.quals | {f"{short}.{n}" for n in module.names}
    every_name = {n for n in every_name if all(is_public(p) for p in n.split("."))}

    failures: list[Failure] = []
    marks: dict[str, dict[str, dict[str, str | None]]] = {}
    for module in modules.values():
        recorded, bad = judge_marks(module, major, every_name)
        failures += bad
        if recorded:
            marks[module.name] = recorded

    data = load_names_file(writing)
    listed: dict[str, list[str]] = data["modules"] if data else {}
    was_marked: dict[str, dict[str, dict[str, str | None]]] = data["deprecated"] if data else {}
    read_at = str(data["version"]) if data else version
    moved = major_of(read_at) != major
    if major_of(read_at) > major:
        raise Unseen(f"the names file was read at {read_at}, a later major than the source's {version}")

    dates = changelog_dates() if moved else {}
    removed: dict[str, set[str]] = {}  # names a moved major may drop from the file

    def present(module_name: str, name: str) -> bool:
        module = modules.get(module_name)
        if module is None:
            return False
        if name == MODULE_SELF:
            return True
        return name in module.names if "." not in name else name in module.quals

    def gone(module_name: str, name: str) -> None:
        if not moved:
            text = f"listed at {read_at}, gone from the source within major {major} (a name stays within a major)"
            failures.append(Failure(module_name, name, "names", text, "gone"))
            return
        mark = was_marked.get(module_name, {}).get(name) or was_marked.get(module_name, {}).get(MODULE_SELF)
        since = mark.get("since") if mark else None
        if mark is None:
            text = f"gone in major {major} with no deprecation mark at {read_at} (a name is marked before it leaves)"
        elif not since:
            text = f"gone in major {major}, marked at {read_at} with no release it was deprecated in"
        elif since not in dates:
            text = f"gone in major {major}, deprecated since {since}, a release CHANGELOG.md does not date"
        elif six_months_after(dates[since]) > today:
            text = (
                f"gone in major {major}, deprecated since {since} ({dates[since].isoformat()}): under six months "
                f"before {today.isoformat()} (a name stays six months marked)"
            )
        else:
            removed.setdefault(module_name, set()).add(name)
            return
        failures.append(Failure(module_name, name, "six months", text, "early"))

    for module_name, names in sorted(listed.items()):
        for name in sorted(names):
            if not present(module_name, name):
                gone(module_name, name)
    for module_name, keys in sorted(was_marked.items()):
        for name in sorted(keys):
            if "." in name and not present(module_name, name):
                gone(module_name, name)

    for module_name, module in sorted(modules.items()):
        for name in sorted(module.names - set(listed.get(module_name, []))):
            failures.append(
                Failure(
                    module_name, name, "names", "public, not in scripts/public-names.json (run --write)", "unlisted"
                )
            )
    for module_name in sorted(set(marks) | set(was_marked)):
        now, then = marks.get(module_name, {}), was_marked.get(module_name, {})
        for name in sorted(set(now) | set(then)):
            if name.startswith("(line") or not present(module_name, name):
                continue
            if now.get(name) != then.get(name):
                text = f"the source has {said(now.get(name))}, the names file {said(then.get(name))} (run --write)"
                failures.append(Failure(module_name, name, "names", text, "record"))

    if writing:
        held_back = any(f.kind in ("gone", "early") for f in failures)
        new_modules: dict[str, list[str]] = {}
        for module_name in sorted(set(listed) | set(modules)):
            keep = {n for n in listed.get(module_name, []) if n not in removed.get(module_name, set())}
            names = keep | (modules[module_name].names if module_name in modules else set())
            if names:
                new_modules[module_name] = sorted(names)
        new_marks: dict[str, dict[str, dict[str, str | None]]] = {}
        for module_name in sorted(set(marks) | set(was_marked)):
            entries = {k: v for k, v in marks.get(module_name, {}).items() if not k.startswith("(line")}
            for name, mark in was_marked.get(module_name, {}).items():
                if not present(module_name, name) and name not in removed.get(module_name, set()):
                    entries[name] = mark  # a name still listed keeps the mark it left with
            if entries:
                new_marks[module_name] = dict(sorted(entries.items()))
        out = {
            "about": ABOUT,
            "version": read_at if held_back and moved else version,
            "major": major_of(read_at) if held_back and moved else major,
            "modules": new_modules,
            "deprecated": new_marks,
        }
        with NAMES_FILE.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(out, indent=2, ensure_ascii=True) + "\n")
        failures = [f for f in failures if f.kind not in ("unlisted", "record")]

    for failure in failures:
        print(failure.line())
    count = sum(len(m.names) for m in modules.values())
    marked = sum(len(v) for v in marks.values())
    verdict = f"{len(failures)} failure{'s' if len(failures) != 1 else ''}" if failures else "the promise holds"
    print(f"verify_promise: {len(modules)} public modules, {count} names, {marked} marks, at {version}: {verdict}")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--write", action="store_true", help="add new names and update marks in the names file")
    args = parser.parse_args(argv)
    try:
        return run(args.write, datetime.date.today())
    except Unseen as exc:
        print(f"verify_promise: could not see: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
