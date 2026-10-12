"""Per-frame VisuCoreDataSlope (BRK-0035, option C). Synthetic data only.

ParaVision stores one slope value per frame (a 2D slice or a 3D volume) in
2dseq frame order. Equal values become one header scalar and the data stays
raw (as 0.5.7); different values are applied to the data frame by frame
(float data, header slope 1), before slice packs are split and frames are
selected, so every output keeps the right value for its frames.
"""
from __future__ import annotations

from pathlib import Path

import nibabel as nib
import numpy as np
import pytest
import yaml

import brkraw
from brkraw.cli.main import main

from tests.helpers import make_synthetic_study


def _raw(study: Path, scan_id: int):
    return brkraw.load(str(study)).get_dataobj(scan_id, 1)


def _convert(study: Path, scan_id: int, out: Path, *extra: str) -> nib.Nifti1Image:
    assert main(["convert", str(study), "-s", str(scan_id), "-o", str(out), "--no-context-map", *extra]) == 0
    return nib.load(str(out))


def _values(img: nib.Nifti1Image) -> np.ndarray:
    # values after the header scaling
    return np.asarray(img.get_fdata())


def test_equal_per_frame_slope_stays_in_the_header(tmp_path):
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={5: "EPI"},
                              frames={5: [("FG_CYCLE", 3)]}, slopes={5: [2.0, 2.0, 2.0]})
    img = _convert(st, 5, tmp_path / "o.nii.gz")
    raw = np.asarray(_raw(st, 5))
    # one scalar in the header in memory; nibabel writes it into the stored
    # integers on save (same as a single global slope), so the file stays int16
    assert brkraw.load(str(st)).convert(5, reco_id=1).header.get_slope_inter() == (2.0, 0.0)
    assert img.get_data_dtype() == np.dtype("int16")
    assert np.allclose(_values(img), raw * 2.0)


def test_different_per_frame_slopes_are_applied_per_frame(tmp_path):
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={5: "EPI"},
                              frames={5: [("FG_CYCLE", 3)]}, slopes={5: [1.0, 2.0, 3.0]})
    img = _convert(st, 5, tmp_path / "o.nii.gz")
    raw = np.asarray(_raw(st, 5), dtype=float)
    assert np.allclose(_values(img), raw * np.array([1.0, 2.0, 3.0]))
    assert img.header.get_slope_inter()[0] in (None, 1.0)


def test_per_frame_slopes_follow_slice_packs(tmp_path):
    # frames in 2dseq order: slice (= pack) fastest, then cycle; frame = pack + 2 * cycle
    slopes = [1.0, 10.0, 2.0, 20.0, 3.0, 30.0]
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={7: "EPI"},
                              frames={7: [("FG_CYCLE", 3)]}, packs={7: 2}, slopes={7: slopes})
    out = tmp_path / "o"
    assert main(["convert", str(st), "-s", "7", "-o", str(out) + "/", "--no-context-map"]) == 0
    packs = _raw(st, 7)
    files = sorted(out.glob("*.nii.gz"))
    assert len(files) == 2
    for p, path in enumerate(files):
        expected = np.asarray(packs[p], dtype=float) * np.array([slopes[p + 2 * c] for c in range(3)])
        assert np.allclose(_values(nib.load(str(path))), expected)


def test_per_frame_slopes_follow_the_frame_order_when_slice_is_not_first(tmp_path):
    # FG order echo, slice: frame = echo + 2 * slice
    slopes = [1.0, 2.0, 10.0, 20.0]
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={9: "FieldMap"},
                              frames={9: [("FG_ECHO", 2), ("FG_SLICE", 2)]}, packs={9: 2}, slopes={9: slopes})
    out = tmp_path / "o"
    assert main(["convert", str(st), "-s", "9", "-o", str(out) + "/", "--no-context-map"]) == 0
    packs = _raw(st, 9)
    files = sorted(out.glob("*.nii.gz"))
    assert len(files) == 2
    for p, path in enumerate(files):
        expected = np.asarray(packs[p], dtype=float) * np.array([slopes[e + 2 * p] for e in range(2)])
        assert np.allclose(_values(nib.load(str(path))), expected)


