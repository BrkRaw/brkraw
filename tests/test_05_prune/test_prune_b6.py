"""A pruner spec can declare that it anonymizes (b1 bundle B6).

With `--spec my_anon.yaml`, prune could not tell that the spec anonymizes, so
the default output name and the .prune.yaml record carried the original input
name (which usually holds the date and the subject). A top-level
`anonymize: true` in the spec now gives the same naming and record as
`--anonymize`. Synthetic data only.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from brkraw.cli.main import main

from tests.helpers import SYNTH_MARKERS, make_synthetic_study

BUILTIN = Path(__file__).resolve().parents[2] / "src" / "brkraw" / "default" / "pruner_specs" / "anonymize.yaml"


def _study(tmp_path: Path) -> Path:
    return make_synthetic_study(tmp_path / "data" / SYNTH_MARKERS["folder"], pv="360.3.3", scans={3: "RARE"})


@pytest.fixture
def cwd(tmp_path, monkeypatch):
    out = tmp_path / "work"
    out.mkdir()
    monkeypatch.chdir(out)
    return out


def _spec(tmp_path: Path, **changes) -> Path:
    data = yaml.safe_load(BUILTIN.read_text(encoding="utf-8"))
    data["__meta__"]["name"] = "lab_share"
    data.pop("anonymize", None)
    data.update(changes)
    path = tmp_path / "lab_share.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_builtin_anonymize_spec_declares_it():
    assert yaml.safe_load(BUILTIN.read_text(encoding="utf-8")).get("anonymize") is True


def test_custom_spec_with_anonymize_true_names_output_like_anonymize(tmp_path, cwd):
    spec = _spec(tmp_path, anonymize=True)
    assert main(["prune", str(_study(tmp_path)), "--spec", str(spec), "--subject-id", "M01"]) == 0
    assert (cwd / "pruned_anon_M01_anon.zip").is_file()
    record = yaml.safe_load((cwd / "pruned_anon_M01_anon.prune.yaml").read_text(encoding="utf-8"))
    assert "input_name" not in record
    assert not any(SYNTH_MARKERS["folder"] in p.name for p in cwd.iterdir())


def test_custom_spec_without_the_key_keeps_the_input_name(tmp_path, cwd):
    study = _study(tmp_path)
    spec = _spec(tmp_path)
    assert main(["prune", str(study), "--spec", str(spec)]) == 0
    record = yaml.safe_load((cwd / f"pruned_{study.name}.prune.yaml").read_text(encoding="utf-8"))
    assert record["input_name"] == study.name


def test_anonymize_key_must_be_true_or_false(tmp_path, cwd, caplog):
    spec = _spec(tmp_path, anonymize="yes")
    assert main(["prune", str(_study(tmp_path)), "--spec", str(spec)]) == 2
    assert "anonymize" in caplog.text
