"""onlyworlds.lint: the dist's own folder checker, vendored byte for byte and run on the dist's schema.json."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from onlyworlds import lint

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "codegen" / "schema-dist"
WALK = ROOT / "src" / "onlyworlds" / "_walk"
HYPERION = DIST / "example" / "hyperion"
WORLD = {"id": "0190f2c4-0000-7000-8000-000000000001", "name": "Lint world"}


def _broken(tmp_path: Path) -> Path:
    (tmp_path / "world.json").write_text(json.dumps(WORLD), encoding="utf-8")
    chars = tmp_path / "elements" / "character"
    chars.mkdir(parents=True)
    body = {
        "id": "0190f2c4-0000-7000-8000-000000000002",
        "name": "Ash",
        "location": "not-a-uuid",
        "favourite_colour": "teal",
    }
    (chars / "ash--00000002.json").write_text(json.dumps(body), encoding="utf-8")
    (tmp_path / "elements" / "dragon").mkdir()
    (tmp_path / "elements" / "dragon" / "x.json").write_text(json.dumps({"id": "y", "name": "x"}), encoding="utf-8")
    return tmp_path


def test_the_vendored_checker_is_the_dists_byte_for_byte() -> None:
    assert (WALK / "lint_folder.py").read_bytes() == (DIST / "walk" / "lint_folder.py").read_bytes()
    assert (WALK / "schema.json").read_bytes() == (DIST / "schema.json").read_bytes()
    assert sorted(p.name for p in WALK.iterdir() if p.name != "__pycache__") == ["lint_folder.py", "schema.json"]


def test_loading_the_checker_has_no_side_effect() -> None:
    """No PyYAML, no schema walk, and the import path left as it was (the package's own modules, such as
    errors.py and http.py, must never shadow another import)."""
    code = (
        "import sys, json; from onlyworlds import lint; before = list(sys.path); lint._checker(); "
        "print(json.dumps({'yaml': 'yaml' in sys.modules, 'walk': 'schema_walk' in sys.modules, "
        "'path': sys.path == before}))"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {"yaml": False, "walk": False, "path": True}


def test_a_clean_world_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert lint.main([str(HYPERION)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[-1].startswith("checked ") and out[-1].endswith(": 0 problems")


def test_each_problem_is_named(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert lint.main([str(_broken(tmp_path))]) == 1
    out = capsys.readouterr().out
    assert "favourite_colour" in out
    assert "location" in out
    assert "dragon" in out
    assert out.splitlines()[-1].endswith("problems") and not out.splitlines()[-1].endswith(": 0 problems")


def test_not_a_world_folder(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert lint.main([str(tmp_path / "missing")]) == 2
    assert lint.main([str(tmp_path)]) == 2
    assert "not a world folder" in capsys.readouterr().out


@pytest.mark.parametrize("which", ["clean", "broken"])
def test_the_same_report_as_the_dists_own_command(which: str, tmp_path: Path) -> None:
    """One checker: the dist's command (which decodes the YAML itself) and this one print the same lines."""
    folder = HYPERION if which == "clean" else _broken(tmp_path)
    theirs = subprocess.run(
        [sys.executable, "-B", str(DIST / "walk" / "lint_folder.py"), str(folder)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    ours = subprocess.run(
        [sys.executable, "-m", "onlyworlds.lint", str(folder)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert theirs.returncode == ours.returncode
    assert [ln for ln in theirs.stdout.splitlines() if not ln.startswith("walk note:")] == ours.stdout.splitlines()


def test_git_missing_is_said_for_a_linked_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "world.json").write_text(json.dumps({**WORLD, "api": {"world_id": WORLD["id"]}}), encoding="utf-8")
    (tmp_path / "elements").mkdir()
    monkeypatch.setattr("onlyworlds.lint.shutil.which", lambda name: None)
    report = lint.lint(tmp_path)
    assert any("went unchecked" in w for w in report.warnings)
    assert report.problems == []


def test_git_present_adds_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "world.json").write_text(json.dumps({**WORLD, "api": {"world_id": WORLD["id"]}}), encoding="utf-8")
    (tmp_path / "elements").mkdir()
    monkeypatch.setattr("onlyworlds.lint.shutil.which", lambda name: "/usr/bin/git")
    assert not any("went unchecked" in w for w in lint.lint(tmp_path).warnings)


def test_the_format_version_is_the_checkers() -> None:
    from onlyworlds.folder import FORMAT_VERSION

    assert lint.format_version() == FORMAT_VERSION
