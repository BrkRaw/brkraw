"""get_dataobj reads only the needed frames of 2dseq (WI-0083, D-0106). Synthetic data only.

Reference for every comparison: the same call with the partial path switched off
(``image_resolver.PARTIAL_READ = False``), which is the 0.6.0 behavior (read all,
then cut). Values must be bit-identical and the array properties that brkraw
uses (``flags``, dtype, shape, type) must be the same, because ``convert -F``
picks its flatten order from the flags.
"""
from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import numpy as np
import pytest

import brkraw
from brkraw.cli.main import main
from brkraw.resolver import image as image_resolver

from tests.helpers import make_synthetic_study

# layout name -> (make_synthetic_study kwargs, frame axis names in data order after the z swap)
LAYOUTS = {
    "cycle": ({"frames": {5: [("FG_CYCLE", 7)]}}, ["cycle"]),
    "echo_cycle": ({"frames": {5: [("FG_ECHO", 2), ("FG_CYCLE", 5)]}}, ["echo", "cycle"]),
    "packs_cycle": ({"frames": {5: [("FG_CYCLE", 4)]}, "packs": {5: 2}}, ["cycle"]),
    "echo_slice_swap": ({"frames": {5: [("FG_ECHO", 2), ("FG_SLICE", 3)]}, "packs": {5: 3}}, ["echo"]),
    "slice_echo_cycle": (
        {"frames": {5: [("FG_SLICE", 2), ("FG_ECHO", 2), ("FG_CYCLE", 3)]}, "packs": {5: 2}},
        ["echo", "cycle"],
    ),
    # the frame axes after the first are not size 2, so lists of 2 of 3 on a non-last axis are covered
    "echo3_cycle3": ({"frames": {5: [("FG_ECHO", 3), ("FG_CYCLE", 3)]}}, ["echo", "cycle"]),
    "three_axes": (
        {"frames": {5: [("FG_ECHO", 3), ("FG_DIFFUSION", 2), ("FG_CYCLE", 3)]}},
        ["echo", "diffusion", "cycle"],
    ),
    "packs_three_axes": (
        {"frames": {5: [("FG_SLICE", 2), ("FG_ECHO", 3), ("FG_DIFFUSION", 2), ("FG_CYCLE", 2)]}, "packs": {5: 2}},
        ["echo", "diffusion", "cycle"],
    ),
}

SELECTIONS = [
    0, -1, 1,
    [1], [2, 0], [0, 1], (2, 0),
    "0:2", "1:", ":2", "::2", "::-1", "1:3", "-2:",
]


def _build(tmp_path: Path, layout: str, source: str) -> str:
    kwargs, _ = LAYOUTS[layout]
    study = make_synthetic_study(tmp_path / "study", pv="360.3.3", scans={5: "EPI"}, **kwargs)
    if source == "folder":
        return str(study)
    comp = zipfile.ZIP_STORED if source == "stored" else zipfile.ZIP_DEFLATED
    zpath = tmp_path / f"{source}.zip"
    with zipfile.ZipFile(zpath, "w", compression=comp) as zf:
        for p in sorted(study.rglob("*")):
            if p.is_file():
                zf.write(p, f"synthfolder/{p.relative_to(study).as_posix()}")
    return str(zpath)


def _props(a):
    return (type(a), a.dtype, a.shape, a.flags.f_contiguous, a.flags.c_contiguous, a.flags.writeable)


def _as_tuple(x):
    return x if isinstance(x, tuple) else (x,)


def _get(path, **kwargs):
    return brkraw.load(path).get_dataobj(5, 1, **kwargs)


def _reference(path, **kwargs):
    old = image_resolver.PARTIAL_READ
    image_resolver.PARTIAL_READ = False
    try:
        return _get(path, **kwargs)
    finally:
        image_resolver.PARTIAL_READ = old


def _same(new, ref):
    new, ref = _as_tuple(new), _as_tuple(ref)
    assert len(new) == len(ref)
    for n, r in zip(new, ref):
        assert _props(n) == _props(r)
        assert np.array_equal(n, r)
        assert n.tobytes() == r.tobytes()


