"""Shared test helpers: module loading, environment isolation, synthetic PvDatasets."""
from __future__ import annotations

import importlib
import os
import struct
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Kept while tests run: the config home set by the isolation itself and the
# optional override for the agent-fixtures folder (read only by the manual
# checks in scripts/validate/, never by tests).
KEEP_ENV = ("BRKRAW_CONFIG_HOME", "BRKRAW_AGENT_FIXTURES")


def prep_module(core_level: str, parser: str):
    module_path = f"brkraw.{core_level}"
    mod = importlib.import_module(module_path)
    return getattr(mod, parser)


def isolate_brkraw_env(monkeypatch, base: Path) -> None:
    """Point brkraw's config home and HOME into ``base`` and drop session variables.

    ``brkraw session`` exports ``BRKRAW_PATH``, ``BRKRAW_SCAN_ID``,
    ``BRKRAW_CONVERT_*`` and similar variables that change command defaults;
    without ``BRKRAW_CONFIG_HOME`` brkraw reads ``~/.brkraw``; ``brkraw init``
    looks at ``Path.home()``. Tests must see none of the developer's own
    settings.
    """
    base = Path(base)
    home = base / "home"
    home.mkdir(parents=True, exist_ok=True)
    for key in list(os.environ):
        if key.startswith("BRKRAW_") and key not in KEEP_ENV:
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("BRKRAW_CONFIG_HOME", str(base / "config"))
    monkeypatch.setenv("HOME", str(home))


# ---------------------------------------------------------------------------
# Synthetic ParaVision-like datasets
# ---------------------------------------------------------------------------

# Every identifying value is a unique marker (ZQX… or a fixed digit string) so
# prune tests can search outputs for it. No real data is involved.
SYNTH_MARKERS: Dict[str, str] = {
    "name": "ZQXDoeJohn",
    "subject_id": "ZQXmouse77",
    "study_name": "ZQXstudyAlpha",
    "operator": "ZQXoperatorKim",
    "owner": "ZQXloginuser",
    "institution": "ZQXUniversityOfNowhere",
    "station": "ZQXStation94",
    "referral": "ZQXDrReferrer",
    "comment": "ZQXfreeTextComment",
    "birth": "19870412",
    "order": "ZQXorder5566",
    "folder": "20240315_101010_ZQXDoeJohn_1_1",
    "abs_date": "1710497410",
    "uid": "2.16.840.1.113654.2.ZQX",
}


def _jcamp(title: str, owner: str, path_comment: str, params: List[Tuple[str, str]]) -> str:
    lines = [
        f"##TITLE=Parameter List, {title}",
        "##JCAMPDX=4.24",
        "##DATATYPE=Parameter Values",
        "##ORIGIN=Bruker BioSpin MRI GmbH",
        f"##OWNER={owner}",
        f"$$ Fri Mar 15 10:10:10 2024 EDT (UT-4h)  {owner}",
        f"$$ {path_comment}",
    ]
    for key, value in params:
        lines.append(f"##${key}={value}")
    lines.append("##END=")
    return "\n".join(lines) + "\n"


def _s(text: str) -> str:
    """JCAMP string value: size line, then <text>."""
    return f"( {max(len(text) + 1, 16)} )\n<{text}>"


