"""prune fixes 1-5 and safe writing (b1 bundle B1). Synthetic data only."""
from __future__ import annotations

import hashlib
import logging
import zipfile
from pathlib import Path

import pytest
import yaml

import brkraw
from brkraw.apps.loader import info as info_resolver
from brkraw.apps.loader.info.transform import stringtime_to_datetime
from brkraw.cli.main import main as cli_main
from brkraw.core import fs as fs_module
from brkraw.specs.pruner import prune_dataset_to_zip, prune_dataset_to_zip_from_spec

from tests.helpers import SYNTH_MARKERS, make_synthetic_study

META = {"name": "t", "version": "1.0.0", "description": "test spec", "category": "pruner_spec"}
IMAGE_FILES = ["subject", "acqp", "method", "visu_pars", "reco", "2dseq"]
JCAMP_NAMES = {"subject", "AdjStatePerStudy", "acqp", "method", "AdjStatePerScan", "visu_pars", "reco", "procs"}


def _study(tmp_path: Path) -> Path:
    return make_synthetic_study(tmp_path / SYNTH_MARKERS["folder"], pv="360.3.3", scans={1: "FLASH", 3: "RARE"})


def _entries(zip_path: Path) -> dict:
    with zipfile.ZipFile(zip_path) as zf:
        return {n: zf.read(n) for n in zf.namelist() if not n.endswith("/")}


def _rel(entries: dict) -> dict:
    # drop the top folder
    return {n.split("/", 1)[1]: v for n, v in entries.items()}


def _spec_file(tmp_path: Path, **extra) -> Path:
    spec = {"__meta__": META, "files": IMAGE_FILES}
    spec.update(extra)
    path = tmp_path / "spec.yaml"
    path.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Fix 1: ##OWNER through jcamp_headers
# ---------------------------------------------------------------------------


def test_fix1_jcamp_headers_replace_owner_in_every_kept_jcamp_file(tmp_path):
    study = _study(tmp_path)
    out = prune_dataset_to_zip_from_spec(
        {"__meta__": META, "files": ["subject", "acqp", "method", "visu_pars", "reco", "procs", "2dseq", "fid"],
         "jcamp_headers": {"OWNER": "anon"}},
        source=study,
        dest=tmp_path / "out" / "o.zip",
    )
    entries = _rel(_entries(out))
    for rel, data in entries.items():
        name = rel.split("/")[-1]
        if name in JCAMP_NAMES:
            text = data.decode("utf-8")
            owner_lines = [l for l in text.splitlines() if l.startswith("##OWNER=")]
            assert owner_lines == ["##OWNER=anon"], rel
        else:
            assert data == (study / rel).read_bytes(), rel


def test_fix1_jcamp_headers_accepted_by_validation(tmp_path):
    spec = _spec_file(tmp_path, jcamp_headers={"OWNER": "anon"})
    out = prune_dataset_to_zip_from_spec(spec, source=_study(tmp_path), dest=tmp_path / "o.zip", validate=True)
    assert out.exists()


def test_fix1_jcamp_headers_must_map_names_to_text(tmp_path):
    with pytest.raises(ValueError):
        prune_dataset_to_zip_from_spec(
            {"__meta__": META, "files": IMAGE_FILES, "jcamp_headers": ["OWNER"]},
            source=_study(tmp_path),
            dest=tmp_path / "o.zip",
        )


# ---------------------------------------------------------------------------
# Fix 2: choosing scans keeps study files
# ---------------------------------------------------------------------------


def test_fix2_scan_rule_keeps_study_level_files(tmp_path):
    study = _study(tmp_path)
    out = prune_dataset_to_zip(study, tmp_path / "o.zip", IMAGE_FILES, dirs=[{"level": 1, "dirs": ["3"]}])
    names = set(_rel(_entries(out)))
    assert "subject" in names
    assert {"3/acqp", "3/method", "3/pdata/1/visu_pars", "3/pdata/1/reco", "3/pdata/1/2dseq"} <= names
    assert not any(n.startswith("1/") for n in names)