@pytest.mark.parametrize("source", ["folder", "stored", "deflated"])
@pytest.mark.parametrize("layout", list(LAYOUTS))
def test_frames_equal_the_full_read_for_every_selection(tmp_path, layout, source):
    path = _build(tmp_path, layout, source)
    names = LAYOUTS[layout][1]
    for axis in names:
        for frames in SELECTIONS:
            n = len(names)
            try:
                ref = _reference(path, axis=axis, frames=frames)
            except Exception as exc:  # the same error must come from the new path
                with pytest.raises(type(exc)) as got:
                    _get(path, axis=axis, frames=frames)
                assert str(got.value) == str(exc)
                continue
            _same(_get(path, axis=axis, frames=frames), ref)
            assert n >= 1


def test_axis_by_number_and_single_axis_default(tmp_path):
    path = _build(tmp_path, "echo_cycle", "stored")
    _same(_get(path, axis=4, frames=[3, 1]), _reference(path, axis=4, frames=[3, 1]))
    _same(_get(path, axis=3, frames=1), _reference(path, axis=3, frames=1))
    path = _build(tmp_path / "b", "cycle", "stored")
    _same(_get(path, frames="2:5"), _reference(path, frames="2:5"))


def test_errors_are_the_same_as_before(tmp_path):
    path = _build(tmp_path, "cycle", "stored")
    for kwargs in ({"axis": "cycle", "frames": 99}, {"axis": "echo", "frames": 0},
                   {"axis": "cycle", "frames": [1, 1]}, {"axis": "cycle", "frames": "x"},
                   {"axis": "cycle", "frames": "3:3"}, {"frames": True}):
        with pytest.raises(Exception) as ref:
            _reference(path, **kwargs)
        with pytest.raises(type(ref.value)) as got:
            _get(path, **kwargs)
        assert str(got.value) == str(ref.value)


def test_clamped_slice_warning_is_logged_once_per_pack(tmp_path, caplog):
    path = _build(tmp_path, "packs_cycle", "stored")
    with caplog.at_level("WARNING"):
        _get(path, axis="cycle", frames="1:99")
    new = [r.getMessage() for r in caplog.records if "reaches past" in r.getMessage()]
    caplog.clear()
    image_resolver.PARTIAL_READ = False
    try:
        with caplog.at_level("WARNING"):
            _get(path, axis="cycle", frames="1:99")
    finally:
        image_resolver.PARTIAL_READ = True
    old = [r.getMessage() for r in caplog.records if "reaches past" in r.getMessage()]
    assert new == old and len(old) == 2


class _Spy:
    """Capture the raw streams open_2dseq hands out."""

    def __init__(self, monkeypatch):
        self.streams = []
        real = image_resolver.open_2dseq

        def spy(reco):
            s = real(reco)
            self.streams.append(s)
            return s

        monkeypatch.setattr(image_resolver, "open_2dseq", spy)

    @property
    def bytes_read(self):
        return sum(s.bytes_read for s in self.streams)


@pytest.mark.parametrize("source", ["folder", "stored", "deflated"])
def test_only_the_needed_frames_are_read(tmp_path, monkeypatch, source):
    path = _build(tmp_path, "cycle", source)
    size = 16 * 7 * 2  # 2dseq bytes: 4x4 int16, 7 cycles
    spy = _Spy(monkeypatch)
    got = _get(path, axis="cycle", frames=[1, 5])
    assert got.shape == (4, 4, 1, 2)
    assert len(spy.streams) == 1
    assert spy.bytes_read == 16 * 2 * 2 < size


@pytest.mark.parametrize("source", ["folder", "stored", "deflated"])
def test_full_read_opens_the_file_once(tmp_path, monkeypatch, source):
    path = _build(tmp_path, "cycle", source)
    spy = _Spy(monkeypatch)
    reads = []
    real_read = zipfile.ZipFile.read

    def counting_read(self, name, pwd=None):
        reads.append(name)
        return real_read(self, name, pwd)

    monkeypatch.setattr(zipfile.ZipFile, "read", counting_read)
    study = brkraw.load(path)
    reads.clear()
    full = study.get_dataobj(5, 1)
    assert full.shape == (4, 4, 1, 7)
    assert len(spy.streams) == 1
    assert not [n for n in reads if n.endswith("2dseq")]
    expected = np.arange(16 * 7, dtype="<i2").reshape((4, 4, 1, 7), order="F")
    assert np.array_equal(full, expected)
    assert full.dtype == np.dtype("<i2")
    assert full.flags.writeable is False and full.flags.f_contiguous


