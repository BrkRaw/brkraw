from __future__ import annotations
import io
from pathlib import Path
from typing import Optional

import pytest

from tests.helpers import prep_module

p_zip = prep_module("core", "zip")
p_fs = prep_module("core", "fs")
p_parameters = prep_module("core", "parameters")
p_dataclasses_study = prep_module("dataclasses", "study")

DatasetFS = p_fs.DatasetFS
Study = p_dataclasses_study.Study
zipcore = p_zip
Parameters = p_parameters.Parameters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_study(tmpdir: Path, name: str, *, with_subject: bool = True, missing: Optional[set[str]] = None) -> Path:
    """Create a Paravision-like tree under tmpdir and return the study path."""
    missing = missing or set()
    study = tmpdir / name
    scan = study / "1"
    pdata = scan / "pdata" / "1"
    pdata.mkdir(parents=True, exist_ok=True)

    if "subject" not in missing and with_subject:
        (study / "subject").write_text("mouse-001\n", encoding="utf-8")
    if "method" not in missing:
        (scan / "method").write_text("##$Method=Demo\n", encoding="utf-8")
    if "acqp" not in missing:
        (scan / "acqp").write_text("##$ACQP=Demo\n", encoding="utf-8")
    if "reco" not in missing:
        (pdata / "reco").write_text("##$Reco=Demo\n", encoding="utf-8")
    if "visu_pars" not in missing:
        (pdata / "visu_pars").write_text("##$VisuPars=Demo\n", encoding="utf-8")
    if "2dseq" not in missing:
        (pdata / "2dseq").write_bytes(b"\x00\x01\x02\x03")

    return study


def _zip_with_anchor(study_dir: Path, zip_path: Path) -> Path:
    """Create a zip containing the study directory with the study root as anchor."""
    tmp_zip = zip_path.with_suffix(".tmp.zip")
    zipcore.create_from_dir(tmp_zip, study_dir)

    with zipcore.load(tmp_zip) as zf:
        roots = zipcore.fetch_dirs_in_zip(zf, dirname="", match_scope="fullpath", wildcard=True)
        root_dir = roots[0] if roots else None
        if root_dir is None:
            raise RuntimeError("Failed to locate root dir in temporary zip")
        root_dir.to_filename(
            zip_path,
            add_root=True,
            root_name=study_dir.name,
            include_dir_entries=True,
        )

    tmp_zip.unlink(missing_ok=True)
    return zip_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_discover_dir_with_subject(tmp_path: Path):
    study_dir = _build_study(tmp_path, "demo-study", with_subject=True)
    fs = DatasetFS.from_path(study_dir)

    studies = Study.discover(fs)
    assert len(studies) == 1
    study = studies[0]
    assert study.has_subject is True
    assert list(study.avail.keys()) == [1]
    assert list(study.scans[1].avail.keys()) == [1]


def test_discover_dir_missing_subject(tmp_path: Path):
    study_dir = _build_study(tmp_path, "no-subject", with_subject=False)
    fs = DatasetFS.from_path(study_dir)

    studies = Study.discover(fs)
    assert len(studies) == 1
    study = studies[0]
    assert study.has_subject is False
    assert list(study.avail.keys()) == [1]


def test_discover_skips_when_method_missing(tmp_path: Path):
    study_dir = _build_study(tmp_path, "missing-method", missing={"method"})
    fs = DatasetFS.from_path(study_dir)

    studies = Study.discover(fs)
    assert studies == []
    with pytest.raises(ValueError, match="No Paravision study"):
        Study.from_path(study_dir)


def test_discover_zip_matches_dir(tmp_path: Path):
    study_dir = _build_study(tmp_path, "zip-study", with_subject=True)
    zip_path = tmp_path / "zip-study.zip"
    _zip_with_anchor(study_dir, zip_path)

    fs_dir = DatasetFS.from_path(study_dir)
    fs_zip = DatasetFS.from_path(zip_path)

    studies_dir = Study.discover(fs_dir)
    studies_zip = Study.discover(fs_zip)

    assert len(studies_dir) == 1
    assert len(studies_zip) == 1
    sd = studies_dir[0]
    sz = studies_zip[0]
    assert sd.relroot == sz.relroot
    assert list(sd.avail.keys()) == [1]
    assert list(sz.avail.keys()) == [1]
    assert list(sd.scans[1].avail.keys()) == [1]
    assert list(sz.scans[1].avail.keys()) == [1]


def test_discover_multiple_studies_under_one_root(tmp_path: Path):
    study_a = _build_study(tmp_path, "studyA", with_subject=True)
    study_b = _build_study(tmp_path, "studyB", with_subject=False)

    # Top-level root containing multiple studies
    fs = DatasetFS.from_path(tmp_path)
    studies = Study.discover(fs)

    assert len(studies) == 2
    names = sorted(s.relroot for s in studies)
    assert names == ["studyA", "studyB"]

    by_name = {s.relroot: s for s in studies}
    assert by_name["studyA"].has_subject is True
    assert by_name["studyB"].has_subject is False

    # from_path should raise when given a root with multiple studies
    with pytest.raises(ValueError, match="Multiple studies"):
        Study.from_path(tmp_path)

@pytest.mark.parametrize("mode", ["dir", "zip"])
def test_node_open_type_detection(tmp_path: Path, mode: str):
    study_dir = _build_study(tmp_path, "open-types", with_subject=True)
    # Ensure method is recognizable as JCAMP and add a dotted filename to exercise candidate generation.
    (study_dir / "1" / "method").write_text(
        "##TITLE=Demo\n##JCAMPDX=5.0\n##$TEST=1\n", encoding="utf-8"
    )
    (study_dir / "notes.txt").write_text("hello world\n", encoding="utf-8")

    if mode == "zip":
        zip_path = tmp_path / "open-types.zip"
        _zip_with_anchor(study_dir, zip_path)
        fs = DatasetFS.from_path(zip_path)
    else:
        fs = DatasetFS.from_path(study_dir)

    study = Study.discover(fs)[0]
    scan = study.scans[1]
    reco = scan.recos[1]

    param = scan.method
    assert isinstance(param, Parameters)
    # Attribute alias using file_ prefix should hit the same cached object.
    assert scan.file_method is param

    subject = study.subject
    assert isinstance(subject, io.StringIO)
    assert "mouse-001" in subject.getvalue()

    # Underscore-to-dot candidate mapping should allow access to dotted filenames.
    notes = study.notes_txt
    assert isinstance(notes, io.StringIO)
    assert notes.getvalue().strip() == "hello world"

    seq = reco["2dseq"]
    assert isinstance(seq, io.BytesIO)
    assert seq.read() == b"\x00\x01\x02\x03"
