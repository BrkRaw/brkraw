"""Context map v3 value rules (b1 bundle B4; BRK-0016, BRK-0021 ... BRK-0024).

Covers test plan v3 groups 1-4 (lookup, value forms, validation, include), the
YAML loader without base-60 numbers, value-level results of the design
examples, and the read-only rule on synthetic data (approved zips: scripts/validate/). Path
templates, utils values, collisions and split slicing are bundle B5.
"""
from __future__ import annotations

import copy
import logging
import textwrap
from pathlib import Path

import pytest

from brkraw.core import config as config_core
from brkraw.specs.context_map import (
    ContextMapError,
    apply_context_map,
    find_context_map,
    load_context_map,
    load_yaml,
    plan_scan,
    resolve_context_map,
    validate_context_map,
)

from tests.helpers import make_synthetic_study

BASE_MAP = """
__meta__:
  name: bids_rodent_base
  version: "0.1.0"
  description: test base
  category: context_map
  layout_template: "sub-{bids.sub}/ses-{bids.ses}/{bids.datatype}/sub-{bids.sub}_{bids.suffix}"
  on_collision: error
bids:
  sub: {from: Subject.ID}
  ses: {from: Session.ID}
  datatype: {from: Method, map: {EPI: func, FieldMap: fmap, RARE: anat, FLASH: anat, MSME: anat}}
  suffix: {from: Method, map: {EPI: bold, RARE: T2w, MSME: MESE, FieldMap: fieldmap}}
  task: {when: {Method: EPI}, value: rest}
convert:
  - {when: {Protocol: {regex: "(?i)tripilot|localizer"}}, value: false}
sidecar:
  TaskName: {from: bids.task}
"""

DATA_MAP = """
__meta__:
  category: context_map
  include: bids_rodent_base
bids:
  sub: "01"
  ses: baseline
  acq: {when: {ScanID: 3}, from: Protocol, map: {T2_TurboRARE: rare}, default: other}
  run:
    - {when: {ScanID: 5}, value: 1}
    - {when: {ScanID: 6}, value: 2}
convert:
  - {when: {ScanID: 7}, value: false}
split:
  when: {ScanID: 8}
  value:
    - {axis: echo, frames: 0, bids: {suffix: magnitude1}}
    - {axis: echo, frames: 1, bids: {suffix: phasediff}}
"""

LAB_COMMON = """
__meta__:
  category: context_map
  layout_template: "{lab.project}/{lab.animal}/{lab.timepoint}/E{lab.scan}_{lab.protocol}[_TE{lab.echo}]"
lab:
  scan: {from: ScanID}
  protocol: {from: Protocol}
convert:
  - {when: {Protocol: {regex: "(?i)tripilot|localizer"}}, value: false}
"""

LAB_DATA = """
__meta__:
  category: context_map
  include: ./lab_common.yaml
lab:
  project: stroke-pilot
  animal: R07
  timepoint: day14
  echo: {when: {ScanID: 7}, from: "TE (ms)"}
sidecar:
  AcquisitionDateTime: null
"""

SMALLEST = """
__meta__:
  category: context_map
  layout_template: "{out.sub}/{out.scan}_{out.protocol}"
out:
  sub: P01
  scan: {from: ScanID}
  protocol: {from: Protocol}
"""

SCANS = {
    1: {"Method": "FLASH", "Protocol": "1_Localizer_TriPilot"},
    3: {"Method": "RARE", "Protocol": "T2_TurboRARE"},
    5: {"Method": "EPI", "Protocol": "rsfMRI_EPI"},
    6: {"Method": "EPI", "Protocol": "rsfMRI_EPI"},
    7: {"Method": "MSME", "Protocol": "MSME_T2map", "TE (ms)": [10.0, 20.0]},
    8: {"Method": "FieldMap", "Protocol": "B0Map"},
}
STUDY = {"Subject": {"ID": "mouse01"}, "Study": {"ID": "S1"}}
METADATA = {"RepetitionTime": 2.0, "EchoTime": 0.01, "AcquisitionDateTime": "x"}


