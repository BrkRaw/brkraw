"""prune 0.6.0 design (b1 bundle B3; BRK-0030, BRK-0031, BRK-0032). Synthetic data only
(the byte-identical prune of approved zips is a manual check, scripts/validate/)."""
from __future__ import annotations

import logging
import re
import zipfile
from pathlib import Path

import pytest
import yaml

from brkraw.cli.main import main
from brkraw.specs.pruner import prune_dataset_to_zip, select_files

from tests.helpers import SYNTH_MARKERS, make_synthetic_study, zip_synthetic_study

ANON_FILES = {"subject", "acqp", "method", "reco", "visu_pars", "2dseq"}


def _study(tmp_path: Path, scans=None) -> Path:
    return make_synthetic_study(tmp_path / "data" / SYNTH_MARKERS["folder"], pv="360.3.3",
                                scans=scans or {1: "FLASH", 3: "RARE"})


def _files(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _zip(path: Path):
    with zipfile.ZipFile(path) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        tops = {n.split("/", 1)[0] for n in names}
        data = {n.split("/", 1)[1]: zf.read(n) for n in names}
    return tops, data


@pytest.fixture
def cwd(tmp_path, monkeypatch):
    out = tmp_path / "work"
    out.mkdir()
    monkeypatch.chdir(out)
    return out


# ---------------------------------------------------------------------------
# Default: the whole study, values unchanged
# ---------------------------------------------------------------------------


def test_default_copies_every_file_unchanged(tmp_path, cwd):
    study = _study(tmp_path)
    assert main(["prune", str(study)]) == 0
    out = cwd / f"pruned_{study.name}.zip"
    tops, data = _zip(out)
    assert tops == {study.name}
    assert data == _files(study)


def test_default_from_zip_input(tmp_path, cwd):
    study = _study(tmp_path)
    zipped = zip_synthetic_study(study, tmp_path / "data" / "study.zip")
    assert main(["prune", str(zipped)]) == 0
    tops, data = _zip(cwd / "pruned_study.zip")
    assert tops == {SYNTH_MARKERS["folder"]}
    assert data == _files(study)


def test_scan_and_reco_choice_keeps_every_file_of_them_and_study_files(tmp_path, cwd):
    study = _study(tmp_path)
    assert main(["prune", str(study), "-s", "3", "-r", "1", "-o", "o.zip"]) == 0
    _, data = _zip(cwd / "o.zip")
    expected = {k: v for k, v in _files(study).items() if not k.startswith("1/")}
    assert data == expected
    assert {"subject", "AdjStatePerStudy", "ScanProgram.scanProgram", "3/fid", "3/AdjStatePerScan"} <= set(data)


def test_output_option_changes_only_the_file_name(tmp_path, cwd):
    study = _study(tmp_path)
    assert main(["prune", str(study), "-o", "other.zip"]) == 0
    tops, _ = _zip(cwd / "other.zip")
    assert tops == {study.name}


def test_without_path_uses_brkraw_path_but_not_its_scan_ids(tmp_path, cwd, monkeypatch):
    study = _study(tmp_path)
    monkeypatch.setenv("BRKRAW_PATH", str(study))
    monkeypatch.setenv("BRKRAW_SCAN_ID", "1")
    monkeypatch.setenv("BRKRAW_RECO_ID", "1")
    assert main(["prune"]) == 0
    _, data = _zip(cwd / f"pruned_{study.name}.zip")
    assert data == _files(study)


def test_without_any_path_prints_help(cwd):
    assert main(["prune"]) == 2


def test_library_default_is_the_whole_dataset(tmp_path):
    study = _study(tmp_path)
    out = prune_dataset_to_zip(study, tmp_path / "o.zip")
    assert _zip(out)[1] == _files(study)
    assert select_files(study) == sorted(_files(study))
    assert select_files(study, dirs=[{"level": 1, "dirs": ["3"]}]) == sorted(
        k for k in _files(study) if not k.startswith("1/"))


# ---------------------------------------------------------------------------
# --files / --exclude-files, --mode gone
# ---------------------------------------------------------------------------


def test_files_keeps_only_named_files(tmp_path, cwd):
    study = _study(tmp_path)
    assert main(["prune", str(study), "--files", "subject", "acqp", "-o", "o.zip"]) == 0
    assert set(_zip(cwd / "o.zip")[1]) == {"subject", "1/acqp", "3/acqp"}


def test_exclude_files_drops_named_files(tmp_path, cwd):
    study = _study(tmp_path)
    assert main(["prune", str(study), "--exclude-files", "fid", "-o", "o.zip"]) == 0
    assert set(_zip(cwd / "o.zip")[1]) == {k for k in _files(study) if not k.endswith("/fid")}


def test_files_and_exclude_files_together_are_refused(tmp_path, cwd):
    study = _study(tmp_path)
    with pytest.raises(SystemExit):
        main(["prune", str(study), "--files", "acqp", "--exclude-files", "fid"])


def test_mode_option_is_gone(tmp_path, cwd):
    with pytest.raises(SystemExit):
        main(["prune", str(_study(tmp_path)), "--mode", "keep"])


# ---------------------------------------------------------------------------
# --institution
# ---------------------------------------------------------------------------


def _param(text: str, key: str) -> str:
    m = re.search(r"^##\$" + re.escape(key) + r"=(.*?)(?=^##)", text, flags=re.M | re.S)
    return m.group(1).strip() if m else None


def test_institution_replaces_existing_fields_only(tmp_path, cwd):
    study = _study(tmp_path)
    name = "Example University of a Rather Long Name, Department of Imaging"
    assert main(["prune", str(study), "--institution", name, "-o", "o.zip"]) == 0
    _, data = _zip(cwd / "o.zip")
    original = _files(study)
    for rel, key in (("subject", "SUBJECT_institution"), ("1/acqp", "ACQ_institution"),
                     ("3/pdata/1/visu_pars", "VisuInstitution")):
        value = _param(data[rel].decode("utf-8"), key)
        size, text = re.match(r"\(\s*(\d+)\s*\)\s*<(.*)>", value, flags=re.S).groups()
        assert text == name
        assert int(size) >= len(name) + 1
    assert "ACQ_institution" not in data["1/method"].decode("utf-8")
    assert data["1/method"] == original["1/method"]
    assert data["3/fid"] == original["3/fid"]


# ---------------------------------------------------------------------------
# --anonymize and the example spec
# ---------------------------------------------------------------------------


def test_anonymize_default_name_top_folder_files_and_values(tmp_path, cwd):
    study = _study(tmp_path)
    assert main(["prune", str(study), "--anonymize", "--subject-id", "M01", "--study-id", "S1"]) == 0
    out = cwd / "pruned_anon_M01_S1.zip"
    tops, data = _zip(out)
    assert tops == {"M01"}
    assert {rel.split("/")[-1] for rel in data} == ANON_FILES
    subject = data["subject"].decode("utf-8")
    assert _param(subject, "SUBJECT_id") == "<M01>"
    assert _param(subject, "SUBJECT_study_name") == "<S1>"
    visu = data["3/pdata/1/visu_pars"].decode("utf-8")
    assert _param(visu, "VisuSubjectId") == "<M01>"
    assert _param(visu, "VisuStudyId") == "<S1>"
    # the example spec changes or removes every synthetic identifying value
    with zipfile.ZipFile(out) as zf:
        for member in zf.namelist():
            blob = member.encode() + (b"" if member.endswith("/") else zf.read(member))
            for key, marker in SYNTH_MARKERS.items():
                assert marker.encode() not in blob, (member, key)
    record = yaml.safe_load((cwd / "pruned_anon_M01_S1.prune.yaml").read_text(encoding="utf-8"))
    assert "input_name" not in record


def test_anonymized_copy_can_be_read_back_by_brkraw(tmp_path, cwd):
    # The example spec removes every date; study info must still load (Study.Date empty).
    import brkraw
    from brkraw.apps.loader import info as info_resolver
    from brkraw.apps.loader.info.transform import unixtime_to_datetime

    assert main(["prune", str(_study(tmp_path)), "--anonymize", "--subject-id", "M01", "-o", "a.zip"]) == 0
    info = info_resolver.study(brkraw.load(str(cwd / "a.zip"))) or {}
    assert info["Subject"]["ID"] == "M01"
    assert info["Study"]["Date"] is None
    assert unixtime_to_datetime(None) is None


def test_anonymize_defaults_to_anon_ids(tmp_path, cwd):
    assert main(["prune", str(_study(tmp_path)), "--anonymize"]) == 0
    assert (cwd / "pruned_anon_anon_anon.zip").is_file()


def test_builtin_anonymize_spec_found_by_name_without_install(tmp_path, cwd):
    assert main(["prune", str(_study(tmp_path)), "--spec", "anonymize", "--subject-id", "A"]) == 0
    assert (cwd / "pruned_anon_A_anon.zip").is_file()


def test_anonymize_keeps_institution_when_asked(tmp_path, cwd):
    study = _study(tmp_path)
    assert main(["prune", str(study), "--anonymize", "--institution", "Example U", "-o", "o.zip"]) == 0
    _, data = _zip(cwd / "o.zip")
    assert "<Example U>" in _param(data["3/pdata/1/visu_pars"].decode("utf-8"), "VisuInstitution")


def test_anonymize_and_spec_together_are_refused(tmp_path, cwd):
    with pytest.raises(SystemExit):
        main(["prune", str(_study(tmp_path)), "--anonymize", "--spec", "anonymize"])


def test_old_deid4share_spec_is_gone(tmp_path, cwd):
    assert main(["prune", str(_study(tmp_path)), "--spec", "deid4share"]) == 2


def test_example_spec_suggestions_are_comments(tmp_path):
    from importlib import resources

    try:
        resources.files  # type: ignore[attr-defined]
    except AttributeError:  # Python 3.8
        import importlib_resources as resources  # type: ignore[no-redef]

    text = resources.files("brkraw.default").joinpath("pruner_specs/anonymize.yaml").read_text(encoding="utf-8")
    spec = yaml.safe_load(text)
    assert spec["__meta__"]["name"] == "anonymize"
    for key in ("ACQ_protocol_name", "ACQ_scan_name", "RecoRegridNTrajFile", "RecoStageNodes",
                "VisuAcquisitionProtocol", "VisuSeriesReferences"):
        assert f"# suggest: {key}" in text
        assert all(key not in (spec["update_params"].get(f) or {}) for f in spec["update_params"])
    assert spec["update_params"]["method"]["PVM_StudyB0Map"] is None


# ---------------------------------------------------------------------------
# Placeholders (J)
# ---------------------------------------------------------------------------


def _spec(tmp_path: Path, **extra) -> Path:
    spec = {"__meta__": {"name": "t", "version": "1.0.0", "description": "uses $Project", "category": "pruner_spec"},
            "files": ["subject", "acqp"]}
    spec.update(extra)
    path = tmp_path / "t.yaml"
    path.write_text(yaml.safe_dump(spec), encoding="utf-8")
    return path


def test_unfilled_placeholder_stops_and_writes_nothing(tmp_path, cwd, caplog):
    spec = _spec(tmp_path, root_name="$Project_shared")
    with caplog.at_level(logging.ERROR):
        assert main(["prune", str(_study(tmp_path)), "--spec", str(spec), "-o", "o.zip"]) == 2
    assert "Project_shared" in caplog.text
    assert list(cwd.iterdir()) == []


def test_filled_placeholder_works(tmp_path, cwd):
    spec = _spec(tmp_path, root_name="$Project-shared")
    assert main(["prune", str(_study(tmp_path)), "--spec", str(spec), "--set-var", "Project=CAMRI", "-o", "o.zip"]) == 0
    assert _zip(cwd / "o.zip")[0] == {"CAMRI-shared"}


def test_set_var_without_equals_is_an_error(tmp_path, cwd):
    spec = _spec(tmp_path)
    assert main(["prune", str(_study(tmp_path)), "--spec", str(spec), "--set-var", "Project", "-o", "o.zip"]) == 2


# ---------------------------------------------------------------------------
# --dry-run (C), summary (D), warnings (F)
# ---------------------------------------------------------------------------


def test_dry_run_writes_nothing_and_shows_the_plan(tmp_path, cwd, capsys):
    study = _study(tmp_path)
    assert main(["prune", str(study), "--anonymize", "--subject-id", "M01", "--dry-run"]) == 0
    assert list(cwd.iterdir()) == []
    out = capsys.readouterr().out
    assert "pruned_anon_M01_anon.zip" in out
    assert "scan 1" in out and "scan 3" in out
    assert "SUBJECT_id" in out and "<M01>" in out
    assert "files:" in out


def test_summary_after_writing(tmp_path, cwd, capsys):
    study = _study(tmp_path)
    assert main(["prune", str(study), "-o", "o.zip"]) == 0
    out = capsys.readouterr().out
    assert f"{len(_files(study))} files" in out
    assert "scans: 1, 3" in out


def test_warnings_for_raw_only_missing_and_unknown_ids(tmp_path, cwd, caplog):
    study = _study(tmp_path, scans={1: "FLASH", 2: "PRESS", 3: "RARE"})
    (study / "1" / "pdata" / "1" / "2dseq").unlink()          # raw only
    for p in sorted((study / "3").rglob("*"), reverse=True):   # neither image nor raw
        if p.is_file() and p.name in {"fid", "2dseq"}:
            p.unlink()
    (study / "2" / "fid").rename(study / "2" / "rawdata.job0")  # MRS-like: image plus rawdata.job0
    with caplog.at_level(logging.WARNING):
        assert main(["prune", str(study), "-s", "1", "2", "3", "9", "-o", "o.zip"]) == 0
    text = caplog.text
    assert "scan 1" in text and "raw data only" in text
    assert "scan 3" in text and "no image or raw data" in text
    assert "scan 2" not in text
    assert "9" in text and "not found" in text


def test_help_explains_the_default(capsys):
    with pytest.raises(SystemExit):
        main(["prune", "-h"])
    out = capsys.readouterr().out
    assert "Nothing is anonymized" in " ".join(out.split())
    for option in ("--files", "--exclude-files", "--institution", "--anonymize", "--dry-run", "--overwrite"):
        assert option in out
