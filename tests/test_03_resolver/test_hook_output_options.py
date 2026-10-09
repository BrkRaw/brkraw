"""NIfTI output options and converter hooks (WI-0110, D-0180).

`xyz_units`, `t_units` and `override_header` describe the output file, not how
the data or the affine are read. With a converter hook they must reach the
hook's `convert` (when it takes them or `**kwargs`) and must not be handed to
`get_dataobj`/`get_affine` through `**kwargs`. Before the fix, a hook whose
`get_dataobj` takes `**kwargs` (brkraw-sordino) swallowed the unit options, a
hook that only replaces `convert` (brkraw-dti) never saw them because brkraw's
own `get_dataobj` takes `**kwargs`, and `override_header` never reached any
hook. Synthetic data only."""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pytest
from nibabel.nifti1 import Nifti1Image

import brkraw
from brkraw.apps.loader import helper

from tests.helpers import make_synthetic_study

OUTPUT_KEYS = ("xyz_units", "t_units", "override_header")
HEADER = {"cal_max": 123.0, "descrip": b"wi-0110"}


def _study(tmp_path):
    return make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={5: "EPI"},
                                frames={5: [("FG_CYCLE", 3)]}, slopes={5: [1.0, 1.0, 1.0]})


def _bind(loader, scan_id, hook, name="fakehook"):
    scan = loader.get_scan(scan_id)
    helper.apply_converter_hook(scan, hook)
    scan._converter_hook_name = name
    return scan


def _first(img):
    return img[0] if isinstance(img, tuple) else img


def _image(dataobj, affine, xyz_units="mm", t_units="sec", override_header=None):
    data = dataobj[0] if isinstance(dataobj, tuple) else dataobj
    aff = affine[0] if isinstance(affine, tuple) else affine
    nii = Nifti1Image(np.asarray(data), aff)
    nii.header.set_xyzt_units(xyz_units, t_units)
    for key, value in (override_header or {}).items():
        nii.header[key] = value
    return nii


def _kwargs_hook(seen: Dict[str, Dict[str, Any]]):
    """The brkraw-sordino shape: all three functions take **kwargs."""

    def get_dataobj(scan, reco_id=None, **kwargs):
        seen["get_dataobj"] = dict(kwargs)
        return helper.get_dataobj(scan, reco_id)

    def get_affine(scan, reco_id=None, *, space="subject_ras", override_subject_type=None,
                   override_subject_pose=None, decimals=None, **kwargs):
        seen["get_affine"] = dict(kwargs)
        return helper.get_affine(scan, reco_id, space=space,
                                 override_subject_type=override_subject_type,
                                 override_subject_pose=override_subject_pose, decimals=decimals)

    def convert(scan, dataobj, affine, *, xyz_units="mm", t_units="sec",
                override_header=None, **kwargs):
        seen["convert"] = dict(kwargs, xyz_units=xyz_units, t_units=t_units,
                               override_header=override_header)
        return _image(dataobj, affine, xyz_units, t_units, override_header)

    return {"get_dataobj": get_dataobj, "get_affine": get_affine, "convert": convert}


# ---------------------------------------------------------------------------
# sordino shape: **kwargs everywhere
# ---------------------------------------------------------------------------


def test_kwargs_hook_convert_gets_units_and_header(tmp_path):
    seen: Dict[str, Dict[str, Any]] = {}
    loader = brkraw.load(str(_study(tmp_path)))
    _bind(loader, 5, _kwargs_hook(seen))
    img = _first(loader.convert(5, reco_id=1, xyz_units="micron", t_units="msec",
                                override_header=HEADER))
    assert seen["convert"]["xyz_units"] == "micron"
    assert seen["convert"]["t_units"] == "msec"
    assert seen["convert"]["override_header"] == HEADER
    assert img.header.get_xyzt_units() == ("micron", "msec")
    assert float(img.header["cal_max"]) == 123.0


def test_kwargs_hook_read_functions_do_not_get_output_options(tmp_path):
    # sordino warns "ignoring unknown option(s): t_units, xyz_units" when they arrive here
    seen: Dict[str, Dict[str, Any]] = {}
    loader = brkraw.load(str(_study(tmp_path)))
    _bind(loader, 5, _kwargs_hook(seen))
    loader.convert(5, reco_id=1, xyz_units="micron", t_units="msec", override_header=HEADER)
    for name in ("get_dataobj", "get_affine"):
        assert not set(OUTPUT_KEYS) & set(seen[name]), (name, sorted(seen[name]))


def test_kwargs_hook_options_still_reach_the_read_functions(tmp_path):
    # hook options (hook_args_by_name) keep their old route: get_dataobj takes **kwargs,
    # so it gets them, and convert does not (unchanged)
    seen: Dict[str, Dict[str, Any]] = {}
    loader = brkraw.load(str(_study(tmp_path)))
    _bind(loader, 5, _kwargs_hook(seen))
    loader.convert(5, reco_id=1, xyz_units="micron", t_units="msec",
                   hook_args_by_name={"fakehook": {"my_option": 7}})
    assert seen["get_dataobj"].get("my_option") == 7
    assert seen["get_affine"].get("my_option") == 7
    assert "my_option" not in seen["convert"]
    assert seen["convert"]["xyz_units"] == "micron"


def test_default_units_reach_the_hook_too(tmp_path):
    seen: Dict[str, Dict[str, Any]] = {}
    loader = brkraw.load(str(_study(tmp_path)))
    _bind(loader, 5, _kwargs_hook(seen))
    loader.convert(5, reco_id=1, xyz_units="mm", t_units="sec")
    assert (seen["convert"]["xyz_units"], seen["convert"]["t_units"]) == ("mm", "sec")
    assert "xyz_units" not in seen["get_dataobj"]