def test_fix2_level_rule_applies_only_to_paths_with_a_folder_at_that_level(tmp_path):
    import shutil

    study = _study(tmp_path)
    # a competing reco folder at the same level as the chosen one
    shutil.copytree(study / "3" / "pdata" / "1", study / "3" / "pdata" / "2")
    out = prune_dataset_to_zip(
        study, tmp_path / "o.zip", IMAGE_FILES, dirs=[{"level": 1, "dirs": ["3"]}, {"level": 3, "dirs": ["1"]}]
    )
    names = set(_rel(_entries(out)))
    # files above level 3 (study and scan files) are kept by the file list alone
    assert {"subject", "3/acqp", "3/method", "3/pdata/1/2dseq", "3/pdata/1/visu_pars"} <= names
    # the level-3 rule drops the other reco and the level-1 rule drops the other scan
    assert not any(n.startswith("3/pdata/2/") for n in names)
    assert not any(n.startswith("1/") for n in names)


# ---------------------------------------------------------------------------
# Fix 3: comment option falls back to the spec
# ---------------------------------------------------------------------------


def _has_comments(zip_path: Path) -> bool:
    for rel, data in _rel(_entries(zip_path)).items():
        if rel.split("/")[-1] in JCAMP_NAMES and any(
            l.lstrip().startswith("$$") for l in data.decode("utf-8").splitlines()
        ):
            return True
    return False


def test_fix3_cli_uses_spec_value_when_no_flag(tmp_path):
    spec = _spec_file(tmp_path, strip_jcamp_comments=True)
    out = tmp_path / "o.zip"
    assert cli_main(["prune", str(_study(tmp_path)), "--spec", str(spec), "-o", str(out)]) == 0
    assert not _has_comments(out)


def test_fix3_keep_flag_overrides_spec(tmp_path):
    spec = _spec_file(tmp_path, strip_jcamp_comments=True)
    out = tmp_path / "o.zip"
    assert cli_main(["prune", str(_study(tmp_path)), "--spec", str(spec), "-o", str(out), "--keep-jcamp-comments"]) == 0
    assert _has_comments(out)


def test_fix3_strip_flag_overrides_spec(tmp_path):
    spec = _spec_file(tmp_path, strip_jcamp_comments=False)
    out = tmp_path / "o.zip"
    assert cli_main(["prune", str(_study(tmp_path)), "--spec", str(spec), "-o", str(out), "--strip-jcamp-comments"]) == 0
    assert not _has_comments(out)


def test_fix3_flags_are_exclusive(tmp_path):
    spec = _spec_file(tmp_path)
    with pytest.raises(SystemExit):
        cli_main(["prune", str(_study(tmp_path)), "--spec", str(spec), "-o", str(tmp_path / "o.zip"),
                  "--strip-jcamp-comments", "--keep-jcamp-comments"])


# ---------------------------------------------------------------------------
# Fix 4: record file stores names, not paths
# ---------------------------------------------------------------------------


def _all_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _all_strings(k)
            yield from _all_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _all_strings(v)


def test_fix4_record_has_names_and_spec_hash_but_no_paths(tmp_path):
    study = _study(tmp_path)
    spec = _spec_file(tmp_path, strip_jcamp_comments=True)
    out = tmp_path / "out" / "o.zip"
    assert cli_main(["prune", str(study), "--spec", str(spec), "-o", str(out)]) == 0
    record = yaml.safe_load((tmp_path / "out" / "o.prune.yaml").read_text(encoding="utf-8"))
    assert record["input_name"] == study.name
    assert record["output_name"] == "o.zip"
    assert record["spec_name"] == "spec.yaml"
    assert record["spec_sha256"] == hashlib.sha256(spec.read_bytes()).hexdigest()
    assert record["strip_jcamp_comments"] is True
    for text in _all_strings(record):
        assert str(tmp_path) not in text, text
        assert not text.startswith("/"), text


def test_fix4_record_without_input_name_when_anonymizing(tmp_path):
    from brkraw.cli.commands import prune as prune_cmd

    spec = _spec_file(tmp_path)
    out = tmp_path / "o.zip"
    out.write_bytes(b"")
    prune_cmd.write_prune_record(
        out_path=out,
        input_path=tmp_path / SYNTH_MARKERS["folder"],
        spec_path=spec,
        settings={"strip_jcamp_comments": True},
        anonymize=True,
    )
    record = yaml.safe_load((tmp_path / "o.prune.yaml").read_text(encoding="utf-8"))
    assert "input_name" not in record
    for text in _all_strings(record):
        assert SYNTH_MARKERS["name"] not in text


# ---------------------------------------------------------------------------
# Fix 5: missing or unreadable birth date does not stop study info
# ---------------------------------------------------------------------------