def _info(scan_id):
    info = copy.deepcopy(STUDY)
    info.update(copy.deepcopy(SCANS[scan_id]))
    return info


def _write(folder: Path, name: str, text: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


@pytest.fixture
def installed_base():
    # installed shared maps live in the config folder's context_maps/ (BRK-0038)
    folder = config_core.paths().context_maps_dir
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "bids_rodent_base.yaml").write_text(BASE_MAP, encoding="utf-8")
    return folder


# ---------------------------------------------------------------------------
# YAML loader: no base-60 numbers (BRK-0024)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("frames: 1:30", "1:30"),
        ("frames: 10:20", "10:20"),
        ("frames: 0:100", "0:100"),
        ("frames: 2:100", "2:100"),
        ('frames: "1:30"', "1:30"),
        ("frames: [0, 1]", [0, 1]),
        ("run: 1", 1),
        ("sub: 01", 1),
        ("x: 1.5", 1.5),
        ("t: true", True),
        ("n: null", None),
    ],
)
def test_yaml_loader_reads_colon_numbers_as_text(text, expected):
    data = load_yaml(text)
    assert list(data.values()) == [expected]


def test_yaml_error_is_a_context_map_error():
    with pytest.raises(ContextMapError):
        load_yaml("frames: 5:")


# ---------------------------------------------------------------------------
# Group 1: finding the file
# ---------------------------------------------------------------------------


def test_same_name_lookup_for_folder_zip_and_pvdatasets(tmp_path):
    study = make_synthetic_study(tmp_path / "20240101_mouse01")
    assert find_context_map(study) is None
    yaml_path = _write(tmp_path, "20240101_mouse01.yaml", SMALLEST)
    assert find_context_map(study) == yaml_path
    zipped = tmp_path / "20240101_mouse01.zip"
    zipped.write_bytes(b"")
    assert find_context_map(zipped) == yaml_path
    pv = tmp_path / "M01.PvDatasets"
    pv.write_bytes(b"")
    yml = _write(tmp_path, "M01.yml", SMALLEST)
    assert find_context_map(pv) == yml


def test_both_yaml_and_yml_is_an_error(tmp_path):
    study = make_synthetic_study(tmp_path / "s1")
    _write(tmp_path, "s1.yaml", SMALLEST)
    _write(tmp_path, "s1.yml", SMALLEST)
    with pytest.raises(ContextMapError, match="both"):
        find_context_map(study)


def test_auto_found_file_without_category_is_ignored_with_a_warning(tmp_path, caplog):
    study = make_synthetic_study(tmp_path / "s1")
    _write(tmp_path, "s1.yaml", "out:\n  sub: P01\n")
    with caplog.at_level(logging.WARNING):
        assert resolve_context_map(study) is None
    assert "category" in caplog.text


def test_explicit_file_wins_and_none_turns_lookup_off(tmp_path):
    study = make_synthetic_study(tmp_path / "s1")
    _write(tmp_path, "s1.yaml", SMALLEST)
    other = _write(tmp_path / "maps", "other.yaml", SMALLEST.replace("P01", "P02"))
    assert resolve_context_map(study)["out"]["sub"] == "P01"
    assert resolve_context_map(study, str(other))["out"]["sub"] == "P02"
    assert resolve_context_map(study, None) is None


def test_explicit_file_with_another_category_is_an_error(tmp_path):
    path = _write(tmp_path, "x.yaml", "__meta__: {category: info_spec}\nout: {sub: P01}\n")
    with pytest.raises(ContextMapError, match="category"):
        load_context_map(path)


# ---------------------------------------------------------------------------
# Group 2: value forms and the read-only rule
# ---------------------------------------------------------------------------


