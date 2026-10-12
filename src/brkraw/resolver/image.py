"""
Load Paravision `2dseq` data into a NumPy array with geometry metadata.

This resolver reads dtype/slope/offset and shape info for a given `Scan`/`Reco`,
then reshapes the `2dseq` buffer (Fortran order) and normalizes axis labels so
the spatial z-axis sits at index 2. Returns None when required metadata or
files are missing.
"""
from __future__ import annotations


from typing import IO, TYPE_CHECKING, Any, Callable, Optional, Sequence, TypedDict, List, Tuple, Union
import logging
import os
import sys
import zipfile
from .datatype import resolve as datatype_resolver
from .shape import resolve as shape_resolver
from .helpers import get_reco, get_file, swap_element
from .rawcube import read_cube
import numpy as np

if TYPE_CHECKING:
    from ..dataclasses import Scan, Reco
    from .shape import ResolvedShape
    from .shape import ResolvedCycle


class ResolvedImage(TypedDict):
    dataobj: Optional[np.ndarray]
    slope: Union[float, Sequence[float], np.ndarray]
    offset: Union[float, Sequence[float], np.ndarray]
    shape_desc: Optional[List[str]]
    sliceorder_scheme: Optional[str]
    num_cycles: int
    time_per_cycle: Optional[float]


Z_AXIS_DESCRIPTORS = {'spatial', 'slice', 'without_slice'}
logger = logging.getLogger("brkraw.resolver.image")

# WI-0083 (D-0106): read only the frames a caller asks for. False switches back to
# the 0.6.0 way (read all of 2dseq, then cut); tests use it as the reference.
PARTIAL_READ = True

_SKIP_CHUNK = 256 << 10
_IO_CHUNK = 1 << 20  # a zip entry builds a temporary copy of what one call reads: keep calls small


class RawStream:
    """A 2dseq entry opened as a stream that can seek, and counts the bytes it reads.

    Folder files seek directly, and so do stored zip entries on Python 3.12 and later.
    Before 3.12, ZipExtFile.seek on a stored entry reads the skipped bytes (up to 16 MiB
    in one piece) instead of jumping, and a compressed entry can only be read forward
    on every version. For those a seek ahead reads and drops the bytes in small steps
    (memory stays bounded), a seek back opens the entry again.
    """

    def __init__(self, opener: Callable[[], IO[bytes]], size: Optional[int] = None) -> None:
        self._opener = opener
        self._f = opener()
        self._pos = 0
        self.size = size
        self.bytes_read = 0
        compress = getattr(self._f, "_compress_type", None)  # None: not a zip entry (plain file)
        self._direct = compress is None or (compress == zipfile.ZIP_STORED and sys.version_info >= (3, 12))

    def seek(self, pos: int) -> int:
        pos = int(pos)
        if self._direct:
            self._f.seek(pos)
            self._pos = pos
            return pos
        if pos < self._pos:
            self._f.close()
            self._f = self._opener()
            self._pos = 0
        left = pos - self._pos
        if left:
            scratch = bytearray(min(left, _SKIP_CHUNK))
            while left > 0:
                got = self._f.readinto(memoryview(scratch)[: min(left, _SKIP_CHUNK)])
                if not got:
                    break
                left -= got
                self._pos += got
        return self._pos

    def readinto(self, buf: Any) -> Optional[int]:
        view = memoryview(buf).cast("B")
        done = 0
        while done < len(view):
            got = self._f.readinto(view[done: done + _IO_CHUNK])
            if not got:
                break
            done += got
        self._pos += done
        self.bytes_read += done
        return done

    def read(self, n: int = -1) -> bytes:
        data = self._f.read(n)
        self._pos += len(data)
        self.bytes_read += len(data)
        return data

    def close(self) -> None:
        self._f.close()

    def __enter__(self) -> "RawStream":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def _entry_size(entry: Any) -> Optional[int]:
    """Size in bytes of a file entry (zip entry or folder file), None when unknown."""
    try:
        zipobj = getattr(entry, "zipobj", None)
        if zipobj is not None:
            return int(zipobj.getinfo(entry.arcname).file_size)
        return int(os.stat(entry.fs.root / entry.fs._normalize_relpath(entry.path)).st_size)
    except Exception:
        return None


