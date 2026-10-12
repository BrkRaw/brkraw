"""convert with context map v3 output, --axis/--frames, legacy cycle options, info frame axes
(b1 bundle B5). Synthetic data only (echo/cycle frame groups); the checks on approved
zips are manual checks in scripts/validate/."""
from __future__ import annotations

import json
import logging
import shutil
import warnings
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest
import yaml

import brkraw
from brkraw.cli.main import main

from tests.helpers import make_synthetic_study

SCANS = {3: "RARE", 5: "EPI", 6: "EPI", 8: "FieldMap"}
FRAMES = {5: [("FG_CYCLE", 3)], 6: [("FG_CYCLE", 3)], 8: [("FG_ECHO", 2)]}

BIDS_MAP = {
    "__meta__": {
        "category": "context_map",
        "layout_template": "sub-{bids.sub}/ses-{bids.ses}/{bids.datatype}/"
                           "sub-{bids.sub}_ses-{bids.ses}[_task-{bids.task}][_run-{bids.run}]_{bids.suffix}",
    },
    "bids": {
        "sub": "01",
        "ses": "baseline",
        "datatype": {"from": "MethodBase", "map": {"EPI": "func", "RARE": "anat", "FieldMap": "fmap"}},
        "suffix": {"from": "MethodBase", "map": {"EPI": "bold", "RARE": "T2w", "FieldMap": "fieldmap"}},
        "task": {"when": {"MethodBase": "EPI"}, "value": "rest"},
        "run": [{"when": {"ScanID": 5}, "value": 1}, {"when": {"ScanID": 6}, "value": 2}],
    },
    "split": {
        "when": {"ScanID": 8},
        "value": [
            {"axis": "echo", "frames": 0, "bids": {"suffix": "magnitude1"}},
            {"axis": "echo", "frames": 1, "bids": {"suffix": "phasediff"}, "sidecar": {"EchoNumber": 2}},
        ],
    },
    "sidecar": {"TaskName": {"from": "bids.task"}},
}
P = "sub-01/ses-baseline"
EXPECTED = {
    f"{P}/anat/sub-01_ses-baseline_T2w.nii.gz",
    f"{P}/func/sub-01_ses-baseline_task-rest_run-1_bold.nii.gz",
    f"{P}/func/sub-01_ses-baseline_task-rest_run-2_bold.nii.gz",
    f"{P}/fmap/sub-01_ses-baseline_magnitude1.nii.gz",
    f"{P}/fmap/sub-01_ses-baseline_phasediff.nii.gz",
}


@pytest.fixture
def study(tmp_path):
    return make_synthetic_study(tmp_path / "data" / "20240101_mouse01", pv="360.3.3", scans=SCANS, frames=FRAMES)


def _map(study: Path, data: dict, name: str = None) -> Path:
    path = study.parent / (name or f"{study.name}.yaml")
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _niis(out: Path):
    return {p.relative_to(out).as_posix() for p in out.rglob("*.nii.gz")}


def _data(path: Path) -> np.ndarray:
    return np.asarray(nib.load(str(path)).dataobj)


def _full(study: Path, scan_id: int) -> np.ndarray:
    return np.asarray(brkraw.load(str(study)).get_dataobj(scan_id, 1))


# ---------------------------------------------------------------------------
# Context map output
# ---------------------------------------------------------------------------


def test_same_name_map_gives_the_designed_paths_and_split_data(study, tmp_path):
    _map(study, BIDS_MAP)
    out = tmp_path / "out"
    assert main(["convert", str(study), "-o", str(out), "-c"]) == 0
    assert _niis(out) == EXPECTED
    full = _full(study, 8)
    assert np.array_equal(_data(out / P / "fmap" / "sub-01_ses-baseline_magnitude1.nii.gz"), full[..., 0])
    assert np.array_equal(_data(out / P / "fmap" / "sub-01_ses-baseline_phasediff.nii.gz"), full[..., 1])
    side_bold = json.loads((out / P / "func" / "sub-01_ses-baseline_task-rest_run-1_bold.json").read_text())
    side_t2 = json.loads((out / P / "anat" / "sub-01_ses-baseline_T2w.json").read_text())
    side_pd = json.loads((out / P / "fmap" / "sub-01_ses-baseline_phasediff.json").read_text())
    assert side_bold["TaskName"] == "rest"
    assert "TaskName" not in side_t2
    assert side_pd["EchoNumber"] == 2


def test_convert_false_skips_scans(study, tmp_path):
    data = dict(BIDS_MAP, convert=[{"when": {"ScanID": 3}, "value": False}])
    _map(study, data)
    out = tmp_path / "out"
    assert main(["convert", str(study), "-o", str(out)]) == 0
    assert not any("anat" in p for p in _niis(out))


