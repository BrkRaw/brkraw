"""Docs examples and small CLI points documented in b1 bundle B6. Synthetic data only."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import brkraw
from brkraw.cli.main import main

from tests.helpers import make_synthetic_study

DOCS = Path(__file__).resolve().parents[2] / "docs"


def _block(page: Path, marker: str) -> str:
    """The fenced block right after `<!-- example: MARKER -->` in a docs page."""
    text = page.read_text(encoding="utf-8")
    m = re.search(r"<!-- example: " + re.escape(marker) + r" -->\s*```\w*\n(.*?)```", text, flags=re.S)
    assert m, f"example {marker} not found in {page.name}"
    return m.group(1)


def test_bids_page_example_gives_the_documented_paths(tmp_path):
    page = DOCS / "getting-started" / "bids.md"
    study = make_synthetic_study(
        tmp_path / "data" / "20240101_mouse01", pv="360.3.3",
        scans={1: "Localizer", 3: "RARE", 5: "EPI", 6: "EPI", 8: "FieldMap"},
        frames={5: [("FG_CYCLE", 3)], 6: [("FG_CYCLE", 3)], 8: [("FG_ECHO", 2)]},
    )
    (study.parent / "20240101_mouse01.yaml").write_text(_block(page, "bids-context-map"), encoding="utf-8")
    out = tmp_path / "bids"
    assert main(["convert", str(study), "-o", str(out), "-c"]) == 0
    expected = {line.strip() for line in _block(page, "bids-paths").splitlines() if line.strip()}
    got = {p.relative_to(out).as_posix() for p in out.rglob("*.nii.gz")}
    assert got == expected
    for rel in expected:
        assert (out / rel.replace(".nii.gz", ".json")).is_file()


def test_config_path_knows_pruner_specs(tmp_path, capsys):
    assert main(["config", "--root", str(tmp_path / "cfg"), "path", "pruner_specs"]) == 0
    assert capsys.readouterr().out.strip().endswith("pruner_specs")


def test_api_layout_example_runs(tmp_path):
    from brkraw.api import layout

    study = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={3: "RARE"}, packs={3: 2})
    loader = brkraw.load(str(study))
    name = layout.render_layout(
        loader, 3, reco_id=1,
        layout_entries=[{"key": "Study.ID", "entry": "study", "sep": "/"},
                        {"key": "Subject.ID", "entry": "sub", "sep": "/"},
                        {"key": "Protocol", "hide": True}],
    )
    assert name.count("/") == 2 and name.startswith("study-")
    info, metadata = layout.load_layout_info_parts(loader, 3, reco_id=1)
    assert info["MethodBase"] == "RARE" and metadata == {}
    suffixes = layout.render_slicepack_suffixes(layout.load_layout_info(loader, 3, reco_id=1), count=2,
                                                template="_slpack{index}")
    assert suffixes == ["_slpack1", "_slpack2"]
