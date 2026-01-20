from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import prep_module

p_fs = prep_module("core", "fs")
p_zip = prep_module("core", "zip")

DatasetFS = p_fs.DatasetFS
DatasetDir = p_fs.DatasetDir
DatasetFile = p_fs.DatasetFile
zipcore = p_zip


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_sample_tree(tmp_path: Path) -> Path:
    root = tmp_path / "sample_root"
    (root / "data").mkdir(parents=True)
    (root / "pkg").mkdir(parents=True)

    (root / "README.md").write_text("root readme", encoding="utf-8")
    (root / "data" / "config.json").write_text('{"x": 1}', encoding="utf-8")
    (root / "pkg" / "__init__.py").write_text("# init", encoding="utf-8")
    (root / "pkg" / "module.py").write_text("print('hello')", encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_listdir_and_iterdir_dir_mode(tmp_path: Path):
    root = _build_sample_tree(tmp_path)
    fs = DatasetFS.from_path(root)

    names = fs.listdir()
    assert names == ["data", "pkg", "README.md"]

    entries = list(fs.iterdir())
    assert [e.name for e in entries] == ["data", "pkg", "README.md"]
    assert all(e.is_dir() for e in entries[:2])
    assert entries[-1].is_file()

    pkg = entries[1]
    assert isinstance(pkg, DatasetDir)
    assert pkg.listdir() == ["__init__.py", "module.py"]
    pkg_entries = list(pkg.iterdir())
    assert [e.name for e in pkg_entries] == ["__init__.py", "module.py"]
    assert all(isinstance(e, DatasetFile) for e in pkg_entries)
    assert all(e.is_file() for e in pkg_entries)


def test_listdir_and_iterdir_zip_mode(tmp_path: Path):
    root = _build_sample_tree(tmp_path)
    zip_path = tmp_path / "sample.zip"
    zipcore.create_from_dir(zip_path, root)

    fs = DatasetFS.from_path(zip_path)

    names = fs.listdir()
    assert names == ["data", "pkg", "README.md"]

    entries = list(fs.iterdir())
    assert [e.name for e in entries] == ["data", "pkg", "README.md"]
    assert all(e.is_dir() for e in entries[:2])
    assert entries[-1].is_file()

    pkg = entries[1]
    pkg_names = pkg.listdir()
    assert pkg_names == ["__init__.py", "module.py"]
    pkg_entries = list(pkg.iterdir())
    assert [e.name for e in pkg_entries] == ["__init__.py", "module.py"]
    assert all(e.is_file() for e in pkg_entries)


@pytest.mark.parametrize("mode", ["dir", "zip"])
def test_listdir_missing_returns_empty(tmp_path: Path, mode: str):
    root = _build_sample_tree(tmp_path)
    if mode == "zip":
        zip_path = tmp_path / "sample.zip"
        zipcore.create_from_dir(zip_path, root)
        fs = DatasetFS.from_path(zip_path)
    else:
        fs = DatasetFS.from_path(root)

    assert fs.listdir("missing") == []
    assert list(fs.iterdir("missing")) == []