def test_explicit_map_and_no_context_map(study, tmp_path):
    _map(study, BIDS_MAP)
    other = dict(BIDS_MAP, bids=dict(BIDS_MAP["bids"], sub="02"))
    explicit = _map(study, other, name="other.yaml")
    out = tmp_path / "a"
    assert main(["convert", str(study), "-o", str(out), "-M", str(explicit)]) == 0
    assert all(p.startswith("sub-02/") for p in _niis(out))
    plain = tmp_path / "b"
    assert main(["convert", str(study), "-o", str(plain), "--no-context-map"]) == 0
    names = _niis(plain)
    # config layout: flat file names, no map folders
    assert len(names) == 4 and not any("/" in p for p in names)


def test_collision_is_an_error_by_default_and_nothing_is_written(study, tmp_path, caplog):
    data = dict(BIDS_MAP, bids={k: v for k, v in BIDS_MAP["bids"].items() if k != "run"})
    _map(study, data)
    out = tmp_path / "out"
    with caplog.at_level(logging.ERROR):
        assert main(["convert", str(study), "-o", str(out)]) == 2
    assert "scan 6" in caplog.text and "scan 5" in caplog.text
    # nothing at all: no NIfTI, no sidecar, no folder content
    assert not out.exists() or not any(p.is_file() for p in out.rglob("*"))


def test_collision_with_existing_files_and_suffix_mode(study, tmp_path, caplog):
    _map(study, BIDS_MAP)
    out = tmp_path / "out"
    assert main(["convert", str(study), "-o", str(out)]) == 0
    with caplog.at_level(logging.ERROR):
        assert main(["convert", str(study), "-o", str(out)]) == 2
    assert "already exists" in caplog.text
    data = dict(BIDS_MAP, __meta__=dict(BIDS_MAP["__meta__"], on_collision="suffix"))
    _map(study, data)
    assert main(["convert", str(study), "-o", str(out)]) == 0
    assert f"{P}/anat/sub-01_ses-baseline_T2w_2.nii.gz" in _niis(out)


def test_split_without_distinct_names_collides_and_names_the_tag(study, tmp_path, caplog):
    data = dict(BIDS_MAP, split={"when": {"ScanID": 8}, "value": [{"axis": "echo", "frames": 0},
                                                                    {"axis": "echo", "frames": 1}]})
    _map(study, data)
    with caplog.at_level(logging.ERROR):
        assert main(["convert", str(study), "-o", str(tmp_path / "out")]) == 2
    assert "utils.split" in caplog.text


def test_utils_values_in_the_template(study, tmp_path):
    data = {
        "__meta__": {"category": "context_map", "layout_template": "{x.sub}/E{x.scan}[_sp{utils.slicepack}][_part{utils.split}]"},
        "x": {"sub": "P01", "scan": {"from": "ScanID"}},
        "split": {"when": {"ScanID": 8}, "value": [{"axis": "echo", "frames": 0}, {"axis": "echo", "frames": 1}]},
    }
    _map(study, data)
    out = tmp_path / "out"
    assert main(["convert", str(study), "-o", str(out)]) == 0
    assert _niis(out) == {"P01/E3.nii.gz", "P01/E5.nii.gz", "P01/E6.nii.gz", "P01/E8_part1.nii.gz", "P01/E8_part2.nii.gz"}
    counter = {"__meta__": {"category": "context_map", "layout_template": "{x.sub}/img_{utils.counter}"},
               "x": {"sub": "P01"}}
    _map(study, counter)
    out2 = tmp_path / "out2"
    assert main(["convert", str(study), "-o", str(out2)]) == 0
    assert _niis(out2) == {f"P01/img_{n}.nii.gz" for n in (1, 2, 3, 4)}


def test_utils_slicepack_numbers_packs_before_split_parts(tmp_path):
    # scan 4: two slice packs; scan 9: two slice packs x echo 2, split by echo
    st = make_synthetic_study(tmp_path / "data" / "packs", pv="360.3.3", scans={4: "RARE", 9: "FieldMap"},
                              frames={9: [("FG_ECHO", 2)]}, packs={4: 2, 9: 2})
    _map(st, {
        "__meta__": {"category": "context_map", "layout_template": "E{x.scan}[_sp{utils.slicepack}][_part{utils.split}]"},
        "x": {"scan": {"from": "ScanID"}},
        "split": {"when": {"ScanID": 9}, "value": [{"axis": "echo", "frames": 0}, {"axis": "echo", "frames": 1}]},
    })
    out = tmp_path / "out"
    assert main(["convert", str(st), "-o", str(out)]) == 0
    assert _niis(out) == {"E4_sp1.nii.gz", "E4_sp2.nii.gz", "E9_sp1_part1.nii.gz", "E9_sp1_part2.nii.gz",
                          "E9_sp2_part1.nii.gz", "E9_sp2_part2.nii.gz"}
    packs = brkraw.load(str(st)).get_dataobj(9, 1)
    for sp in (1, 2):
        for part in (1, 2):
            got = _data(out / f"E9_sp{sp}_part{part}.nii.gz")
            assert np.array_equal(got, np.asarray(packs[sp - 1])[..., part - 1])