def open_2dseq(reco: "Reco") -> RawStream:
    """Open the reco's 2dseq as a stream without reading the file into memory.

    Raises FileNotFoundError when the reco has no 2dseq.
    """
    resolve_entry = getattr(reco, "_resolve_entry", None)
    if resolve_entry is None:  # not a dataset node (for example a test double): old way
        return RawStream(lambda: get_file(reco, "2dseq"))
    entry = resolve_entry(reco._full_path("2dseq"))
    if entry is None:
        raise FileNotFoundError("2dseq")
    return RawStream(entry.open, _entry_size(entry))


def _read_exact(f: Any, nbytes: int) -> bytearray:
    """Read up to nbytes into a new buffer (shorter only at the end of the file)."""
    buf = bytearray(nbytes)
    view = memoryview(buf)
    done = 0
    while done < nbytes:
        got = f.readinto(view[done:])
        if not got:
            break
        done += got
    return buf if done == nbytes else buf[:done]


def _readonly_array(buf: bytearray, dtype: np.dtype) -> np.ndarray:
    return np.frombuffer(memoryview(buf).toreadonly(), dtype)


def _find_z_axis_candidate(shape_desc: Sequence[str]) -> Optional[int]:
    """Return the first spatial z-axis descriptor index found at/after position 2."""
    for idx, desc in enumerate(shape_desc):
        if idx < 2:
            continue
        if desc in Z_AXIS_DESCRIPTORS:
            return idx
    return None


def _normalize_zaxis_descriptor(shape_desc: List[str]) -> List[str]:
    """Ensure the z-axis descriptor uses 'slice' to represent spatial depth."""
    normalized = shape_desc[:]
    if normalized[2] == 'without_slice':
        normalized[2] = 'slice'
    return normalized


def _validate_swapped_axes(
    dataobj: np.ndarray,
    expected_shape: Sequence[int],
    shape_desc: List[str],
    original_zaxis_desc: str,
    swapped_idx: int,
):
    """Validate shape/descriptor invariants after moving spatial z-axis into position 2."""
    if dataobj.shape != tuple(expected_shape):
        raise ValueError(f"data shape {dataobj.shape} does not match expected {tuple(expected_shape)} after z-axis swap")
    if len(expected_shape) != len(shape_desc):
        raise ValueError("shape and shape_desc length mismatch after z-axis normalization")
    if shape_desc[swapped_idx] != original_zaxis_desc:
        raise ValueError(f"axis {swapped_idx} descriptor mismatch after swap; expected '{original_zaxis_desc}'")
    if shape_desc[2] not in Z_AXIS_DESCRIPTORS:
        raise ValueError(f"z-axis descriptor '{shape_desc[2]}' is invalid; expected one of {sorted(Z_AXIS_DESCRIPTORS)}")


def normalized_layout(shape_info: "ResolvedShape") -> Tuple[List[int], List[str]]:
    """(shape, shape_desc) after the same z-axis normalization as the data, without reading it.

    Used to check a frame selection (axis names and sizes) before any data is
    loaded. Index 0-2 are the spatial axes; frame axes follow.
    """
    shape = [int(s) for s in shape_info["shape"]]
    shape_desc = list(shape_info["shape_desc"])
    if len(shape) < 3 or len(shape_desc) < 3 or len(shape) != len(shape_desc):
        return shape, shape_desc
    if shape_desc[2] in Z_AXIS_DESCRIPTORS:
        return shape, _normalize_zaxis_descriptor(shape_desc)
    idx = _find_z_axis_candidate(shape_desc)
    if idx is None:
        return shape, shape_desc
    shape = swap_element(shape, 2, idx)
    shape_desc = swap_element(shape_desc, 2, idx)
    return shape, _normalize_zaxis_descriptor(shape_desc)