def test_fix5_study_info_without_birth_date(tmp_path):
    out = prune_dataset_to_zip(
        _study(tmp_path),
        tmp_path / "o.zip",
        IMAGE_FILES,
        update_params={"subject": {"SUBJECT_dbirth": None}, "visu_pars": {"VisuSubjectBirthDate": None}},
    )
    info = info_resolver.study(brkraw.load(str(out))) or {}
    assert info["Subject"]["ID"] == SYNTH_MARKERS["subject_id"]
    assert info["Subject"].get("DateOfBirth") in (None, "Unknown")


def test_fix5_unreadable_date_warns_and_keeps_text(caplog):
    with caplog.at_level(logging.WARNING):
        assert stringtime_to_datetime("not a date") == "not a date"
    assert any("not a date" in r.getMessage() for r in caplog.records)
    assert stringtime_to_datetime("Unknown") == "Unknown"


# ---------------------------------------------------------------------------
# E: safe writing
# ---------------------------------------------------------------------------


def test_e_existing_output_is_not_overwritten(tmp_path):
    dest = tmp_path / "o.zip"
    dest.write_bytes(b"keep me")
    with pytest.raises(FileExistsError):
        prune_dataset_to_zip(_study(tmp_path), dest, IMAGE_FILES)
    assert dest.read_bytes() == b"keep me"


def test_e_overwrite_replaces(tmp_path):
    dest = tmp_path / "o.zip"
    dest.write_bytes(b"old")
    prune_dataset_to_zip(_study(tmp_path), dest, IMAGE_FILES, overwrite=True)
    assert zipfile.is_zipfile(dest)


def test_e_cli_refuses_existing_output_without_overwrite(tmp_path):
    spec = _spec_file(tmp_path)
    out = tmp_path / "o.zip"
    out.write_bytes(b"keep me")
    assert cli_main(["prune", str(_study(tmp_path)), "--spec", str(spec), "-o", str(out)]) == 2
    assert out.read_bytes() == b"keep me"
    assert cli_main(["prune", str(_study(tmp_path)), "--spec", str(spec), "-o", str(out), "--overwrite"]) == 0
    assert zipfile.is_zipfile(out)


def test_e_failed_write_leaves_no_output_or_temp_file(tmp_path, monkeypatch):
    from brkraw.specs.pruner import logic as pruner_logic

    def boom(*args, **kwargs):
        raise RuntimeError("simulated failure while writing")

    # acqp is edited after other members were already written (members are sorted),
    # so the zip is half-written when the failure happens
    monkeypatch.setattr(pruner_logic, "_apply_jcamp_updates", boom)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    with pytest.raises(RuntimeError):
        prune_dataset_to_zip(_study(tmp_path), out_dir / "o.zip", IMAGE_FILES + ["fid"],
                             update_params={"visu_pars": {"VisuStation": "<x>"}})
    assert list(out_dir.iterdir()) == []


def test_e_large_members_use_zip64(tmp_path, monkeypatch):
    study = _study(tmp_path)
    monkeypatch.setattr(zipfile, "ZIP64_LIMIT", 40)  # every member above 40 bytes counts as "large"
    out = prune_dataset_to_zip(study, tmp_path / "o.zip", IMAGE_FILES + ["fid"])
    entries = _rel(_entries(out))
    assert entries["3/fid"] == (study / "3" / "fid").read_bytes()
    assert entries["3/pdata/1/2dseq"] == (study / "3" / "pdata" / "1" / "2dseq").read_bytes()


def test_e_stripping_comments_streams_non_jcamp_files(tmp_path, monkeypatch):
    study = _study(tmp_path)
    reads = []
    original = fs_module.DatasetFS.open_binary

    class Spy:
        def __init__(self, fh, rel):
            self._fh, self._rel = fh, rel

        def read(self, n=-1):
            reads.append((self._rel, n))
            return self._fh.read(n)

        def close(self):
            self._fh.close()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.close()
            return False

    def spy_open(self, relpath):
        return Spy(original(self, relpath), relpath)

    monkeypatch.setattr(fs_module.DatasetFS, "open_binary", spy_open)
    out = prune_dataset_to_zip(study, tmp_path / "o.zip", IMAGE_FILES + ["fid"], strip_jcamp_comments=True)
    whole = [rel for rel, n in reads if rel.split("/")[-1] in {"fid", "2dseq"} and (n is None or n < 0 or n > (1 << 20))]
    assert whole == []
    entries = _rel(_entries(out))
    assert entries["3/fid"] == (study / "3" / "fid").read_bytes()
    assert not _has_comments(out)