@pytest.mark.parametrize(
    "extra, index, scale",
    [
        (["--axis", "cycle", "--frames", "2"], (Ellipsis, 2), 3.0),
        (["--frames", "2,0"], (Ellipsis, [2, 0]), np.array([3.0, 1.0])),
        (["--frames", "1:3"], (Ellipsis, slice(1, 3)), np.array([2.0, 3.0])),
        (["--cycle-index", "1", "--cycle-count", "2"], (Ellipsis, slice(1, 3)), np.array([2.0, 3.0])),
    ],
)
def test_frame_selection_keeps_each_frames_slope(tmp_path, extra, index, scale):
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={5: "EPI"},
                              frames={5: [("FG_CYCLE", 3)]}, slopes={5: [1.0, 2.0, 3.0]})
    img = _convert(st, 5, tmp_path / "o.nii.gz", *extra)
    raw = np.asarray(_raw(st, 5), dtype=float)
    assert np.allclose(_values(img), raw[index] * scale)


def test_split_parts_keep_each_frames_slope(tmp_path):
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={8: "FieldMap"},
                              frames={8: [("FG_ECHO", 2)]}, slopes={8: [1.0, 5.0]})
    (st.parent / f"{st.name}.yaml").write_text(yaml.safe_dump({
        "__meta__": {"category": "context_map", "layout_template": "E{x.scan}_part{utils.split}"},
        "x": {"scan": {"from": "ScanID"}},
        "split": {"value": [{"axis": "echo", "frames": 0}, {"axis": "echo", "frames": 1}]},
    }), encoding="utf-8")
    out = tmp_path / "o"
    assert main(["convert", str(st), "-o", str(out)]) == 0
    raw = np.asarray(_raw(st, 8), dtype=float)
    assert np.allclose(_values(nib.load(str(out / "E8_part1.nii.gz"))), raw[..., 0] * 1.0)
    assert np.allclose(_values(nib.load(str(out / "E8_part2.nii.gz"))), raw[..., 1] * 5.0)


def test_flatten_after_per_frame_scaling(tmp_path):
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={9: "EPI"},
                              frames={9: [("FG_ECHO", 2), ("FG_CYCLE", 2)]}, slopes={9: [1.0, 2.0, 3.0, 4.0]})
    img = _convert(st, 9, tmp_path / "o.nii.gz", "-F")
    raw = np.asarray(_raw(st, 9), dtype=float)  # (4, 4, 1, 2, 2): echo fastest
    scaled = raw * np.array([[1.0, 3.0], [2.0, 4.0]])  # [echo, cycle] -> frame echo + 2 * cycle
    # -F flattens in the order of the unscaled data (Fortran for a full read): echo fastest
    assert np.allclose(_values(img), scaled.reshape((4, 4, 1, 4), order="F"))
    plain = make_synthetic_study(tmp_path / "p", pv="360.3.3", scans={9: "EPI"},
                                 frames={9: [("FG_ECHO", 2), ("FG_CYCLE", 2)]})
    ref = _convert(plain, 9, tmp_path / "p.nii.gz", "-F")
    assert np.allclose(_values(ref), np.asarray(_raw(plain, 9), dtype=float).reshape((4, 4, 1, 4), order="F"))


def test_get_dataobj_stays_raw_with_per_frame_slopes(tmp_path):
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={5: "EPI"},
                              frames={5: [("FG_CYCLE", 3)]}, slopes={5: [1.0, 2.0, 3.0]})
    data = np.asarray(_raw(st, 5))
    assert data.dtype == np.int16
    assert np.array_equal(data.reshape(-1, order="F"), np.arange(48))


# ---------------------------------------------------------------------------
# BRK-0036 layout rule: count vs slice packs first, then products of the
# VisuFGOrderDesc axes from the back; only exactly equal values merge; no
# match -> warning, no scaling.
# ---------------------------------------------------------------------------


