"""Manual checks on approved anonymized zips (real ParaVision 5.1, 6.0.1 and 360.3.x studies).

These checks were tests in ``tests/`` that read the ``agent-fixtures`` folder
and were skipped when it was absent (WI-0126). They do not belong in the
automatic test suite: ``tests/`` uses synthetic data only. Run them by hand
when you change prune, convert, context maps, scaling or study info::

    pytest -v scripts/validate/check_agent_fixtures.py

The file name starts with ``check_`` so a plain ``pytest`` (and CI) does not
collect it. The zips are looked up in ``<checkout>/../agent-fixtures`` or in
``BRKRAW_AGENT_FIXTURES=/path``; the run stops with a message when the folder
is missing. Only zips approved in the folder's README with a matching SHA-256
are used, copied into a temporary folder; nothing is written in the folder.

Each check has a synthetic counterpart in ``tests/`` that runs everywhere:
prune of a zip (``test_prune_b3.py``), a same-name map
(``test_convert_context_map.py``), per-frame scaling
(``test_03_resolver/test_frame_scaling.py``) and the read-only rule of context
map values (``test_context_map_v3.py``).
"""
from __future__ import annotations

import copy
import hashlib
import textwrap
import zipfile
from pathlib import Path

import numpy as np
import pytest
import yaml

import brkraw
from brkraw.apps.loader import info as info_resolver
from brkraw.cli.main import main
from brkraw.specs.context_map import load_context_map, plan_scan

from agent_fixtures import find_approved_zips, parse_fixture_readme


# ---------------------------------------------------------------------------
# The fixture finder itself (synthetic folders, no real data)
# ---------------------------------------------------------------------------

