"""
Load Paravision `2dseq` data into a NumPy array with geometry metadata.

This resolver reads dtype/slope/offset and shape info for a given `Scan`/`Reco`,
then reshapes the `2dseq` buffer (Fortran order) and normalizes axis labels so
the spatial z-axis sits at index 2. Returns None when required metadata or
files are missing.
"""
from __future__ import annotations


from typing import TYPE_CHECKING, Optional, Sequence, TypedDict, List, Tuple
import logging
from .datatype import resolve as datatype_resolver
from .shape import resolve as shape_resolver
from .helpers import get_reco, get_file, swap_element
import numpy as np

if TYPE_CHECKING:
    from ..dataclasses import Scan, Reco
    from .shape import ResolvedShape
    from .shape import ResolvedCycle


class ResolvedImage(TypedDict):
    dataobj: Optional[np.ndarray]
    slope: float
    offset: float
    shape_desc: Optional[List[str]]
    sliceorder_scheme: Optional[str]
    num_cycles: int
    time_per_cycle: Optional[float]


Z_AXIS_DESCRIPTORS = {'spatial', 'slice', 'without_slice'}
logger = logging.getLogger("brkraw.resolver.image")


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
        with get_file(reco, "2dseq") as f:
            f.seek(0)
            raw = f.read()
        if len(raw) != expected_size:
            raise ValueError(
                f"2dseq size mismatch: expected {expected_size} bytes for shape {shape}, got {len(raw)}"
            )
        try:
            return np.frombuffer(raw, dtype).reshape(shape, order="F")
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

    with get_file(reco, "2dseq") as f:
        f.seek(byte_offset)
        raw = f.read(byte_size)

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
        return np.frombuffer(raw, dtype).reshape(block_shape, order="F")
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

__all__ = [
    'resolve'
]
