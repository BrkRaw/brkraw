import numpy as np

from brkraw.resolver.affine import resolve_matvec_and_shape


def test_resolve_matvec_and_shape_variable_slices_per_pack() -> None:
    num_slices = [2, 1, 3]
    slice_thickness = [1.0, 1.0, 1.0]

    total_slices = sum(num_slices)
    base_rotate = np.array([1, 0, 0, 0, 1, 0, 0, 0, 1], dtype=float)
    rotate = np.tile(base_rotate, (total_slices, 1))

    z = np.array([10, 11, 20, 30, 31, 32], dtype=float)
    origin = np.column_stack([np.zeros(total_slices), np.zeros(total_slices), z])

    visu_pars = {
        "VisuCoreDim": 2,
        "VisuCoreOrientation": rotate,
        "VisuCorePosition": origin,
        "VisuCoreExtent": np.array([40.0, 40.0], dtype=float),
        "VisuCoreSize": np.array([256, 256], dtype=float),
    }

    for spack_idx, expected_min_z in enumerate([10.0, 20.0, 30.0]):
        mat, vec, shape = resolve_matvec_and_shape(
            visu_pars, spack_idx, num_slices, slice_thickness
        )
        assert shape == (256, 256, num_slices[spack_idx])
        assert np.allclose(vec, [0.0, 0.0, expected_min_z])
        assert np.allclose(np.diag(mat), [40.0 / 256.0, 40.0 / 256.0, 1.0])

