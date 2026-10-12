"""A legacy cycle_index/cycle_count call must not change what later plain calls return
(WI-0084, D-0107 4). Synthetic data only."""
from __future__ import annotations

import numpy as np
import pytest

import brkraw

from tests.helpers import make_synthetic_study

SCANS = {5: "EPI", 8: "FieldMap"}
FRAMES = {5: [("FG_CYCLE", 4)], 8: [("FG_ECHO", 2), ("FG_CYCLE", 3)]}


@pytest.fixture
def study(tmp_path):
    return make_synthetic_study(tmp_path / "data" / "20240101_mouse01", pv="360.3.3", scans=SCANS, frames=FRAMES)


def _bytes(a):
    a = np.asarray(a)
    return a.dtype.str, a.shape, a.flags.f_contiguous, a.flags.c_contiguous, a.flags.writeable, a.tobytes()


def _legacy(loader, scan, **kw):
    with pytest.warns(DeprecationWarning):
        return loader.get_dataobj(scan, 1, **kw)


@pytest.mark.parametrize("scan", [5, 8])
@pytest.mark.parametrize("kw", [{"cycle_index": 1}, {"cycle_index": 1, "cycle_count": 2}, {"cycle_count": 1}])
def test_plain_call_after_legacy_call_returns_the_full_array(study, scan, kw):
    ref = _bytes(brkraw.load(str(study)).get_dataobj(scan, 1))
    loader = brkraw.load(str(study))
    block = _legacy(loader, scan, **kw)
    assert np.asarray(block).shape[-1] < ref[1][-1]
    assert _bytes(loader.get_dataobj(scan, 1)) == ref


def test_plain_call_before_and_after_legacy_call_are_identical(study):
    loader = brkraw.load(str(study))
    before = _bytes(loader.get_dataobj(5, 1))
    _legacy(loader, 5, cycle_index=2, cycle_count=1)
    assert _bytes(loader.get_dataobj(5, 1)) == before


def test_axis_frames_after_legacy_call_selects_from_the_full_array(study):
    full = np.asarray(brkraw.load(str(study)).get_dataobj(5, 1))
    loader = brkraw.load(str(study))
    _legacy(loader, 5, cycle_index=1, cycle_count=1)
    assert np.array_equal(loader.get_dataobj(5, 1, axis="cycle", frames=[0, 3]), full[..., [0, 3]])


def test_repeated_and_different_legacy_blocks_are_independent(study):
    full = np.asarray(brkraw.load(str(study)).get_dataobj(5, 1))
    loader = brkraw.load(str(study))
    assert np.array_equal(_legacy(loader, 5, cycle_index=3), full[..., 3:])
    assert np.array_equal(_legacy(loader, 5, cycle_index=0, cycle_count=2), full[..., 0:2])
    assert np.array_equal(_legacy(loader, 5, cycle_index=3), full[..., 3:])


def test_legacy_block_equals_new_style_selection(study):
    loader = brkraw.load(str(study))
    assert _bytes(_legacy(loader, 5, cycle_index=1, cycle_count=2)) == _bytes(
        brkraw.load(str(study)).get_dataobj(5, 1, axis="cycle", frames="1:3"))


def test_convert_after_legacy_call_writes_the_full_scan(study):
    ref = np.asarray(brkraw.load(str(study)).convert(5, reco_id=1).dataobj)
    loader = brkraw.load(str(study))
    _legacy(loader, 5, cycle_index=1, cycle_count=1)
    assert np.array_equal(np.asarray(loader.convert(5, reco_id=1).dataobj), ref)


def test_legacy_call_leaves_the_stored_image_info_alone(study):
    loader = brkraw.load(str(study))
    scan = loader.get_scan(5)
    before = scan.image_info[1]
    _legacy(loader, 5, cycle_index=1, cycle_count=1)
    assert scan.image_info[1] is before