def ensure_3d_spatial_data(dataobj: np.ndarray, shape_info: "ResolvedShape") -> Tuple[np.ndarray, List[str]]:
    """
    Normalize data and descriptors so the spatial z-axis sits at index 2.

    Swaps axes when needed to place the first spatial z-axis descriptor at
    position 2 and rewrites 'without_slice' to 'slice' for clarity.

    Raises:
        ValueError: When data dimensionality and shape_desc disagree or z-axis
            descriptor is missing.
    """
    # NOTE: `shape_info['shape']` describes the full dataset. When we read only a
    # subset of cycles (block read), `dataobj.shape` may differ (typically the last
    # dimension). Use the actual `dataobj.shape` for validation and swapping.
    shape = list(dataobj.shape)
    shape_desc = list(shape_info['shape_desc'])

    if dataobj.ndim != len(shape_desc):
        raise ValueError(f"dataobj.ndim ({dataobj.ndim}) and shape_desc length ({len(shape_desc)}) do not match")

    if dataobj.ndim < 3 or len(shape_desc) < 3:
        return dataobj, shape_desc

    if shape_desc[2] in Z_AXIS_DESCRIPTORS:
        return dataobj, _normalize_zaxis_descriptor(shape_desc)

    zaxis_candi_idx = _find_z_axis_candidate(shape_desc)
    if zaxis_candi_idx is None:
        raise ValueError(f"z-axis descriptor not found in shape_desc starting at index 2: {shape_desc}")

    pre_zaxis_desc = shape_desc[2]
    new_dataobj = np.swapaxes(dataobj, 2, zaxis_candi_idx)
    new_shape = swap_element(shape, 2, zaxis_candi_idx)
    new_shape_desc = swap_element(shape_desc, 2, zaxis_candi_idx)

    _validate_swapped_axes(new_dataobj, new_shape, new_shape_desc, pre_zaxis_desc, zaxis_candi_idx)

    normalized_shape_desc = _normalize_zaxis_descriptor(new_shape_desc)
    return new_dataobj, normalized_shape_desc