def test_four_value_forms_and_first_match(tmp_path):
    path = _write(tmp_path, "m.yaml", """
        __meta__: {category: context_map}
        v:
          direct: "01"
          nothing: null
          literal_list: {value: [1, 2]}
          frm: {from: Subject.ID}
          table: {from: Method, map: {EPI: func}}
          table_default: {from: Method, map: {X: y}, default: other}
          table_no_default: {from: Method, map: {X: y}}
          cond: {when: {ScanID: 5}, value: yes5}
          cond_miss: {when: {ScanID: 9}, value: yes9}
          first:
            - {when: {ScanID: 6}, value: six}
            - {when: {Method: EPI}, value: epi}
            - fallback
    """)
    plan = plan_scan(_info(5), load_context_map(path), scan_id=5)
    assert plan.namespaces["v"] == {
        "direct": "01", "nothing": None, "literal_list": [1, 2], "frm": "mouse01", "table": "func",
        "table_default": "other", "table_no_default": None, "cond": "yes5", "cond_miss": None, "first": "epi",
    }
    assert plan.convert is True and plan.split is None


def test_session_id_defaults_to_study_id(tmp_path):
    path = _write(tmp_path, "m.yaml", "__meta__: {category: context_map}\nv: {ses: {from: Session.ID}}\n")
    assert plan_scan(_info(3), load_context_map(path), scan_id=3).namespaces["v"]["ses"] == "S1"
    info = _info(3)
    info["Session"] = {"ID": "given"}
    assert plan_scan(info, load_context_map(path), scan_id=3).namespaces["v"]["ses"] == "given"


def test_originals_and_metadata_are_never_changed_and_results_are_copies(tmp_path, installed_base):
    data = load_context_map(_write(tmp_path, "20240101_mouse01.yaml", DATA_MAP))
    for scan_id in SCANS:
        info, metadata = _info(scan_id), dict(METADATA)
        before_info, before_meta = copy.deepcopy(info), copy.deepcopy(metadata)
        out = apply_context_map(info, data, scan_id=scan_id)
        side = apply_context_map(info, data, target="metadata_spec", scan_id=scan_id, metadata=metadata)
        assert info == before_info and metadata == before_meta
        assert out is not info and side is not metadata
        assert apply_context_map(info, data, scan_id=scan_id) == out   # same input, same result
    info = _info(7)
    lab = load_context_map(_write(tmp_path / "lab", "R07.yaml", "__meta__: {category: context_map}\nx: {te: {from: 'TE (ms)'}}\n"))
    plan = plan_scan(info, lab, scan_id=7)
    plan.namespaces["x"]["te"].append(99.0)
    assert info["TE (ms)"] == [10.0, 20.0]


def test_apply_keeps_originals_and_adds_namespaces(tmp_path, installed_base):
    data = load_context_map(_write(tmp_path, "20240101_mouse01.yaml", DATA_MAP))
    out = apply_context_map(_info(3), data, scan_id=3)
    assert out["Subject"]["ID"] == "mouse01"
    assert out["bids"]["sub"] == "01" and out["bids"]["acq"] == "rare"
    assert "convert" not in out and "sidecar" not in out and "split" not in out


# ---------------------------------------------------------------------------
# Design examples, value level
# ---------------------------------------------------------------------------


def test_example_1_bids_values(tmp_path, installed_base):
    data = load_context_map(_write(tmp_path, "20240101_mouse01.yaml", DATA_MAP))
    plans = {s: plan_scan(_info(s), data, scan_id=s, metadata=dict(METADATA)) for s in SCANS}
    assert [s for s, p in plans.items() if not p.convert] == [1, 7]
    assert plans[3].namespaces["bids"] == {"sub": "01", "ses": "baseline", "datatype": "anat", "suffix": "T2w",
                                           "task": None, "acq": "rare", "run": None}
    assert plans[5].namespaces["bids"]["run"] == 1 and plans[6].namespaces["bids"]["run"] == 2
    assert plans[5].namespaces["bids"]["task"] == "rest"
    assert plans[5].sidecar == {**METADATA, "TaskName": "rest"}
    assert plans[3].sidecar == METADATA                      # empty TaskName removes the key
    assert plans[8].split == [{"axis": "echo", "frames": 0, "bids": {"suffix": "magnitude1"}},
                              {"axis": "echo", "frames": 1, "bids": {"suffix": "phasediff"}}]
    assert all(plans[s].split is None for s in SCANS if s != 8)
    assert data["__meta__"]["layout_template"].startswith("sub-{bids.sub}")   # inherited from the base