def test_existing_sidecar_is_a_collision_and_is_not_overwritten(study, tmp_path, caplog):
    _map(study, BIDS_MAP)
    out = tmp_path / "out"
    assert main(["convert", str(study), "-o", str(out), "-c"]) == 0
    side = out / P / "anat" / "sub-01_ses-baseline_T2w.json"
    side.write_text('{"mine": 1}', encoding="utf-8")
    for nii in out.rglob("*.nii.gz"):
        nii.unlink()
    with caplog.at_level(logging.ERROR):
        assert main(["convert", str(study), "-o", str(out), "-c"]) == 2
    assert "already exists" in caplog.text
    assert side.read_text(encoding="utf-8") == '{"mine": 1}'
    assert _niis(out) == set()


def test_split_without_template_checks_one_axis_and_notes_missing_frames(tmp_path, caplog):
    st = make_synthetic_study(tmp_path / "data" / "two", pv="360.3.3", scans={9: "FieldMap"},
                              frames={9: [("FG_ECHO", 2), ("FG_CYCLE", 3)]})
    mixed = {"__meta__": {"category": "context_map"},
             "split": {"when": {"ScanID": 9}, "value": [{"axis": "echo", "frames": 0}, {"axis": "cycle", "frames": 0}]}}
    _map(st, mixed)
    out = tmp_path / "out"
    with caplog.at_level(logging.ERROR):
        assert main(["convert", str(st), "-o", str(out)]) == 2
    assert "same axis" in caplog.text
    assert not out.exists() or _niis(out) == set()
    caplog.clear()
    partial = {"__meta__": {"category": "context_map"},
               "split": {"when": {"ScanID": 9}, "value": [{"axis": "cycle", "frames": 0}]}}
    _map(st, partial)
    with caplog.at_level(logging.INFO):
        assert main(["convert", str(st), "-o", str(tmp_path / "out2")]) == 0
    assert "in no part" in caplog.text


def test_metadata_rules_do_not_depend_on_sidecar_option(study, tmp_path):
    # AcquisitionDateTime is a sidecar (metadata) field, not scan info; the
    # metadata spec comes with `brkraw init` (the test config home starts empty)
    assert main(["init", "--yes", "--install-default"]) == 0
    meta = brkraw.load(str(study)).get_metadata(3, reco_id=1) or {}
    assert meta.get("AcquisitionDateTime") == "2024-03-15T10:10:10,123-0400"
    assert "AcquisitionDateTime" not in brkraw.load(str(study)).info(scope="scan", as_dict=True).get(3, {})
    data = {"__meta__": {"category": "context_map", "layout_template": "E{x.scan}"},
            "x": {"scan": {"from": "ScanID"}},
            "convert": [{"when": {"ScanID": 3, "AcquisitionDateTime": "2024-03-15T10:10:10,123-0400"},
                         "value": False}]}
    _map(study, data)
    for extra in ([], ["-c"]):
        out = tmp_path / ("out" + "".join(extra))
        assert main(["convert", str(study), "-o", str(out)] + extra) == 0
        assert _niis(out) == {"E5.nii.gz", "E6.nii.gz", "E8.nii.gz"}, extra
    # the same rule without a layout_template (config layout path)
    data["__meta__"] = {"category": "context_map"}
    _map(study, data)
    out = tmp_path / "plain"
    assert main(["convert", str(study), "-o", str(out)]) == 0
    assert len(_niis(out)) == 3 and not any("scan-3_" in p for p in _niis(out))


def test_method_base_without_vendor_prefix(study):
    from brkraw.apps.loader.info.transform import strip_method_prefix
    from brkraw.core import layout as layout_core

    info, _ = layout_core.load_layout_info_parts(brkraw.load(str(study)), 5, reco_id=1)
    assert info["Method"] == "Bruker:EPI"
    assert info["MethodBase"] == "EPI"
    assert strip_method_prefix("User:zte_mjm_anatomical") == "zte_mjm_anatomical"
    assert strip_method_prefix("FLASH") == "FLASH"
    assert strip_method_prefix("Unknown") == "Unknown"