def _read_2dseq_data(
        reco: "Reco",
        dtype: np.dtype,
        shape: Sequence[int],
        *,
        cycle_index: Optional[int] = None,
        cycle_count: Optional[int] = None,
        total_cycles: Optional[int] = None,
    ) -> np.ndarray:
    """Read 2dseq into a Fortran-ordered NumPy array.

    Default behavior reads the full dataset.

    When `cycle_index` is provided, read a contiguous block of cycles starting at
    `cycle_index`. Use `cycle_count` to limit how many cycles to read. If
    `cycle_count` is None, read through the end.

    Notes:
        This assumes cycles are stored contiguously by cycle in the 2dseq stream.
        BrkRaw treats the cycle axis as the LAST dimension of `shape`.
    """
    itemsize = np.dtype(dtype).itemsize

    # Full read path (default).
    if cycle_index is None:
        expected_size = int(np.prod(shape)) * itemsize
        with open_2dseq(reco) as f:
            f.seek(0)
            raw = _read_exact(f, expected_size)
            if len(raw) == expected_size:
                extra = f.read(1)
                if extra:  # longer than expected: count the rest for the message
                    total = expected_size + len(extra)
                    while True:
                        more = f.read(_SKIP_CHUNK)
                        if not more:
                            break
                        total += len(more)
                    raise ValueError(
                        f"2dseq size mismatch: expected {expected_size} bytes for shape {shape}, got {total}"
                    )
        if len(raw) != expected_size:
            raise ValueError(
                f"2dseq size mismatch: expected {expected_size} bytes for shape {shape}, got {len(raw)}"
            )
        try:
            return _readonly_array(raw, dtype).reshape(shape, order="F")
        except ValueError as exc:
            raise ValueError(f"failed to reshape 2dseq buffer to shape {shape}") from exc

    # Block read path.
    if total_cycles is None:
        raise ValueError("total_cycles is required when cycle_index is provided")

    total_cycles = int(total_cycles)
    if total_cycles < 1:
        raise ValueError(f"invalid total_cycles={total_cycles}")

    if cycle_index < 0 or cycle_index >= total_cycles:
        raise ValueError(f"cycle_index {cycle_index} out of range [0, {total_cycles - 1}]")

    if not shape:
        raise ValueError("shape is empty")

    # BrkRaw convention: cycle axis is the last dimension only when cycles > 1.
    if total_cycles > 1:
        if int(shape[-1]) != total_cycles:
            raise ValueError(
                f"cycle axis mismatch: expected shape[-1]==total_cycles ({total_cycles}), got shape[-1]={shape[-1]} for shape={shape}"
            )
        elems_per_cycle = int(np.prod(shape[:-1])) if len(shape) > 1 else 1
    else:
        elems_per_cycle = int(np.prod(shape))
    bytes_per_cycle = elems_per_cycle * itemsize

    if cycle_count is None:
        cycle_count = total_cycles - cycle_index
    cycle_count = int(cycle_count)

    if cycle_count <= 0:
        raise ValueError(f"cycle_count must be > 0 (got {cycle_count})")
    if cycle_index + cycle_count > total_cycles:
        raise ValueError(
            f"cycle_index+cycle_count exceeds total_cycles: {cycle_index}+{cycle_count} +> {total_cycles}"
        )

    byte_offset = cycle_index * bytes_per_cycle
    byte_size = cycle_count * bytes_per_cycle

    with open_2dseq(reco) as f:
        f.seek(byte_offset)
        raw = _read_exact(f, byte_size)

    if len(raw) != byte_size:
        raise ValueError(
            f"2dseq block read size mismatch: expected {byte_size} bytes, got {len(raw)}"
        )

    # Cycle axis is the last dimension.
    if len(shape) == 1:
        block_shape = (cycle_count,)
    else:
        block_shape = (*shape[:-1], cycle_count)

    try:
        return _readonly_array(raw, dtype).reshape(block_shape, order="F")
    except ValueError as exc:
        raise ValueError(f"failed to reshape 2dseq block buffer to shape {block_shape}") from exc


def _normalize_cycle_info(cycle_info: Optional["ResolvedCycle"]) -> Tuple[int, Optional[float]]:
    """Normalize cycle info and provide safe defaults when metadata is absent."""
    if not cycle_info:
        return 1, None
    return int(cycle_info['num_cycles']), cycle_info.get('time_step')


def resolve(
    scan: "Scan",
    reco_id: int = 1,
    *,
    load_data: bool = True,
    cycle_index: Optional[int] = None,
    cycle_count: Optional[int] = None,
) -> Optional[ResolvedImage]:
    """Load 2dseq as a NumPy array with associated metadata.

    Args:
        scan: Scan node containing the target reco.
        reco_id: Reco identifier to read (default: 1).

    Returns:
        ImageResolveResult with:
            - dataobj: NumPy array reshaped using Fortran order.
            - slope/offset: intensity scaling.
            - shape_desc: normalized descriptors with spatial z-axis at index 2.
            - slice/cycle metadata.
        None if required metadata or files are missing; raises ValueError on
        inconsistent metadata.
    """
    reco: "Reco" = get_reco(scan, reco_id)

    dtype_info = datatype_resolver(reco)
    shape_info = shape_resolver(scan, reco_id=reco_id)
    if not dtype_info or not shape_info:
        return None

    dtype = np.dtype(dtype_info["dtype"])
    slope = dtype_info["slope"]
    if slope is None:
        slope = 1.0
    offset = dtype_info["offset"]
    if offset is None:
        offset = 0.0
    shape = shape_info["shape"]

    total_cycles, time_per_cycle = _normalize_cycle_info(shape_info['objs'].cycle)

    dataobj, shape_desc = None, None
    if load_data:
        if total_cycles == 1:
            logger.debug(
                "Cycle slicing disabled: total_cycles=%s shape=%s",
                total_cycles,
                shape,
            )
            cycle_index = None
            cycle_count = None
        else:
            logger.debug(
                "Cycle slicing enabled: total_cycles=%s shape=%s",
                total_cycles,
                shape,
            )
        try:
            dataobj = _read_2dseq_data(
                reco,
                dtype,
                shape,
                cycle_index=cycle_index,
                cycle_count=cycle_count,
                total_cycles=total_cycles,
            )
        except FileNotFoundError:
            return None
        dataobj, shape_desc = ensure_3d_spatial_data(dataobj, shape_info)

    result: ResolvedImage = {
        # image
        'dataobj': dataobj,
        'slope': slope,
        'offset': offset,
        'shape_desc': shape_desc,
        'sliceorder_scheme': shape_info['sliceorder_scheme'],

        # cycle
        'num_cycles': total_cycles,
        'time_per_cycle': time_per_cycle,
    }
    return result

