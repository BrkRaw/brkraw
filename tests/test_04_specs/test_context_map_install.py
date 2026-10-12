"""Installing shared context maps (BRK-0038, b1 bundle B7).

`brkraw addon add` installs a context map with `__meta__.name` and `version`
into the config folder's `context_maps/`; hook packages ship them with a
manifest key `context_maps` (installed under `context_maps/<namespace>/`).
`include` by name looks only there. The dataset's own map stays next to the
dataset.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from brkraw.api import context_map
from brkraw.cli.main import main


def _write(path: Path, data: dict) -> Path:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _base(tmp_path: Path, version: str = "1.0.0", ses: str = "baseline", name: str = "lab_base") -> Path:
    return _write(tmp_path / f"{name}-{version}.yaml", {
        "__meta__": {"category": "context_map", "name": name, "version": version, "description": "lab base"},
        "bids": {"ses": ses},
    })


def _dataset_map(tmp_path: Path, include) -> Path:
    return _write(tmp_path / "study.yaml", {
        "__meta__": {"category": "context_map", "include": [include]},
        "bids": {"sub": "01"},
    })


@pytest.fixture
def root(tmp_path, monkeypatch):
    cfg = tmp_path / "cfg"
    monkeypatch.setenv("BRKRAW_CONFIG_HOME", str(cfg))
    return cfg


def test_addon_add_installs_a_context_map_into_context_maps(tmp_path, root, capsys, caplog):
    import logging

    assert main(["addon", "add", str(_base(tmp_path))]) == 0
    assert (root / "context_maps" / "lab_base-1.0.0.yaml").is_file()
    assert main(["config", "path", "context_maps"]) == 0
    assert capsys.readouterr().out.strip().endswith("context_maps")
    with caplog.at_level(logging.INFO):              # addon list prints its tables through logging
        assert main(["addon", "list"]) == 0
    assert "lab_base" in caplog.text and "Context Maps" in caplog.text


def test_include_by_name_finds_the_installed_map(tmp_path, root):
    assert main(["addon", "add", str(_base(tmp_path))]) == 0
    data = context_map.load_context_map(_dataset_map(tmp_path, "lab_base"))
    assert data["bids"] == {"ses": "baseline", "sub": "01"}


def test_include_by_name_picks_the_latest_version_unless_one_is_given(tmp_path, root):
    assert main(["addon", "add", str(_base(tmp_path, "1.0.0", "old"))]) == 0
    assert main(["addon", "add", str(_base(tmp_path, "1.2.0", "new"))]) == 0
    assert context_map.load_context_map(_dataset_map(tmp_path, "lab_base"))["bids"]["ses"] == "new"
    pinned = _dataset_map(tmp_path, {"use": "lab_base", "version": "1.0.0"})
    assert context_map.load_context_map(pinned)["bids"]["ses"] == "old"


def test_a_path_next_to_the_file_does_not_need_installing(tmp_path, root):
    base = _base(tmp_path)
    data = context_map.load_context_map(_dataset_map(tmp_path, base.name))
    assert data["bids"]["ses"] == "baseline"


def test_include_by_name_does_not_look_in_specs(tmp_path, root):
    (root / "specs").mkdir(parents=True)
    _base(root / "specs")
    with pytest.raises(context_map.ContextMapError, match="not found"):
        context_map.load_context_map(_dataset_map(tmp_path, "lab_base"))


def test_installing_needs_name_and_version(tmp_path, root, caplog):
    bad = _write(tmp_path / "nameless.yaml", {"__meta__": {"category": "context_map"}, "bids": {"ses": "x"}})
    assert main(["addon", "add", str(bad)]) != 0
    assert "name" in caplog.text and not (root / "context_maps" / "nameless.yaml").exists()


def test_invalid_context_map_is_not_installed(tmp_path, root, caplog):
    bad = _write(tmp_path / "old.yaml", {
        "__meta__": {"category": "context_map", "name": "old_map", "version": "1.0.0", "description": "x"},
        "Subject.ID": {"type": "mapping", "values": {"a": "b"}},
    })
    assert main(["addon", "add", str(bad)]) != 0
    assert not (root / "context_maps" / "old.yaml").exists()


def test_addon_rm_removes_an_installed_context_map(tmp_path, root):
    assert main(["addon", "add", str(_base(tmp_path))]) == 0
    assert main(["addon", "rm", "lab_base-1.0.0.yaml"]) == 0
    assert not (root / "context_maps" / "lab_base-1.0.0.yaml").exists()


def test_hook_manifest_ships_context_maps(tmp_path, root):
    from brkraw.apps.hook import core as hook_core

    pkg = tmp_path / "pkg"
    pkg.mkdir()
    _base(pkg, name="bids_base")
    manifest = pkg / "brkraw_hook.yaml"
    manifest.write_text("context_maps: [bids_base-1.0.0.yaml]\n", encoding="utf-8")
    installed = hook_core._install_manifest({"context_maps": ["bids_base-1.0.0.yaml"]}, manifest,
                                            root=None, namespace="demo")
    assert installed["context_maps"] == ["context_maps/demo/bids_base-1.0.0.yaml"]
    assert (root / "context_maps" / "demo" / "bids_base-1.0.0.yaml").is_file()
    data = context_map.load_context_map(_dataset_map(tmp_path, "bids_base"))
    assert data["bids"]["ses"] == "baseline"