def test_cached_full_data_is_used_when_present(tmp_path, monkeypatch):
    path = _build(tmp_path, "cycle", "stored")
    study = brkraw.load(path)
    full = study.get_dataobj(5, 1)
    spy = _Spy(monkeypatch)
    part = study.get_dataobj(5, 1, axis="cycle", frames="2:4")
    assert spy.streams == []
    assert np.array_equal(part, full[..., 2:4])


def test_partial_result_is_not_kept_as_the_scan_data(tmp_path):
    path = _build(tmp_path, "cycle", "stored")
    study = brkraw.load(path)
    part = study.get_dataobj(5, 1, axis="cycle", frames=[1])
    assert part.shape == (4, 4, 1, 1)
    full = study.get_dataobj(5, 1)
    assert full.shape == (4, 4, 1, 7)
    assert np.array_equal(full[..., 1:2], part)


def test_selecting_everything_reads_everything_like_before(tmp_path):
    path = _build(tmp_path, "cycle", "deflated")
    _same(_get(path, axis="cycle", frames="0:7"), _reference(path, axis="cycle", frames="0:7"))
    _same(_get(path, axis="cycle", frames=list(range(7))), _reference(path, axis="cycle", frames=list(range(7))))


def test_legacy_cycle_block_equals_the_full_read_and_reads_less(tmp_path, monkeypatch):
    path = _build(tmp_path, "cycle", "deflated")
    spy = _Spy(monkeypatch)
    with pytest.warns(DeprecationWarning):
        got = brkraw.load(path).get_dataobj(5, 1, cycle_index=2, cycle_count=3)
    assert spy.bytes_read == 16 * 3 * 2
    expected = np.arange(16 * 7, dtype="<i2").reshape((4, 4, 1, 7), order="F")[..., 2:5]
    assert np.array_equal(got, expected)
    assert got.dtype == np.dtype("<i2")


def _nii_bytes(path, tmp_path, name, *extra):
    out = tmp_path / name
    assert main(["convert", path, "-s", "5", "-o", str(out), "--no-context-map", *extra]) == 0
    import nibabel as nib
    img = nib.load(str(out))
    return np.asarray(img.dataobj).tobytes(), img.shape, img.header.get_data_dtype()


@pytest.mark.parametrize("source", ["folder", "deflated"])
@pytest.mark.parametrize("flatten", [False, True])
@pytest.mark.parametrize("axis, frames", [("echo", "1:"), ("cycle", "0:2"), ("cycle", "::2"), ("echo", 0), ("cycle", [3, 1])])
def test_convert_output_is_the_same_with_and_without_flatten(tmp_path, source, flatten, axis, frames):
    path = _build(tmp_path, "echo_cycle", source)
    extra = ["--axis", axis, "--frames", str(frames).replace(" ", "")] if not isinstance(frames, list) else \
        ["--axis", axis, "--frames", ",".join(map(str, frames))]
    if flatten:
        extra.append("-F")
    new = _nii_bytes(path, tmp_path, "new.nii.gz", *extra)
    image_resolver.PARTIAL_READ = False
    try:
        old = _nii_bytes(path, tmp_path, "old.nii.gz", *extra)
    finally:
        image_resolver.PARTIAL_READ = True
    assert new == old


def test_hash_of_full_read_is_stable(tmp_path):
    path = _build(tmp_path, "slice_echo_cycle", "stored")
    out = _as_tuple(_get(path))
    h = hashlib.sha256(b"".join(a.tobytes() for a in out)).hexdigest()
    image_resolver.PARTIAL_READ = False
    try:
        out2 = _as_tuple(_get(path))
    finally:
        image_resolver.PARTIAL_READ = True
    assert h == hashlib.sha256(b"".join(a.tobytes() for a in out2)).hexdigest()


def _big_study(tmp_path: Path, side: int = 64, cycles: int = 2000):
    """A study whose 2dseq is side x side x cycles int16 (about 16 MB for the defaults)."""
    study = make_synthetic_study(tmp_path / "bigstudy", pv="360.3.3", scans={5: "EPI"},
                                 frames={5: [("FG_CYCLE", cycles)]})
    pdir = study / "5" / "pdata" / "1"
    visu = (pdir / "visu_pars").read_text()
    assert "( 2 )\n4 4" in visu
    (pdir / "visu_pars").write_text(visu.replace("( 2 )\n4 4", f"( 2 )\n{side} {side}", 1))
    rng = np.random.default_rng(1)
    data = rng.integers(0, 4000, size=side * side * cycles, dtype=np.int16)
    (pdir / "2dseq").write_bytes(data.astype("<i2").tobytes())
    return study, data.reshape((side, side, 1, cycles), order="F")