def z_swap_axis(shape_desc: Sequence[str]) -> Optional[int]:
    """Axis that the z-axis normalization swaps with axis 2, None when it swaps nothing."""
    if len(shape_desc) < 3 or shape_desc[2] in Z_AXIS_DESCRIPTORS:
        return None
    return _find_z_axis_candidate(shape_desc)


def resolve_frames(
    scan: "Scan",
    reco_id: int,
    axis: int,
    indices: Sequence[int],
    *,
    shape_info: Optional["ResolvedShape"] = None,
) -> Optional[ResolvedImage]:
    """Like resolve(), but read only ``indices`` of one data axis (WI-0083).

    ``axis`` counts data axes after the z-axis normalization (the numbers of
    ``normalized_layout``); ``shape_info`` is the caller's already resolved shape
    (saves parsing visu_pars again); ``indices`` are sorted, unique and in range. The
    returned ``dataobj`` has only those indices on that axis, every other axis in
    full, laid out like the full array (Fortran order, read-only, z-axis at 2).

    Returns None when the partial read cannot be done (missing metadata or file,
    size of the file unknown); the caller then reads all like 0.6.0. Raises
    ValueError when the file size does not match the metadata, with the message
    of the full read.
    """
    reco: "Reco" = get_reco(scan, reco_id)
    dtype_info = datatype_resolver(reco)
    if shape_info is None:
        shape_info = shape_resolver(scan, reco_id=reco_id)
    if not dtype_info or not shape_info:
        return None
    dtype = np.dtype(dtype_info["dtype"])
    shape = [int(n) for n in shape_info["shape"]]
    shape_desc = list(shape_info["shape_desc"])
    swapped = z_swap_axis(shape_desc)
    pre_axis = axis
    if swapped is not None and axis in (2, swapped):
        pre_axis = swapped if axis == 2 else 2
    try:
        stream = open_2dseq(reco)
    except FileNotFoundError:
        return None
    with stream as f:
        expected_size = int(np.prod(shape)) * dtype.itemsize
        if f.size is None:
            return None
        if f.size != expected_size:
            raise ValueError(
                f"2dseq size mismatch: expected {expected_size} bytes for shape {shape}, got {f.size}"
            )
        cube = read_cube(f, dtype, shape, {pre_axis: list(indices)})
    dataobj, out_desc = ensure_3d_spatial_data(cube, shape_info)
    slope = dtype_info["slope"] if dtype_info["slope"] is not None else 1.0
    offset = dtype_info["offset"] if dtype_info["offset"] is not None else 0.0
    total_cycles, time_per_cycle = _normalize_cycle_info(shape_info['objs'].cycle)
    return {
        'dataobj': dataobj,
        'slope': slope,
        'offset': offset,
        'shape_desc': out_desc,
        'sliceorder_scheme': shape_info['sliceorder_scheme'],
        'num_cycles': total_cycles,
        'time_per_cycle': time_per_cycle,
    }


__all__ = [
    'resolve',
    'resolve_frames',
    'normalized_layout',
    'open_2dseq',
    'z_swap_axis',
]
