"""Tests for the shared test base: environment isolation and synthetic data.

Checks on approved anonymized zips (real data) are not tests; they are manual
checks in ``scripts/validate/`` (docs/dev/contributing.md).
"""
from __future__ import annotations

import os
from pathlib import Path

import brkraw
from brkraw.apps.loader import info as info_resolver
from brkraw.core import config as config_core

from tests.conftest import REAL_HOME
from tests.helpers import SYNTH_MARKERS, isolate_brkraw_env, make_synthetic_study, zip_synthetic_study


# ---------------------------------------------------------------------------
# Environment isolation
# ---------------------------------------------------------------------------


def test_config_home_is_a_temporary_folder():
    root = config_core.resolve_root()
    assert os.environ.get("BRKRAW_CONFIG_HOME") == str(root)
    assert REAL_HOME not in root.parents
    assert root != REAL_HOME / ".brkraw"


def test_home_is_a_temporary_folder():
    assert Path.home() != REAL_HOME
    assert Path.home().is_dir()


def test_no_session_variables_leak_into_tests():
    leaked = [k for k in os.environ if k.startswith("BRKRAW_") and k not in ("BRKRAW_CONFIG_HOME", "BRKRAW_AGENT_FIXTURES")]
    assert leaked == []


def test_isolate_removes_session_variables_and_keeps_fixture_override(monkeypatch, tmp_path):
    monkeypatch.setenv("BRKRAW_PATH", "/somewhere/study")
    monkeypatch.setenv("BRKRAW_SCAN_ID", "3")
    monkeypatch.setenv("BRKRAW_CONVERT_OUTPUT", "/out")
    monkeypatch.setenv("BRKRAW_AGENT_FIXTURES", "/fixtures")
    isolate_brkraw_env(monkeypatch, tmp_path)
    assert "BRKRAW_PATH" not in os.environ
    assert "BRKRAW_SCAN_ID" not in os.environ
    assert "BRKRAW_CONVERT_OUTPUT" not in os.environ
    assert os.environ["BRKRAW_AGENT_FIXTURES"] == "/fixtures"
    assert os.environ["BRKRAW_CONFIG_HOME"] == str(tmp_path / "config")
    assert os.environ["HOME"] == str(tmp_path / "home")
    assert (tmp_path / "home").is_dir()


# ---------------------------------------------------------------------------
# Synthetic PvDataset
# ---------------------------------------------------------------------------


def test_synthetic_study_loads_as_folder_and_zip(tmp_path):
    study = make_synthetic_study(tmp_path / "study", pv="6.0.1", scans={1: "FLASH", 3: "RARE"})
    zipped = zip_synthetic_study(study, tmp_path / "study.zip")
    for src in (study, zipped):
        loader = brkraw.load(str(src))
        assert sorted(loader.avail) == [1, 3]
        info = info_resolver.study(loader) or {}
        assert info["Subject"]["ID"] == SYNTH_MARKERS["subject_id"]
        assert info["Study"]["ID"] == SYNTH_MARKERS["study_name"]


def test_synthetic_study_has_study_scan_and_raw_files(tmp_path):
    study = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={2: "EPI"})
    names = sorted(p.relative_to(study).as_posix() for p in study.rglob("*") if p.is_file())
    assert names == [
        "2/AdjStatePerScan",
        "2/acqp",
        "2/fid",
        "2/method",
        "2/pdata/1/2dseq",
        "2/pdata/1/procs",
        "2/pdata/1/reco",
        "2/pdata/1/visu_pars",
        "AdjStatePerStudy",
        "ScanProgram.scanProgram",
        "subject",
    ]
