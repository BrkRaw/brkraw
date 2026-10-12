"""BRK-0037 safeguards (b1 bundle B7). Synthetic data only.

1. Slice packs: the frames brkraw assigns to each slice pack (a contiguous
   split along FG_SLICE) should share one orientation; if not, warn.
2. Scaling parameters stored with more than one dimension: the declared shape
   should match the frame axes (JCAMP stores the last dimension fastest, so a
   consistent shape lists the trailing frame axes slowest first); if not, warn.
The data is converted in both cases (warnings only).
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

import brkraw

from tests.helpers import make_synthetic_study

IDENTITY = "1 0 0 0 1 0 0 0 1"
TURNED = "0 1 0 1 0 0 0 0 1"


def _convert(study: Path, scan_id: int):
    return brkraw.load(str(study)).convert(scan_id, reco_id=1)


def _msgs(caplog, word):
    return [r.getMessage() for r in caplog.records if word in r.getMessage()]


def test_pack_frames_with_one_orientation_give_no_warning(tmp_path, caplog):
    # 2 packs x 2 cycles; frame = pack + 2 * cycle; each pack keeps its own orientation
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={7: "EPI"}, frames={7: [("FG_CYCLE", 2)]},
                              packs={7: 2}, orientations={7: [IDENTITY, TURNED, IDENTITY, TURNED]})
    with caplog.at_level(logging.WARNING):
        nii = _convert(st, 7)
    assert isinstance(nii, tuple) and len(nii) == 2
    assert not _msgs(caplog, "orientation")


def test_pack_frames_with_mixed_orientations_warn(tmp_path, caplog):
    # pack 1 = frames 0 and 2; frame 2 is turned: the split does not match the geometry
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={7: "EPI"}, frames={7: [("FG_CYCLE", 2)]},
                              packs={7: 2}, orientations={7: [IDENTITY, TURNED, TURNED, TURNED]})
    with caplog.at_level(logging.WARNING):
        nii = _convert(st, 7)
    assert isinstance(nii, tuple) and len(nii) == 2          # still converted
    msgs = _msgs(caplog, "orientation")
    assert len(msgs) == 1 and "slice pack 1" in msgs[0]


def test_single_pack_is_not_checked(tmp_path, caplog):
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={5: "EPI"}, frames={5: [("FG_CYCLE", 2)]},
                              orientations={5: [IDENTITY, TURNED]})
    with caplog.at_level(logging.WARNING):
        _convert(st, 5)
    assert not _msgs(caplog, "orientation")


def test_multidim_slope_matching_the_frame_axes_gives_no_warning(tmp_path, caplog):
    # frame axes echo 2 (fastest), cycle 3; stored shape (3, 2) = cycle, echo: consistent
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={9: "EPI"},
                              frames={9: [("FG_ECHO", 2), ("FG_CYCLE", 3)]},
                              slopes={9: [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]}, slope_shape={9: [3, 2]})
    with caplog.at_level(logging.WARNING):
        nii = _convert(st, 9)
    assert not _msgs(caplog, "stored with shape")
    raw = np.asarray(brkraw.load(str(st)).get_dataobj(9, 1), dtype=float)
    expected = raw * np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]).reshape((2, 3), order="F")
    assert np.allclose(np.asarray(nii.dataobj), expected)


def test_multidim_slope_not_matching_the_frame_axes_warns(tmp_path, caplog):
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={9: "EPI"},
                              frames={9: [("FG_ECHO", 2), ("FG_CYCLE", 3)]},
                              slopes={9: [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]}, slope_shape={9: [2, 3]})
    with caplog.at_level(logging.WARNING):
        nii = _convert(st, 9)
    msgs = _msgs(caplog, "stored with shape")
    assert msgs and "VisuCoreDataSlope" in msgs[0] and "(2, 3)" in msgs[0]
    assert nii is not None                                   # read in stored order, as without the check
