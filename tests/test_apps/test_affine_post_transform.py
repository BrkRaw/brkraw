from __future__ import annotations

import numpy as np
from typing import cast


def test_affine_post_transform_flip_x() -> None:
    from brkraw.apps.loader.helper import _apply_affine_post_transform

    affine = np.eye(4, dtype=float)
    out = _apply_affine_post_transform(affine, kwargs={"flip_x": True})
    assert np.allclose(cast(np.ndarray, out), np.diag([-1.0, 1.0, 1.0, 1.0]))


def test_affine_post_transform_rotation_z() -> None:
    from brkraw.apps.loader.helper import _apply_affine_post_transform

    affine = np.eye(4, dtype=float)
    out = _apply_affine_post_transform(affine, kwargs={"rad_z": np.pi / 2})
    expected = np.array(
        [[0.0, -1.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]],
        dtype=float,
    )
    assert np.allclose(cast(np.ndarray, out), expected, atol=1e-6)


def test_affine_post_transform_tuple() -> None:
    from brkraw.apps.loader.helper import _apply_affine_post_transform

    affine = np.eye(4, dtype=float)
    out = _apply_affine_post_transform((affine, affine), kwargs={"flip_y": True})
    assert isinstance(out, tuple)
    assert len(out) == 2
    assert np.allclose(out[0], np.diag([1.0, -1.0, 1.0, 1.0]))
