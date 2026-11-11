"""Every importer's --help says one source, one world: its ids are made from the source."""

from __future__ import annotations

import importlib

import pytest

from onlyworlds.folder import ONE_SOURCE_ONE_WORLD

DOORS = ["kanka", "campfire", "legendkeeper", "notion", "worldanvil"]


@pytest.mark.parametrize("door", DOORS)
def test_help_ends_with_one_source_one_world(door: str, capsys: pytest.CaptureFixture[str]) -> None:
    mod = importlib.import_module(f"onlyworlds.{door}")
    with pytest.raises(SystemExit) as exc:
        mod.main(["--help"])
    assert exc.value.code == 0
    out = " ".join(capsys.readouterr().out.split())
    assert " ".join(ONE_SOURCE_ONE_WORLD.split()) in out