def make_synthetic_study(
    root: Path,
    *,
    pv: str = "6.0.1",
    scans: Optional[Dict[int, str]] = None,
    frames: Optional[Dict[int, List[Tuple[str, int]]]] = None,
    packs: Optional[Dict[int, int]] = None,
    slopes: Optional[Dict[int, List[float]]] = None,
    offsets: Optional[Dict[int, List[float]]] = None,
    depth: Optional[Dict[int, int]] = None,
    slope_shape: Optional[Dict[int, List[int]]] = None,
    orientations: Optional[Dict[int, List[str]]] = None,
) -> Path:
    """Write a small ParaVision-like study folder at ``root`` and return it.

    ``scans`` maps scan id -> method name (default ``{1: "FLASH", 3: "RARE"}``).
    Each scan has acqp, method, fid, AdjStatePerScan and pdata/1 with
    visu_pars, reco, procs and a 4x4 int16 2dseq (one slice). Study files:
    subject, AdjStatePerStudy, ScanProgram.scanProgram. Values carry
    SYNTH_MARKERS, JCAMP files carry ``##OWNER`` and ``$$`` comment lines with
    a source path. A minimal identity geometry is written, so brkraw can
    convert the scans (the orientation is not meant to be checked).

    ``frames`` maps scan id -> frame groups, for example
    ``{8: [("FG_ECHO", 2), ("FG_CYCLE", 3)]}``: the scan then has 2 x 3 frames
    and its 2dseq holds ``0, 1, 2, ...`` in ParaVision order, so the data is
    ``np.arange(16 * 6).reshape((4, 4, 1, 2, 3), order="F")``.

    ``packs`` maps scan id -> number of slice packs (one slice each, an
    ``FG_SLICE`` group in front of the frame groups, unless ``frames`` places
    ``("FG_SLICE", n)`` itself). ``slopes`` maps scan id
    -> the VisuCoreDataSlope values to write (VisuCoreDataOffs gets as many 0,
    unless ``offsets`` gives them). ``depth`` maps scan id -> z size of a 3D
    scan (VisuCoreDim 3, 4 x 4 x depth per frame, no slice frame group).
    ``slope_shape`` gives the declared JCAMP shape of slope and offset (for
    example ``[3, 2]``), ``orientations`` one 9-value text per frame for
    VisuCoreOrientation (default: identity for every frame).
    """
    packs = packs or {}
    slopes = slopes or {}
    offsets = offsets or {}
    depth = depth or {}
    slope_shape = slope_shape or {}
    orientations = orientations or {}
    frames = frames or {}
    scans = scans or {1: "FLASH", 3: "RARE"}
    m = SYNTH_MARKERS
    iso = not pv.startswith("5")
    date_txt = "2024-03-15T10:10:10,123-0400" if iso else "10:10:10 15 Mar 2024"
    title = f"ParaVision {pv}"
    base = f"/opt/PV{pv}/data/{m['owner']}/nmr/{m['folder']}"
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    subject = [
        ("SUBJECT_name_string", _s(m["name"])),
        ("SUBJECT_id", _s(m["subject_id"])),
        ("SUBJECT_study_name", _s(m["study_name"])),
        ("SUBJECT_study_nr", "3"),
        ("SUBJECT_dbirth", _s(m["birth"])),
        ("SUBJECT_date", _s(date_txt)),
        ("SUBJECT_abs_date", "(" + m["abs_date"] + ", 123, -240)"),
        ("SUBJECT_referral", _s(m["referral"])),
        ("SUBJECT_comment", _s(m["comment"])),
        ("SUBJECT_study_instance_uid", _s(m["uid"] + ".1")),
        ("SUBJECT_institution", _s(m["institution"])),
        ("SUBJECT_type", "Quadruped"),
        ("SUBJECT_entry", "SUBJ_ENTRY_HeadFirst"),
        ("SUBJECT_position", "SUBJ_POS_Supine"),
        ("SUBJECT_sex_animal", "MALE"),
        ("SUBJECT_weight", "0.025"),
    ]
    (root / "subject").write_text(_jcamp(title, m["owner"], base + "/subject", subject), encoding="utf-8")
    (root / "AdjStatePerStudy").write_text(
        _jcamp(title, m["owner"], base + "/AdjStatePerStudy", [("ADJ_note", _s(m["operator"]))]),
        encoding="utf-8",
    )
    (root / "ScanProgram.scanProgram").write_text(
        f"<scanProgram><owner>{m['owner']}</owner><name>{m['name']}</name></scanProgram>\n",
        encoding="utf-8",
    )
    for sid, method in scans.items():
        sdir = root / str(sid)
        pdir = sdir / "pdata" / "1"
        pdir.mkdir(parents=True, exist_ok=True)
        groups = list(frames.get(sid, []))
        n_packs = int(packs.get(sid, 1))
        if n_packs > 1 and not any(name == "FG_SLICE" for name, _ in groups):
            groups = [("FG_SLICE", n_packs)] + groups
        n_frames = 1
        for _, size in groups:
            n_frames *= int(size)
        acqp = [
            ("ACQ_method", _s(f"Bruker:{method}")),
            ("ACQ_protocol_name", _s(f"{method}_proto")),
            ("ACQ_scan_name", _s(f"{method}_E{sid}")),
            ("ACQ_time", _s(date_txt)),
            ("ACQ_abs_time", "(" + m["abs_date"] + ", 456, -240)"),
            ("ACQ_operator", _s(m["operator"])),
            ("ACQ_institution", _s(m["institution"])),
            ("ACQ_station", _s(m["station"])),
            ("ACQ_sw_version", _s(f"PV-{pv}" if pv.startswith("360") else f"PV {pv}")),
            ("ACQ_calib_date", _s(date_txt)),
            ("NI", "1"),
            ("NR", "1"),
        ]
        method_p = [
            ("Method", f"<Bruker:{method}>" if iso else method),
            ("PVM_EchoTime", "10"),
            ("PVM_RepetitionTime", "2000"),
            ("PVM_Matrix", "( 2 )\n4 4"),
            ("PVM_NSPacks", str(n_packs)),
            ("PVM_SPackArrNSlices", f"( {n_packs} )\n" + " ".join(["1"] * n_packs)),
            ("PVM_SPackArrSliceOrient", f"( {n_packs} )\n" + " ".join(["axial"] * n_packs)),
            ("PVM_SPackArrSliceDistance", f"( {n_packs} )\n" + " ".join(["1"] * n_packs)),
            ("PVM_SPackArrSliceGap", f"( {n_packs} )\n" + " ".join(["0"] * n_packs)),
            ("PVM_SliceThick", "1"),
        ]
        nz = int(depth.get(sid, 0))
        core = [
            ("VisuCoreDim", "3"),
            ("VisuCoreSize", f"( 3 )\n4 4 {nz}"),
            ("VisuCoreDimDesc", "( 3 )\nspatial spatial spatial"),
        ] if nz else [
            ("VisuCoreDim", "2"),
            ("VisuCoreSize", "( 2 )\n4 4"),
            ("VisuCoreDimDesc", "( 2 )\nspatial spatial"),
        ]
        visu = core + [
            ("VisuCoreFrameCount", str(n_frames)),
            ("VisuCoreFrameType", f"( {n_frames} )\n" + " ".join(["MAGNITUDE_IMAGE"] * n_frames)),
            ("VisuCoreOrientation", f"( {n_frames}, 9 )\n"
             + " ".join(orientations.get(sid) or ["1 0 0 0 1 0 0 0 1"] * n_frames)),
            ("VisuCorePosition", f"( {n_frames}, 3 )\n" + " ".join(["0 0 0"] * n_frames)),
            ("VisuSubjectType", "Quadruped"),
            ("VisuSubjectPosition", "Head_Supine"),
            ("VisuCoreWordType", "_16BIT_SGN_INT"),
            ("VisuCoreByteOrder", "littleEndian"),
            ("VisuCoreExtent", f"( 3 )\n20 20 {nz}" if nz else "( 2 )\n20 20"),
            ("VisuSubjectName", _s(m["name"])),
            ("VisuSubjectId", _s(m["subject_id"])),
            ("VisuSubjectBirthDate", _s(m["birth"])),
            ("VisuSubjectComment", _s(m["comment"])),
            ("VisuStudyId", _s(m["study_name"])),
            ("VisuStudyDate", _s(date_txt)),
            ("VisuStudyUid", _s(m["uid"] + ".2")),
            ("VisuStudyReferringPhysician", _s(m["referral"])),
            ("VisuSeriesDate", _s(date_txt)),
            ("VisuAcqDate", _s(date_txt)),
            ("VisuCreationDate", _s(date_txt)),
            ("VisuUid", _s(m["uid"] + ".3")),
            ("VisuSeriesUid", _s(m["uid"] + ".4")),
            ("VisuInstitution", _s(m["institution"])),
            ("VisuStation", _s(m["station"])),
            ("VisuSystemOrderNumber", _s(m["order"])),
            ("VisuAcqProtocol", _s(f"{method}_proto")),
            ("VisuExperimentNumber", str(sid)),
        ]
        if sid in slopes or sid in offsets:
            vals = [float(v) for v in slopes.get(sid, [1.0])]
            offs = [float(v) for v in offsets.get(sid, [0.0] * len(vals))]
            dims = ", ".join(str(d) for d in slope_shape.get(sid, []))
            visu += [
                ("VisuCoreDataSlope", f"( {dims or len(vals)} )\n" + " ".join(repr(v) for v in vals)),
                ("VisuCoreDataOffs", f"( {dims or len(offs)} )\n" + " ".join(repr(v) for v in offs)),
            ]
        if groups:
            desc = " ".join(f"({size}, <{name}>, <>, 0, 0)" for name, size in groups)
            visu += [
                ("VisuFGOrderDescDim", str(len(groups))),
                ("VisuFGOrderDesc", f"( {len(groups)} )\n{desc}"),
            ]
        reco = [
            ("RECO_size", "( 2 )\n4 4"),
            ("RECO_time", _s(date_txt)),
            ("RECO_abs_time", "(" + m["abs_date"] + ", 789, -240)"),
            ("RECO_base_image_uid", _s(m["uid"] + ".5")),
        ]
        (sdir / "acqp").write_text(_jcamp(title, m["owner"], f"{base}/{sid}/acqp", acqp), encoding="utf-8")
        (sdir / "method").write_text(_jcamp(title, m["owner"], f"{base}/{sid}/method", method_p), encoding="utf-8")
        (sdir / "fid").write_bytes(b"\x00" * 64)
        (sdir / "AdjStatePerScan").write_text(
            _jcamp(title, m["owner"], f"{base}/{sid}/AdjStatePerScan", [("ADJ_x", _s(m["name"]))]),
            encoding="utf-8",
        )
        (pdir / "visu_pars").write_text(
            _jcamp(title, m["owner"], f"{base}/{sid}/pdata/1/visu_pars", visu), encoding="utf-8"
        )
        (pdir / "reco").write_text(_jcamp(title, m["owner"], f"{base}/{sid}/pdata/1/reco", reco), encoding="utf-8")
        (pdir / "procs").write_text(
            _jcamp(title, m["owner"], f"{base}/{sid}/pdata/1/procs", [("PROC_x", _s(m["owner"]))]),
            encoding="utf-8",
        )
        count = 16 * max(nz, 1) * n_frames
        (pdir / "2dseq").write_bytes(struct.pack(f"<{count}h", *range(count)))
    return root


def zip_synthetic_study(study: Path, zip_path: Path, *, inner: Optional[str] = None) -> Path:
    """Zip ``study`` with its files under one top folder (default: the marker folder name)."""
    inner = inner or SYNTH_MARKERS["folder"]
    with zipfile.ZipFile(zip_path, "w") as zf:
        for p in sorted(Path(study).rglob("*")):
            if p.is_file():
                zf.write(p, f"{inner}/{p.relative_to(study).as_posix()}")
    return Path(zip_path)