def _mem(study: Path, scan_id: int):
    """Converted images written and read back (an in-memory image ignores its header slope)."""
    nii = brkraw.load(str(study)).convert(scan_id, reco_id=1)
    imgs = list(nii) if isinstance(nii, tuple) else [nii]
    out = []
    for k, img in enumerate(imgs):
        path = study.parent / f"mem-{scan_id}-{k}.nii"
        img.to_filename(str(path))
        out.append(nib.load(str(path)))
    return out


def test_near_equal_values_are_not_merged(tmp_path):
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={4: "RARE"}, packs={4: 2},
                              slopes={4: [1.0, 1.000005]})
    packs = _raw(st, 4)
    imgs = _mem(st, 4)
    for p, scale in enumerate((1.0, 1.000005)):
        assert np.allclose(np.asarray(imgs[p].get_fdata()), np.asarray(packs[p], dtype=float) * scale,
                           rtol=1e-7, atol=0)


def test_3d_with_z_size_equal_to_frame_count_is_scaled_per_frame(tmp_path):
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={6: "FLASH3D"},
                              frames={6: [("FG_CYCLE", 3)]}, depth={6: 3}, slopes={6: [1.0, 2.0, 3.0]})
    raw = np.asarray(_raw(st, 6), dtype=float)
    assert raw.shape == (4, 4, 3, 3)
    out = np.asarray(_mem(st, 6)[0].get_fdata())
    assert np.allclose(out, raw * np.array([1.0, 2.0, 3.0]))


def test_per_frame_offsets(tmp_path):
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={5: "EPI"}, frames={5: [("FG_CYCLE", 3)]},
                              slopes={5: [1.0, 2.0, 3.0]}, offsets={5: [10.0, 20.0, 30.0]})
    raw = np.asarray(_raw(st, 5), dtype=float)
    out = np.asarray(_mem(st, 5)[0].get_fdata())
    assert np.allclose(out, raw * np.array([1.0, 2.0, 3.0]) + np.array([10.0, 20.0, 30.0]))


def test_values_vary_along_the_trailing_axes(tmp_path):
    # FG order echo 2, cycle 3; 3 values -> one per cycle, same for both echoes
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={9: "EPI"},
                              frames={9: [("FG_ECHO", 2), ("FG_CYCLE", 3)]}, slopes={9: [1.0, 2.0, 3.0]})
    raw = np.asarray(_raw(st, 9), dtype=float)  # (4, 4, 1, 2, 3)
    out = np.asarray(_mem(st, 9)[0].get_fdata())
    assert np.allclose(out, raw * np.array([1.0, 2.0, 3.0]).reshape(1, 1, 1, 1, 3))


def test_no_matching_layout_warns_and_applies_no_scaling(tmp_path, caplog):
    import logging

    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={5: "EPI"}, frames={5: [("FG_CYCLE", 3)]},
                              slopes={5: [1.0, 2.0, 3.0, 4.0]})
    raw = np.asarray(_raw(st, 5), dtype=float)
    with caplog.at_level(logging.WARNING):
        out = np.asarray(_mem(st, 5)[0].get_fdata())
    assert np.array_equal(out, raw)
    assert "VisuCoreDataSlope" in caplog.text and "not applied" in caplog.text


def test_pack_count_is_checked_first(tmp_path):
    # 3 slice packs of one slice x 3 cycles; 3 values match both the pack count and the
    # trailing cycle axis: the rule checks slice packs first (Park's proposal for the tie)
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={7: "EPI"}, frames={7: [("FG_CYCLE", 3)]},
                              packs={7: 3}, slopes={7: [1.0, 2.0, 3.0]})
    packs = _raw(st, 7)
    imgs = _mem(st, 7)
    for p, scale in enumerate((1.0, 2.0, 3.0)):
        assert np.allclose(np.asarray(imgs[p].get_fdata()), np.asarray(packs[p], dtype=float) * scale)