def test_no_override_header_is_not_passed(tmp_path):
    got: Dict[str, Any] = {}

    def convert(scan, dataobj, affine, **kwargs):
        got.update(kwargs)
        return None

    loader = brkraw.load(str(_study(tmp_path)))
    _bind(loader, 5, {"convert": convert})
    loader.convert(5, reco_id=1)
    assert "override_header" not in got


# ---------------------------------------------------------------------------
# dti shape: only convert, reading the options from **kwargs
# ---------------------------------------------------------------------------


def test_convert_only_hook_gets_units_and_header(tmp_path):
    got: Dict[str, Any] = {}

    def convert(scan, dataobj, affine, **kwargs):
        got.update(kwargs)
        return _image(dataobj, affine, kwargs.get("xyz_units", "mm"),
                      kwargs.get("t_units", "sec"), kwargs.get("override_header"))

    loader = brkraw.load(str(_study(tmp_path)))
    _bind(loader, 5, {"convert": convert})
    img = _first(loader.convert(5, reco_id=1, xyz_units="micron", t_units="msec",
                                override_header=HEADER))
    assert got["xyz_units"] == "micron" and got["t_units"] == "msec"
    assert got["override_header"] == HEADER
    assert got["reco_id"] == 1
    assert img.header.get_xyzt_units() == ("micron", "msec")


# ---------------------------------------------------------------------------
# hooks that do not take the options keep working
# ---------------------------------------------------------------------------


def test_convert_without_kwargs_is_called_without_the_options(tmp_path):
    calls = []

    def convert(scan, dataobj, affine):
        calls.append(True)
        return None

    loader = brkraw.load(str(_study(tmp_path)))
    _bind(loader, 5, {"convert": convert})
    loader.convert(5, reco_id=1, xyz_units="micron", t_units="msec", override_header=HEADER)
    assert calls == [True]


def test_convert_naming_only_xyz_units_gets_only_that(tmp_path):
    got = []

    def convert(scan, dataobj, affine, xyz_units="mm"):
        got.append(xyz_units)
        return None

    loader = brkraw.load(str(_study(tmp_path)))
    _bind(loader, 5, {"convert": convert})
    loader.convert(5, reco_id=1, xyz_units="micron", t_units="msec", override_header=HEADER)
    assert got == ["micron"]


def test_read_functions_without_kwargs_send_hook_options_to_convert(tmp_path):
    # the brkraw-mrs shape: no **kwargs in get_dataobj/get_affine
    got: Dict[str, Any] = {}

    def get_dataobj(scan, reco_id=None):
        return helper.get_dataobj(scan, reco_id)

    def get_affine(scan, reco_id=None, *, space=None, override_subject_type=None,
                   override_subject_pose=None, decimals=None):
        return helper.get_affine(scan, reco_id, decimals=decimals)

    def convert(scan, dataobj, affine, **kwargs):
        got.update(kwargs)
        return None

    loader = brkraw.load(str(_study(tmp_path)))
    _bind(loader, 5, {"get_dataobj": get_dataobj, "get_affine": get_affine, "convert": convert})
    loader.convert(5, reco_id=1, xyz_units="micron", t_units="msec",
                   hook_args_by_name={"fakehook": {"my_option": 7}})
    assert got["my_option"] == 7
    assert got["xyz_units"] == "micron" and got["t_units"] == "msec"


def test_read_function_that_names_an_output_option_still_gets_it(tmp_path):
    # an explicit parameter is a declaration: keep passing it, and convert gets it too
    seen: Dict[str, Optional[str]] = {}

    def get_dataobj(scan, reco_id=None, xyz_units=None, **kwargs):
        seen["get_dataobj"] = xyz_units
        seen["get_dataobj_t_units"] = kwargs.get("t_units")
        return helper.get_dataobj(scan, reco_id)

    def convert(scan, dataobj, affine, *, xyz_units="mm", t_units="sec", **kwargs):
        seen["convert"] = xyz_units
        seen["convert_t_units"] = t_units
        return None

    loader = brkraw.load(str(_study(tmp_path)))
    _bind(loader, 5, {"get_dataobj": get_dataobj, "convert": convert})
    loader.convert(5, reco_id=1, xyz_units="micron", t_units="msec")
    assert seen == {"get_dataobj": "micron", "get_dataobj_t_units": None,
                    "convert": "micron", "convert_t_units": "msec"}


# ---------------------------------------------------------------------------
# no hook: unchanged
# ---------------------------------------------------------------------------


def test_default_path_applies_units_and_header(tmp_path):
    loader = brkraw.load(str(_study(tmp_path)))
    img = _first(loader.convert(5, reco_id=1, xyz_units="micron", t_units="msec",
                                override_header=HEADER))
    assert img.header.get_xyzt_units() == ("micron", "msec")
    assert float(img.header["cal_max"]) == 123.0


@pytest.mark.parametrize("units", [("mm", "sec"), ("micron", "msec")])
def test_default_path_data_and_affine_unchanged_by_units(tmp_path, units):
    st = _study(tmp_path)
    ref = _first(brkraw.load(str(st)).convert(5, reco_id=1))
    img = _first(brkraw.load(str(st)).convert(5, reco_id=1, xyz_units=units[0], t_units=units[1]))
    assert np.array_equal(np.asarray(img.dataobj), np.asarray(ref.dataobj))
    assert np.array_equal(img.affine, ref.affine)