@pytest.mark.parametrize("source", ["folder", "stored", "deflated"])
def test_memory_stays_small_for_a_few_frames(tmp_path, source):
    import tracemalloc

    study, expected = _big_study(tmp_path)
    if source == "folder":
        path = str(study)
    else:
        comp = zipfile.ZIP_STORED if source == "stored" else zipfile.ZIP_DEFLATED
        path = str(tmp_path / f"big-{source}.zip")
        with zipfile.ZipFile(path, "w", compression=comp) as zf:
            for p in sorted(study.rglob("*")):
                if p.is_file():
                    zf.write(p, f"synthfolder/{p.relative_to(study).as_posix()}")
    size = expected.nbytes
    loaded = brkraw.load(path)
    tracemalloc.start()
    try:
        got = loaded.get_dataobj(5, 1, axis="cycle", frames=[1500, 1501])
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert np.array_equal(got, expected[..., [1500, 1501]])
    assert peak < size / 4, (peak, size)
    loaded = brkraw.load(path)
    tracemalloc.start()
    try:
        full = loaded.get_dataobj(5, 1)
        _, peak_full = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert np.array_equal(full, expected)
    assert peak_full < size * 1.6, (peak_full, size)  # the full read holds the data once, not twice


def _rewrite_2dseq(tmp_path: Path, source: str, new_size: int) -> str:
    """A cycle study whose 2dseq has new_size bytes (cut or padded), as folder or stored/deflated zip."""
    study = make_synthetic_study(tmp_path / "bad", pv="360.3.3", scans={5: "EPI"}, frames={5: [("FG_CYCLE", 7)]})
    f = study / "5" / "pdata" / "1" / "2dseq"
    data = f.read_bytes()
    f.write_bytes((data + bytes(new_size))[:new_size])
    if source == "folder":
        return str(study)
    comp = zipfile.ZIP_STORED if source == "stored" else zipfile.ZIP_DEFLATED
    zpath = tmp_path / f"bad-{source}.zip"
    with zipfile.ZipFile(zpath, "w", compression=comp) as zf:
        for p in sorted(study.rglob("*")):
            if p.is_file():
                zf.write(p, f"synthfolder/{p.relative_to(study).as_posix()}")
    return str(zpath)


@pytest.mark.parametrize("source", ["folder", "stored", "deflated"])
@pytest.mark.parametrize("new_size", [16 * 7 * 2 - 32, 16 * 7 * 2 + 32])
def test_wrong_sized_2dseq_gives_the_same_error_for_frames_and_full_reads(tmp_path, source, new_size):
    path = _rewrite_2dseq(tmp_path, source, new_size)
    for kwargs in ({}, {"axis": "cycle", "frames": [1, 5]}, {"axis": "cycle", "frames": 0}):
        with pytest.raises(ValueError) as ref:
            _reference(path, **kwargs)
        assert "size mismatch" in str(ref.value)
        with pytest.raises(ValueError) as got:
            _get(path, **kwargs)
        assert str(got.value) == str(ref.value)


@pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_raw_stream_skip_ahead_keeps_memory_small_on_every_python(tmp_path, compression):
    """WI-0090: a seek far ahead in a zip entry must not read the skipped bytes into memory at once.

    ZipExtFile.seek jumps directly in a stored entry only from Python 3.12; before that it
    reads (up to 16 MiB per step) and keeps what it skipped, so RawStream must skip in small steps.
    """
    import tracemalloc

    frame = 64 * 64 * 2
    payload = bytes(range(256)) * (frame * 2000 // 256)
    zpath = tmp_path / "raw.zip"
    with zipfile.ZipFile(zpath, "w", compression=compression) as zf:
        zf.writestr("a/2dseq", payload)
    with zipfile.ZipFile(zpath) as zf:
        tracemalloc.start()
        try:
            with image_resolver.RawStream(lambda: zf.open("a/2dseq"), len(payload)) as s:
                s.seek(1500 * frame)
                buf = bytearray(2 * frame)
                assert s.readinto(buf) == 2 * frame
                _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
    assert bytes(buf) == payload[1500 * frame:1502 * frame]
    assert peak < len(payload) / 4, (peak, len(payload))
