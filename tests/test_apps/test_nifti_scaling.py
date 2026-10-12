from pathlib import Path
from typing import cast

import numpy as np
import pytest
from nibabel.nifti1 import Nifti1Image

from brkraw.apps.loader import helper
from brkraw.core.fs import DatasetFS
from brkraw.dataclasses.scan import Scan


class DummyScan(Scan):
    def __init__(self, image_info, affine_info):
        super().__init__(fs=DatasetFS(root=Path("."), _mode="dir", _zip=None), scan_id=0, relroot="")
        self.image_info = image_info
        self.affine_info = affine_info


def _make_scan(*, dataobj, slope, offset, num_slices):
    image_info = {
        1: {
            "dataobj": dataobj,
            "slope": slope,
            "offset": offset,
            "shape_desc": ["read", "phase", "slice"],
            "sliceorder_scheme": None,
            "num_cycles": 1,
            "time_per_cycle": None,
        }
    }
    affine_info = {
        1: {
            "num_slices": num_slices,
        }
    }
    return DummyScan(image_info=image_info, affine_info=affine_info)


def test_get_nifti1image_keeps_scalar_scaling_in_header():
    dataobj = np.asarray([[[1, 2]]], dtype=np.int16)
    scan = _make_scan(dataobj=dataobj, slope=2.0, offset=10.0, num_slices=[2])

    niiobj = helper.get_nifti1image(
        scan,
        reco_id=1,
        dataobjs=(dataobj,),
        affines=(np.eye(4),),
    )

    assert niiobj is not None
    assert isinstance(niiobj, Nifti1Image)
    np.testing.assert_array_equal(np.asarray(niiobj.dataobj), dataobj)
    assert niiobj.header.get_slope_inter() == (2.0, 10.0)


def test_get_nifti1image_applies_per_slice_scaling_to_dataobj():
    dataobj = np.asarray([[[1, 2, 3]]], dtype=np.int16)
    scan = _make_scan(
        dataobj=dataobj,
        slope=[1.0, 2.0, 3.0],
        offset=[0.0, 10.0, 20.0],
        num_slices=[3],
    )

    niiobj = helper.get_nifti1image(
        scan,
        reco_id=1,
        dataobjs=(dataobj,),
        affines=(np.eye(4),),
    )

    assert niiobj is not None
    assert isinstance(niiobj, Nifti1Image)
    np.testing.assert_allclose(np.asarray(niiobj.dataobj), np.asarray([[[1.0, 14.0, 29.0]]]))
    assert niiobj.header.get_slope_inter() == (1.0, 0.0)


def test_get_nifti1image_keeps_per_pack_uniform_scaling_in_each_header():
    pack1 = np.asarray([[[1, 2]]], dtype=np.int16)
    pack2 = np.asarray([[[3]]], dtype=np.int16)
    full = np.concatenate([pack1, pack2], axis=2)
    scan = _make_scan(
        dataobj=full,
        slope=[2.0, 3.0],
        offset=[5.0, 7.0],
        num_slices=[2, 1],
    )

    niiobj = helper.get_nifti1image(
        scan,
        reco_id=1,
        dataobjs=(pack1, pack2),
        affines=(np.eye(4), np.eye(4)),
    )

    assert isinstance(niiobj, tuple)
    assert len(niiobj) == 2
    first_img = cast(Nifti1Image, niiobj[0])
    second_img = cast(Nifti1Image, niiobj[1])
    np.testing.assert_array_equal(np.asarray(first_img.dataobj), pack1)
    np.testing.assert_array_equal(np.asarray(second_img.dataobj), pack2)
    assert first_img.header.get_slope_inter() == (2.0, 5.0)
    assert second_img.header.get_slope_inter() == (3.0, 7.0)


def test_get_nifti1image_override_slope_inter_replaces_native_scaling():
    dataobj = np.asarray([[[1, 2, 3]]], dtype=np.int16)
    scan = _make_scan(
        dataobj=dataobj,
        slope=[1.0, 2.0, 3.0],
        offset=[0.0, 10.0, 20.0],
        num_slices=[3],
    )

    niiobj = helper.get_nifti1image(
        scan,
        reco_id=1,
        dataobjs=(dataobj,),
        affines=(np.eye(4),),
        override_header={"slope_inter": (4.0, 5.0)},
    )

    assert niiobj is not None
    assert isinstance(niiobj, Nifti1Image)
    np.testing.assert_array_equal(np.asarray(niiobj.dataobj), dataobj)
    assert niiobj.header.get_slope_inter() == (4.0, 5.0)


def test_get_nifti1image_rejects_invalid_scaling_length():
    dataobj = np.asarray([[[1, 2, 3]]], dtype=np.int16)
    scan = _make_scan(
        dataobj=dataobj,
        slope=[1.0, 2.0, 3.0, 4.0],
        offset=0.0,
        num_slices=[3],
    )

    with pytest.raises(ValueError, match="VisuCoreDataSlope has 4 values"):
        helper.get_nifti1image(
            scan,
            reco_id=1,
            dataobjs=(dataobj,),
            affines=(np.eye(4),),
        )