def test_bad_map_stops_with_a_clear_message(study, tmp_path, caplog):
    _map(study, {"__meta__": {"category": "context_map"}, "Subject.ID": {"value": "01"}})
    with caplog.at_level(logging.ERROR):
        assert main(["convert", str(study), "-o", str(tmp_path / "out")]) == 2
    assert "original value" in caplog.text


def test_old_context_map_variable_is_not_read(study, tmp_path, monkeypatch):
    monkeypatch.setenv("BRKRAW_CONVERT_CONTEXT_MAP", str(tmp_path / "missing.yaml"))
    out = tmp_path / "out"
    assert main(["convert", str(study), "-o", str(out)]) == 0
    assert len(_niis(out)) == 4


def test_session_no_longer_knows_the_context_map_option(capsys):
    assert main(["session", "set", "--convert-option", "CONTEXT_MAP=x.yaml"]) == 2
    assert "CONTEXT_MAP" in capsys.readouterr().out


def test_batch_uses_each_datasets_own_map(tmp_path):
    folder = tmp_path / "studies"
    a = make_synthetic_study(folder / "A", pv="360.3.3", scans={3: "RARE"})
    make_synthetic_study(folder / "B", pv="360.3.3", scans={3: "RARE"})
    _map(a, {"__meta__": {"category": "context_map", "layout_template": "{x.sub}/{x.scan}"},
             "x": {"sub": "fromA", "scan": {"from": "ScanID"}}})
    out = tmp_path / "out"
    assert main(["convert", str(folder), "--batch", "-o", str(out)]) == 0
    names = _niis(out)
    assert "fromA/3.nii.gz" in names and len(names) == 2


# ---------------------------------------------------------------------------
# --axis / --frames and the legacy cycle options (BRK-0032 ①)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "extra, index",
    [
        (["--axis", "cycle", "--frames", "1:3"], (Ellipsis, slice(1, 3))),
        (["--frames", "0"], (Ellipsis, 0)),
        (["--frames", "2,0"], (Ellipsis, [2, 0])),
    ],
)
def test_axis_and_frames_select_frames(study, tmp_path, extra, index):
    out = tmp_path / "o.nii.gz"
    assert main(["convert", str(study), "-s", "5", "-o", str(out), "--no-context-map"] + extra) == 0
    assert np.array_equal(_data(out), _full(study, 5)[index])


def test_axis_on_data_without_frame_axis_is_an_error(study, tmp_path, caplog):
    with caplog.at_level(logging.ERROR):
        assert main(["convert", str(study), "-s", "3", "-o", str(tmp_path / "o.nii.gz"), "--axis", "echo", "--frames", "0"]) == 2
    assert "no frame axis" in caplog.text


def test_legacy_cycle_options_still_work_with_a_warning(study, tmp_path, caplog):
    out = tmp_path / "o.nii.gz"
    with caplog.at_level(logging.WARNING):
        assert main(["convert", str(study), "-s", "5", "-o", str(out), "--cycle-index", "1", "--cycle-count", "2"]) == 0
    assert "deprecated" in caplog.text and "--axis cycle --frames" in caplog.text
    assert np.array_equal(_data(out), _full(study, 5)[..., 1:3])


def test_legacy_and_new_options_together_are_refused(study, tmp_path):
    assert main(["convert", str(study), "-s", "5", "-o", str(tmp_path / "o.nii.gz"),
                 "--cycle-index", "1", "--frames", "0"]) == 2


def test_python_api_axis_frames_and_legacy_warning(study):
    loader = brkraw.load(str(study))
    full = np.asarray(loader.get_dataobj(8, 1))
    assert np.array_equal(loader.get_dataobj(8, 1, axis="echo", frames=[1, 0]), full[..., [1, 0]])
    assert loader.get_dataobj(8, 1, frames=1).shape == full.shape[:3]
    with pytest.warns(DeprecationWarning, match="axis"):
        part = loader.get_dataobj(5, 1, cycle_index=1, cycle_count=1)
    assert np.array_equal(part, np.asarray(brkraw.load(str(study)).get_dataobj(5, 1))[..., 1:2])


# ---------------------------------------------------------------------------
# info shows frame axes (BRK-0032 decision 5)
# ---------------------------------------------------------------------------


def test_info_shows_frame_axes(study, capsys):
    loader = brkraw.load(str(study))
    info = loader.info(scope="scan", as_dict=True, show_reco=True)
    scans = info["Scan(s)"] if "Scan(s)" in info else info
    recos = {sid: entry.get("Reco(s)", {}) for sid, entry in scans.items()}
    assert recos[8][1]["Frame axes"] == "echo(2)"
    assert recos[5][1]["Frame axes"] == "cycle(3)"
    assert "Frame axes" not in recos[3][1]