def test_example_2_lab_values(tmp_path):
    _write(tmp_path, "lab_common.yaml", LAB_COMMON)
    data = load_context_map(_write(tmp_path, "R07_day14.yaml", LAB_DATA))
    plans = {s: plan_scan(_info(s), data, scan_id=s, metadata=dict(METADATA)) for s in SCANS}
    assert [s for s, p in plans.items() if not p.convert] == [1]
    assert plans[7].namespaces["lab"] == {"scan": 7, "protocol": "MSME_T2map", "project": "stroke-pilot",
                                          "animal": "R07", "timepoint": "day14", "echo": [10.0, 20.0]}
    assert plans[3].namespaces["lab"]["echo"] is None
    assert "AcquisitionDateTime" not in plans[3].sidecar and plans[3].sidecar["RepetitionTime"] == 2.0


def test_example_3_smallest_values(tmp_path):
    data = load_context_map(_write(tmp_path, "pilot.2024.yaml", SMALLEST))
    plans = {s: plan_scan(_info(s), data, scan_id=s) for s in SCANS}
    assert all(p.convert for p in plans.values())
    assert plans[1].namespaces["out"] == {"sub": "P01", "scan": 1, "protocol": "1_Localizer_TriPilot"}


# ---------------------------------------------------------------------------
# Group 3: validation errors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body, message",
    [
        ("Subject.ID: {value: '01'}", "original value"),
        ("Subject: {ID: '01'}", "original"),
        ("'1bad': {a: 1}", "namespace"),
        ("x: {a: '1', b: {from: x.a}}", "reads only original values"),
        ("x: {a: {value: '1', from: Protocol}}", "either value or from"),
        ("x: {a: {map: {EPI: func}}}", "need from"),
        ("x: {a: {default: z}}", "need from"),
        ("x: {a: {vaule: '1'}}", "unknown word"),
        ("x: {a: {when: {ScanID: 1}}}", "needs value or from"),
        ("x: {a: {type: mapping, values: {A: b}}}", "old context map"),
        ("x: {a: {from: Method, values: {A: b}}}", "old context map"),
        ("x: {a: {cases: []}}", "old context map"),
        ("x: {a: {selector: true, value: 1}}", "old context map"),
        ("__split__: {value: []}", "old context map"),
        ("utils: {counter: 1}", "utils"),
        ("x: {a: {from: utils.counter}}", "utils"),
        ("convert: {when: {utils.split: 1}, value: false}", "utils"),
        ("sidecar: {A: {from: utils.slicepack}}", "utils"),
        ("x: {a: {when: {Method: {gt: 3}}, value: 1}}", "condition operator"),
    ],
)
def test_validation_errors(tmp_path, body, message):
    path = _write(tmp_path, "bad.yaml", "__meta__: {category: context_map}\n" + body + "\n")
    with pytest.raises(ContextMapError, match=message):
        load_context_map(path)


@pytest.mark.parametrize(
    "meta, message",
    [
        ("{category: context_map, slicepack_suffix: _sp}", "slicepack_suffix"),
        ("{category: context_map, layout_entries: []}", "old context map"),
        ("{category: context_map, include_mode: strict}", "old context map"),
        ("{category: context_map, colour: red}", "unknown __meta__"),
        ("{category: context_map, on_collision: counter}", "on_collision"),
        ("{category: context_map, layout_template: '{x.a}/{Protocol}'}", "Protocol"),
        ("{category: context_map, layout_template: '{x.a}/{utils.nope}'}", "utils.nope"),
    ],
)
def test_meta_validation_errors(tmp_path, meta, message):
    path = _write(tmp_path, "bad.yaml", f"__meta__: {meta}\nx: {{a: '1'}}\n")
    with pytest.raises(ContextMapError, match=message):
        load_context_map(path)