_HEADER = (
    "| File | ParaVision | Made by / date | Prune spec (file + SHA-256) | Approved |\n"
    "| --- | --- | --- | --- | --- |\n"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _row(rel: str, sha: str, state: str) -> str:
    return f"| `{rel}` (zip sha256 `{sha}`) | x | Park | `spec.yaml` sha256 `{'b' * 64}` | {state} |\n"


def test_parse_fixture_readme_reads_path_zip_hash_and_exact_approval():
    h = "A" * 64
    text = "# t\n" + _HEADER + _row("pv5.1/a.zip", h, "승인") + _row("pv5.1/b.zip", h, "승인 대기")
    rows = parse_fixture_readme(text)
    assert rows == [
        {"path": "pv5.1/a.zip", "sha256": "a" * 64, "approved": True},
        {"path": "pv5.1/b.zip", "sha256": "a" * 64, "approved": False},
    ]


def test_find_approved_zips_uses_only_approved_rows_with_matching_hash(tmp_path):
    folder = tmp_path / "agent-fixtures"
    (folder / "pv5.1").mkdir(parents=True)
    (folder / "pv6").mkdir()
    ok = folder / "pv5.1" / "ok.zip"
    bad = folder / "pv5.1" / "bad.zip"
    wait = folder / "pv5.1" / "wait.zip"
    other = folder / "pv6" / "other.zip"
    for p in (ok, bad, wait, other):
        p.write_bytes(p.name.encode())
    text = _HEADER
    text += _row("pv5.1/ok.zip", _sha(ok), "승인")
    text += _row("pv5.1/bad.zip", "0" * 64, "승인")
    text += _row("pv5.1/wait.zip", _sha(wait), "승인 대기")
    text += _row("pv5.1/missing.zip", "1" * 64, "승인")
    text += _row("pv6/other.zip", _sha(other), "승인")
    (folder / "README.md").write_text(text, encoding="utf-8")

    found, reasons = find_approved_zips(folder, "pv5.1")

    assert found == [ok]
    joined = "\n".join(reasons)
    assert "bad.zip" in joined and "SHA-256" in joined
    assert "wait.zip" in joined and "not approved" in joined
    assert "missing.zip" in joined and "missing" in joined
    assert "other.zip" not in joined


def test_find_approved_zips_without_folder_or_readme(tmp_path):
    found, reasons = find_approved_zips(tmp_path / "nowhere", "pv5.1")
    assert found == [] and "not found" in reasons[0]
    (tmp_path / "empty").mkdir()
    found, reasons = find_approved_zips(tmp_path / "empty", "pv5.1")
    assert found == [] and "README" in reasons[0]


# ---------------------------------------------------------------------------
# Real folder: the approved_zips fixture copies into tmp_path
# ---------------------------------------------------------------------------


def test_approved_zips_fixture_copies(approved_zips, tmp_path):
    paths = approved_zips("pv5.1")
    for p in paths:
        assert tmp_path in p.parents
        assert p.suffix == ".zip"


# ---------------------------------------------------------------------------
# prune: a default prune of an approved zip is byte-identical (ParaVision 5.1)
# ---------------------------------------------------------------------------


def test_default_prune_of_approved_zip_is_byte_identical(approved_zips, tmp_path, cwd):
    for src in approved_zips("pv5.1"):
        assert main(["prune", str(src), "-o", f"{src.stem}_copy.zip"]) == 0
        with zipfile.ZipFile(src) as a, zipfile.ZipFile(cwd / f"{src.stem}_copy.zip") as b:
            files_a = {n: a.read(n) for n in a.namelist() if not n.endswith("/")}
            files_b = {n: b.read(n) for n in b.namelist() if not n.endswith("/")}
        assert files_a == files_b


# ---------------------------------------------------------------------------
# convert: a same-name map gives one output per converted scan
# ---------------------------------------------------------------------------

# Frame-level scaling tests are in tests/test_03_resolver/test_frame_scaling.py.
KNOWN_SLOPE_FAILURES: dict = {}
SLOPE_SCANS = {"pv5.1-02.zip": {11}, "pv360-3.1-01.zip": {4}}


def _map(study: Path, data: dict, name: str = None) -> Path:
    path = study.parent / (name or f"{study.name}.yaml")
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _niis(out: Path):
    return {p.relative_to(out).as_posix() for p in out.rglob("*.nii.gz")}


@pytest.mark.parametrize("pv", ["pv5.1", "pv6.0.1", "pv360-3.x"])
def test_same_name_map_on_approved_zips(pv, approved_zips, tmp_path):
    for src in approved_zips(pv):
        _map(src, {"__meta__": {"category": "context_map",
                                "layout_template": "{x.sub}/scan-{x.scan}[_sp{utils.slicepack}][_reco-{x.reco}]"},
                   "x": {"sub": {"from": "Subject.ID"}, "scan": {"from": "ScanID"}, "reco": {"from": "RecoID"}}},
             name=f"{src.stem}.yaml")  # a zip's same-name map drops ".zip"
        out = tmp_path / f"out-{src.stem}"
        loader = brkraw.load(str(src))
        assert main(["convert", str(src), "-o", str(out), "-c"]) == 0
        names = _niis(out)
        sub = str((info_resolver.study(loader) or {}).get("Subject", {}).get("ID"))
        assert names and all(n.startswith(f"{sub}/scan-") for n in names)
        written = {int(n.split("scan-")[1].split("_")[0].split(".")[0]) for n in names}
        # every scan is written, except the known scaling regression (test_per_frame_slope_scans_convert);
        # when that is fixed, this fails until KNOWN_SLOPE_FAILURES is emptied
        assert written == set(loader.avail) - KNOWN_SLOPE_FAILURES.get(src.name, set())
        for n in names:
            assert (out / (n[: -len(".nii.gz")] + ".json")).is_file()


# ---------------------------------------------------------------------------
# Scaling: scans with one equal slope per frame keep raw data (BRK-0035, option C)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pv, name", [("pv5.1", "pv5.1-02.zip"), ("pv360-3.x", "pv360-3.1-01.zip")])
def test_per_frame_slope_scans_convert(pv, name, approved_zips):
    src = [p for p in approved_zips(pv) if p.name == name][0]
    loader = brkraw.load(str(src))
    for scan_id in SLOPE_SCANS[name]:
        nii = loader.convert(scan_id, reco_id=1)
        assert nii is not None
        raw = np.asarray(loader.get_dataobj(scan_id, 1))
        # these scans have one equal slope per frame: kept in the header, data stays raw (as 0.5.7)
        assert np.array_equal(np.asarray(nii.dataobj), raw)


# ---------------------------------------------------------------------------
# Context map values from real scan info leave the info unchanged
# ---------------------------------------------------------------------------


def _write(folder: Path, name: str, text: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


@pytest.mark.parametrize("pv", ["pv5.1", "pv6.0.1", "pv360-3.x"])
def test_values_from_real_scan_info_leave_it_unchanged(pv, approved_zips, tmp_path):
    data = load_context_map(_write(tmp_path, "m.yaml", """
        __meta__: {category: context_map}
        v:
          method: {from: Method}
          sub: {from: Subject.ID}
          ses: {from: Session.ID}
          scan: {from: ScanID}
          kind: {from: Method, map: {"Bruker:EPI": func}, default: other}
    """))
    for zip_path in approved_zips(pv):
        loader = brkraw.load(str(zip_path))
        study = info_resolver.study(loader) or {}
        for scan_id in sorted(loader.avail):
            scan = info_resolver.scan(loader.get_scan(scan_id)) or {}
            info = {**study, **scan}
            before = copy.deepcopy(info)
            plan = plan_scan(info, data, scan_id=scan_id)
            assert info == before
            assert plan.namespaces["v"]["method"] == scan.get("Method")
            assert plan.namespaces["v"]["sub"] == (study.get("Subject") or {}).get("ID")
            assert plan.namespaces["v"]["ses"] == (study.get("Study") or {}).get("ID")
            assert plan.namespaces["v"]["scan"] == scan_id
            assert plan.namespaces["v"]["kind"] in {"func", "other"}
