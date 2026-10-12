"""read_cube: read selected indices of a Fortran-ordered raw array from a binary file (WI-0083).

Synthetic data only. The reference is numpy indexing of the full array.
"""
from __future__ import annotations

import io
import itertools
import zipfile

import numpy as np
import pytest

from brkraw.resolver.rawcube import read_cube


def _full(shape, dtype="<i2", seed=0):
    rng = np.random.default_rng(seed)
    n = int(np.prod(shape))
    if np.dtype(dtype).kind == "f":
        flat = rng.standard_normal(n).astype(dtype)
    else:
        flat = rng.integers(-3000, 3000, size=n).astype(dtype)
    return flat, flat.reshape(shape, order="F")


def _expected(full, indices):
    sel = [np.arange(n) for n in full.shape]
    for ax, idx in indices.items():
        sel[ax] = np.asarray(list(idx))
    return full[np.ix_(*sel)]


def _zip_stream(tmp_path, payload, compression):
    path = tmp_path / "x.zip"
    with zipfile.ZipFile(path, "w", compression=compression) as zf:
        zf.writestr("a/2dseq", payload)
    zf = zipfile.ZipFile(path)
    return zf, zf.open("a/2dseq")


SHAPES = [(5,), (4, 3), (4, 3, 2), (4, 3, 2, 5), (4, 3, 2, 3, 4), (3, 1, 2, 1, 4), (1, 1, 1, 6)]


def _random_indices(shape, rng):
    out = {}
    for ax, n in enumerate(shape):
        mode = rng.integers(0, 4)
        if mode == 0:
            continue  # all
        if mode == 1:
            out[ax] = [int(rng.integers(0, n))]
        elif mode == 2:
            k = int(rng.integers(1, n + 1))
            out[ax] = sorted(int(v) for v in rng.choice(n, size=k, replace=False))
        else:
            lo = int(rng.integers(0, n))
            hi = int(rng.integers(lo + 1, n + 1))
            out[ax] = list(range(lo, hi))
    return out


@pytest.mark.parametrize("shape", SHAPES)
@pytest.mark.parametrize("dtype", ["<i2", "<f4", ">i4", "<u2"])
def test_random_selections_match_numpy_bytesio(shape, dtype):
    flat, full = _full(shape, dtype)
    payload = flat.tobytes()
    rng = np.random.default_rng(5)
    for _ in range(40):
        indices = _random_indices(shape, rng)
        got = read_cube(io.BytesIO(payload), dtype, shape, indices)
        want = _expected(full, indices)
        assert got.dtype == np.dtype(dtype)
        assert got.shape == want.shape
        assert np.array_equal(got, want)
        assert got.flags.writeable is False
        assert got.flags.f_contiguous or got.size <= 1 or max(got.shape) == got.size


@pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_zip_streams_match_numpy(tmp_path, compression):
    shape = (6, 5, 3, 4, 3)
    flat, full = _full(shape)
    zf, stream = _zip_stream(tmp_path, flat.tobytes(), compression)
    try:
        # offsets only increase in one call, as in real use
        for indices in ({4: [2]}, {3: [0, 1, 3], 4: [1, 2]}, {2: [1], 3: [2]}, {0: [1, 2]}, {}):
            got = read_cube(stream, "<i2", shape, indices)
            assert np.array_equal(got, _expected(full, indices))
    finally:
        stream.close()
        zf.close()


def test_real_file(tmp_path):
    shape = (4, 4, 2, 6)
    flat, full = _full(shape)
    p = tmp_path / "2dseq"
    p.write_bytes(flat.tobytes())
    with open(p, "rb") as f:
        got = read_cube(f, "<i2", shape, {3: [5, ]})
    assert np.array_equal(got, full[:, :, :, 5:6])


def test_position_on_entry_does_not_matter():
    shape = (3, 3, 4)
    flat, full = _full(shape)
    buf = io.BytesIO(flat.tobytes())
    buf.seek(7)
    assert np.array_equal(read_cube(buf, "<i2", shape, {2: [1, 3]}), full[:, :, [1, 3]])


def test_only_needed_bytes_are_read():
    shape = (8, 8, 2, 50)
    flat, full = _full(shape)

    class Counting(io.BytesIO):
        n = 0

        def readinto(self, b):
            r = super().readinto(b)
            Counting.n += r or 0
            return r

    Counting.n = 0
    got = read_cube(Counting(flat.tobytes()), "<i2", shape, {3: [10, 11, 40]})
    assert np.array_equal(got, full[:, :, :, [10, 11, 40]])
    assert Counting.n == 8 * 8 * 2 * 3 * 2  # three frames, int16


def test_non_last_axis_reads_one_chunk_per_outer_index():
    shape = (4, 4, 3, 5)  # select z = 1: one chunk of 16 values per (frame)
    flat, full = _full(shape)

    class Counting(io.BytesIO):
        reads = 0

        def readinto(self, b):
            Counting.reads += 1
            return super().readinto(b)

    Counting.reads = 0
    got = read_cube(Counting(flat.tobytes()), "<i2", shape, {2: [1]})
    assert np.array_equal(got, full[:, :, 1:2, :])
    assert Counting.reads == 5


@pytest.mark.parametrize(
    "indices, word",
    [
        ({9: [0]}, "axis"),
        ({-1: [0]}, "axis"),
        ({True: [0]}, "axis"),
        ({"1": [0]}, "axis"),
        ({1: []}, "empty"),
        ({1: [1, 1]}, "indices"),
        ({1: [2, 1]}, "indices"),
        ({1: [-1]}, "indices"),
        ({1: [5]}, "indices"),
    ],
)
def test_validation(indices, word):
    flat, _ = _full((4, 5))
    with pytest.raises(ValueError) as exc:
        read_cube(io.BytesIO(flat.tobytes()), "<i2", (4, 5), indices)
    assert word in str(exc.value)


def test_truncated_file():
    flat, _ = _full((4, 5, 6))
    data = flat.tobytes()[: 4 * 5 * 4 * 2]  # four of six frames
    with pytest.raises(ValueError) as exc:
        read_cube(io.BytesIO(data), "<i2", (4, 5, 6), {2: [5]})
    assert "truncated" in str(exc.value)
    with pytest.raises(ValueError) as exc:
        read_cube(io.BytesIO(data), "<i2", (4, 5, 6), {})
    assert "truncated" in str(exc.value)


def test_numpy_ints_are_accepted():
    flat, full = _full((3, 4))
    got = read_cube(io.BytesIO(flat.tobytes()), "<i2", (3, 4), {1: np.array([1, 3])})
    assert np.array_equal(got, full[:, [1, 3]])


def test_exhaustive_small_shape():
    shape = (2, 3, 2)
    flat, full = _full(shape)
    payload = flat.tobytes()
    axes = range(len(shape))
    subsets = {ax: [list(c) for r in range(1, shape[ax] + 1) for c in itertools.combinations(range(shape[ax]), r)]
               for ax in axes}
    for combo in itertools.product(*[[None] + subsets[ax] for ax in axes]):
        indices = {ax: v for ax, v in zip(axes, combo) if v is not None}
        got = read_cube(io.BytesIO(payload), "<i2", shape, indices)
        assert np.array_equal(got, _expected(full, indices)), indices
