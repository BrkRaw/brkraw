import numpy as np
from nibabel.nifti1 import Nifti1Image

from brkraw.resolver import nifti


def test_update_keeps_uniform_array_scaling_in_header():
    dataobj = np.asarray([[[1, 2, 3]]], dtype=np.int16)
    niiobj = Nifti1Image(dataobj, np.eye(4))

    nifti.update(
        niiobj,
        {
            "slope_inter": (
                np.asarray([2.0, 2.0, 2.0]),
                np.asarray([10.0, 10.0, 10.0]),
            ),
        },
    )

    np.testing.assert_array_equal(np.asarray(niiobj.dataobj), dataobj)
    assert niiobj.header.get_slope_inter() == (2.0, 10.0)


def test_update_applies_distinct_array_scaling_to_dataobj():
    dataobj = np.asarray([[[1, 2, 3]]], dtype=np.int16)
    niiobj = Nifti1Image(dataobj, np.eye(4))

    nifti.update(
        niiobj,
        {
            "slope_inter": (
                np.asarray([1.0, 2.0, 3.0]),
                np.asarray([0.0, 10.0, 20.0]),
            ),
        },
    )

    np.testing.assert_allclose(np.asarray(niiobj.dataobj), np.asarray([[[1.0, 14.0, 29.0]]]))
    assert niiobj.header.get_slope_inter() == (1.0, 0.0)