def test_template_may_use_utils_values(tmp_path):
    path = _write(tmp_path, "ok.yaml", "__meta__: {category: context_map, layout_template: "
                                       "'{x.a}[_sp{utils.slicepack}][_part{utils.split}]_{utils.counter}'}\nx: {a: '1'}\n")
    assert load_context_map(path)["x"]["a"] == "1"


def test_validate_context_map_accepts_a_good_file_and_a_mapping(tmp_path):
    path = _write(tmp_path, "ok.yaml", SMALLEST)
    validate_context_map(path)
    validate_context_map(load_yaml(SMALLEST))
    with pytest.raises(ContextMapError):
        validate_context_map({"__meta__": {"category": "context_map"}, "Subject": {"ID": "x"}})


# ---------------------------------------------------------------------------
# Group 4: include
# ---------------------------------------------------------------------------


def test_include_by_installed_name_prepends_per_field_and_keeps_base_fields(tmp_path, installed_base):
    data = load_context_map(_write(tmp_path, "20240101_mouse01.yaml", DATA_MAP))
    assert data["bids"]["sub"] == ["01", {"from": "Subject.ID"}]
    assert data["bids"]["datatype"] == {"from": "Method", "map": {"EPI": "func", "FieldMap": "fmap", "RARE": "anat",
                                                               "FLASH": "anat", "MSME": "anat"}}
    assert data["convert"][0] == {"when": {"ScanID": 7}, "value": False}
    assert data["convert"][1]["value"] is False
    meta = data["__meta__"]
    assert meta["on_collision"] == "error" and "layout_template" in meta
    assert "include" not in meta and "name" not in meta and "version" not in meta


def test_include_pinned_version_and_missing_names(tmp_path, installed_base):
    ok = _write(tmp_path, "a.yaml", "__meta__: {category: context_map, include: {use: bids_rodent_base, "
                                    "version: '0.1.0'}}\nbids: {sub: '02'}\n")
    assert load_context_map(ok)["bids"]["sub"][0] == "02"
    missing_version = _write(tmp_path, "b.yaml", "__meta__: {category: context_map, include: {use: "
                                                 "bids_rodent_base, version: '9.9.9'}}\n")
    with pytest.raises(ContextMapError, match="9.9.9"):
        load_context_map(missing_version)
    missing_name = _write(tmp_path, "c.yaml", "__meta__: {category: context_map, include: no_such_map}\n")
    with pytest.raises(ContextMapError, match="no_such_map"):
        load_context_map(missing_name)


def test_include_by_relative_path_and_circular_include(tmp_path):
    _write(tmp_path, "lab_common.yaml", LAB_COMMON)
    data = load_context_map(_write(tmp_path, "R07_day14.yaml", LAB_DATA))
    assert data["lab"]["scan"] == {"from": "ScanID"} and data["lab"]["project"] == "stroke-pilot"
    _write(tmp_path, "cyc_a.yaml", "__meta__: {category: context_map, include: ./cyc_b.yaml}\nx: {a: '1'}\n")
    _write(tmp_path, "cyc_b.yaml", "__meta__: {category: context_map, include: ./cyc_a.yaml}\nx: {b: '2'}\n")
    with pytest.raises(ContextMapError, match="circular"):
        load_context_map(tmp_path / "cyc_a.yaml")


# ---------------------------------------------------------------------------
# Public API path (BRK-0020: brkraw.api.addon removed)
# ---------------------------------------------------------------------------


def test_public_api_name():
    import brkraw.api as api

    assert api.context_map.load_context_map is load_context_map
    with pytest.raises(AttributeError):
        api.addon  # noqa: B018
