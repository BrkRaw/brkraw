from __future__ import annotations

from types import MethodType
from functools import partial
import inspect
from typing import (
    TYPE_CHECKING, 
    cast, 
    Optional,
    Tuple, 
    Union, 
    Any, 
    Mapping, 
    List, 
    Dict,
    Sequence,
    NamedTuple,
)
from pathlib import Path
from warnings import warn
import logging

import numpy as np
from numpy.typing import NDArray
from nibabel.nifti1 import Nifti1Image

from ...core.config import resolve_root
from ...core.parameters import Parameters
from ...specs.remapper import load_spec, map_parameters
from ...specs.rules import load_rules, select_rule_use
from ...dataclasses import Reco, Scan, Study
from ...specs import hook as converter_core
from ...resolver import affine as affine_resolver
from ...resolver import image as image_resolver
from ...resolver import fid as fid_resolver
from ...resolver import nifti as nifti_resolver
from ...resolver.helpers import get_file
from .types import (
    ScanLoader, 
    ConvertType, 
    GetDataobjType, 
    GetAffineType
)
if TYPE_CHECKING:
    from ...resolver.image import ResolvedImage
    from ...resolver.nifti import Nifti1HeaderContents
    from .types import (
        SubjectType, 
        SubjectPose, 
        XYZUNIT, 
        TUNIT,
        Dataobjs,
        Affines,
        AffineSpace,
        ConvertedObj,
        Metadata
    )

logger = logging.getLogger(__name__)

__all__ = [
    "resolve_reco_id",
    "resolve_data_and_affine",
    "resolve_converter_hook",
    "search_parameters",
    "get_dataobj",
    "get_affine",
    "get_nifti1image",
    "convert",
    "get_metadata",
    "apply_converter_hook",
    "make_dir",
]


def make_dir(names: List[str]):
    """Return a stable __dir__ function for a module."""
    def _dir() -> List[str]:
        return sorted(names)
    return _dir


def resolve_reco_id(
    scan: Union["Scan", "ScanLoader"],
    reco_id: Optional[int],
) -> Optional[int]:
    """Resolve a reco id, defaulting to the first available when None."""
    scan = cast(ScanLoader, scan)
    available = list(scan.avail.keys())
    if not available:
        logger.warning("No reco ids available for scan %s", getattr(scan, "scan_id", "?"))
        return None
    if reco_id is None:
        return available[0]
    if reco_id not in scan.avail:
        logger.warning(
            "Reco id %s not available for scan %s (available: %s)",
            reco_id,
            getattr(scan, "scan_id", "?"),
            available,
        )
        return None
    return reco_id


def _normalize_pack_scaling(
    value: Any,
    pack_sizes: Sequence[int],
    *,
    name: str,
    default: float,
) -> List[np.ndarray]:
    """Normalize scalar, per-pack, or per-slice scaling values into pack vectors."""
    if not pack_sizes:
        raise ValueError(f"{name} cannot be resolved without slice-pack sizes.")

    if value is None:
        raw = np.asarray([default], dtype=float)
    elif isinstance(value, np.ndarray):
        raw = np.asarray(value, dtype=float).reshape(-1)
    elif isinstance(value, (list, tuple)):
        raw = np.asarray(value, dtype=float).reshape(-1)
    else:
        raw = np.asarray([value], dtype=float)

    if raw.size == 0:
        raw = np.asarray([default], dtype=float)
    if raw.size > 1 and _all_equal(raw):
        # exactly equal values (for example one per frame) are one scalar (BRK-0035, BRK-0036)
        raw = raw[:1]

    normalized_pack_sizes = [int(size) for size in pack_sizes]
    total_slices = int(sum(normalized_pack_sizes))
    num_packs = len(normalized_pack_sizes)

    if raw.size == 1:
        scalar = float(raw[0])
        return [
            np.full(size, scalar, dtype=float)
            for size in normalized_pack_sizes
        ]

    if raw.size == total_slices:
        pack_values: List[np.ndarray] = []
        offset = 0
        for size in normalized_pack_sizes:
            pack_values.append(np.asarray(raw[offset:offset + size], dtype=float))
            offset += size
        return pack_values

    if raw.size == num_packs:
        return [
            np.full(size, float(raw[idx]), dtype=float)
            for idx, size in enumerate(normalized_pack_sizes)
        ]

    raise ValueError(
        f"{name} has {raw.size} values, expected 1 (global), "
        f"{num_packs} (per-pack), or {total_slices} (per-slice); "
        "different per-frame values are applied by convert(), or by a converter hook "
        "with scale_frames() and scaling_applied=True."
    )


def _scaling_vector(value: Any, default: float) -> np.ndarray:
    if value is None:
        return np.asarray([default], dtype=float)
    raw = np.asarray(value, dtype=float).reshape(-1)
    return raw if raw.size else np.asarray([default], dtype=float)


class FrameScaling(NamedTuple):
    """How convert() applies VisuCoreDataSlope/VisuCoreDataOffs (BRK-0035, BRK-0036).

    ``mode``: "header" (one value, or one per slice pack: header path),
    "apply" (``packs`` holds per-pack (slope, offset) arrays for the data) or
    "skip" (no layout matched; a warning was logged, no scaling).
    """

    mode: str
    packs: Optional[List[Tuple[np.ndarray, np.ndarray]]] = None


def _all_equal(vec: np.ndarray) -> bool:
    # exactly equal only (BRK-0036); no tolerance
    return vec.size <= 1 or bool(np.all(vec == vec[0]))


def _scaling_layout(vec: np.ndarray, num_packs: int, fg_shape: Sequence[int]) -> Tuple[str, int]:
    """BRK-0036 rule for one vector: ("equal", 0), ("pack", 0), ("trailing", j) or ("none", 0).

    Exactly equal values are one value. Otherwise the count is compared with
    the slice-pack count first, then with the products of the
    VisuFGOrderDesc axes from the back (last axis, last two, ... all axes =
    one value per frame); ``j`` is the number of trailing axes the values
    vary along (the smallest j that matches).
    """
    if _all_equal(vec):
        return "equal", 0
    if vec.size == num_packs:
        return "pack", 0
    for j in range(1, len(fg_shape) + 1):
        if int(np.prod(fg_shape[-j:])) == vec.size:
            return "trailing", j
    return "none", 0


def _frame_scaling(
    scan: "ScanLoader",
    reco_id: int,
    *,
    axis: Optional[Union[str, int]] = None,
    frames: Optional[Union[int, List[int], str]] = None,
    cycle_index: Optional[int] = None,
    cycle_count: Optional[int] = None,
    full_frames: bool = False,
) -> FrameScaling:
    """Decide and lay out VisuCoreDataSlope/VisuCoreDataOffs for convert() (BRK-0035, BRK-0036).

    Values that vary along trailing frame-group axes are laid out like the
    data: the frame-group axes are the last axes of the resolved shape, in
    2dseq (Fortran) order; then the same legacy cycle block, z-axis swap,
    slice-pack split and ``axis``/``frames`` selection as the data. The
    arrays broadcast against each pack's data. With ``full_frames`` every
    frame axis has its full size (not 1), so the arrays can be flattened like
    data flattened by ``flatten_fg``.
    """
    image_info = scan.image_info.get(reco_id)
    affine_info = scan.affine_info.get(reco_id)
    if image_info is None or affine_info is None:
        return FrameScaling("header")
    num_slices = [int(n) for n in affine_info["num_slices"]]
    num_packs = len(num_slices)
    slope = _scaling_vector(image_info.get("slope"), 1.0)
    offset = _scaling_vector(image_info.get("offset"), 0.0)
    if _all_equal(slope) and _all_equal(offset):
        return FrameScaling("header")

    from ...resolver.shape import resolve as shape_resolve
    from ...specs.context_map.output import pick_axis, select_frames

    shape_info = shape_resolve(scan, reco_id=reco_id)
    fg = shape_info["objs"].frame_group if shape_info else None
    fg_shape = [int(n) for n in (fg or {}).get("shape", [])] if fg and fg.get("type") is not None else []
    fg_ids = [str(i) for i in (fg or {}).get("id", [])] if fg_shape else []
    kinds = {}
    for name, vec in (("VisuCoreDataSlope", slope), ("VisuCoreDataOffs", offset)):
        kind, j = _scaling_layout(vec, num_packs, fg_shape)
        if kind == "pack" and any(int(np.prod(fg_shape[-k:])) == vec.size for k in range(1, len(fg_shape) + 1)):
            logger.info(
                "scan %s reco %s: %s count %s matches the slice packs and frame axes %s; slice packs are "
                "checked first (BRK-0036).",
                getattr(scan, "scan_id", "?"), reco_id, name, vec.size, fg_ids,
            )
        if kind == "none":
            logger.warning(
                "scan %s reco %s: %s has %s values, which match neither the %s slice pack(s) nor a product of "
                "the frame axes %s %s from the back; scaling not applied.",
                getattr(scan, "scan_id", "?"), reco_id, name, vec.size, num_packs, fg_ids, fg_shape,
            )
            return FrameScaling("skip")
        kinds[name] = (kind, j)
    if not any(kind == "trailing" for kind, _ in kinds.values()):
        return FrameScaling("header")

    shape = [int(n) for n in shape_info["shape"]]
    ndim = len(shape)

    def full(arr: np.ndarray) -> np.ndarray:
        if not full_frames:
            return arr
        return np.broadcast_to(arr, [1] * (ndim - len(fg_shape)) + fg_shape).copy()

    def layout(vec: np.ndarray, kind: str, j: int) -> Optional[np.ndarray]:
        if kind == "equal":
            return full(np.full([1] * ndim, float(vec[0])))
        if kind == "pack":
            return None  # filled per pack below
        tail = fg_shape[-j:]
        return full(vec.reshape(tail, order="F").reshape([1] * (ndim - j) + tail))

    vectors = [slope, offset]
    arrays = [layout(v, *kinds[n]) for v, n in zip(vectors, ("VisuCoreDataSlope", "VisuCoreDataOffs"))]

    # legacy cycle block (cycles are the last axis, as in the 2dseq block read)
    total_cycles = int(image_info.get("num_cycles") or 1)
    if (cycle_index is not None or cycle_count is not None) and total_cycles > 1:
        start = int(cycle_index or 0)
        stop = None if cycle_count is None else start + int(cycle_count)
        arrays = [a if a is None or a.shape[-1] == 1 else a[..., start:stop] for a in arrays]

    shape_desc: List[str] = list(image_resolver.normalized_layout(shape_info)[1])
    swapped: List[Optional[np.ndarray]] = []
    for arr in arrays:
        if arr is None:
            swapped.append(None)
            continue
        out, shape_desc = image_resolver.ensure_3d_spatial_data(arr, shape_info)
        swapped.append(out)

    packs: List[Tuple[np.ndarray, np.ndarray]] = []
    start = 0
    for p, count in enumerate(num_slices):
        pair = []
        for vec, arr in zip(vectors, swapped):
            if arr is None:  # one value per slice pack
                pair.append(np.full([1] * ndim, float(vec[p])))
                continue
            part = arr if arr.shape[2] == 1 else arr[:, :, start:start + count]
            if frames is not None:
                ax = pick_axis(shape_desc, axis)
                if part.shape[ax] == 1:
                    if isinstance(frames, int) and not isinstance(frames, bool):
                        part = np.take(part, 0, axis=ax)
                else:
                    part, _ = select_frames(part, shape_desc, axis, frames)
            pair.append(part)
        if frames is not None and isinstance(frames, int) and not isinstance(frames, bool):
            # a per-pack scalar array must lose the selected axis too
            ax = pick_axis(shape_desc, axis)
            pair = [np.take(a, 0, axis=ax) if a.ndim == ndim and a.shape[ax] == 1 and all(
                s == 1 for s in a.shape) else a for a in pair]
        packs.append((pair[0], pair[1]))
        start += count
    return FrameScaling("apply", packs)


def _flatten_like(arr: np.ndarray, data: Any) -> np.ndarray:
    """Flatten the frame axes (axis 3 on) of a scaling array like convert()'s -F flattened ``data``.

    convert() flattens with order "F" when the data as read are only
    Fortran-contiguous, else "C"; a reshape keeps that property, so the
    flattened data show which order was used. When the flattened data are both
    C- and F-contiguous (every spatial axis has size 1), the order cannot be
    told; if two or more frame axes vary, the two orders give different values,
    so this stops with an error instead of guessing (BRK-0051).
    """
    if arr.ndim <= 4:
        return arr
    data = np.asarray(data)
    n = int(np.prod(arr.shape[3:]))
    if n not in (1, int(data.shape[3])):
        raise ValueError(
            f"per-frame scaling has {n} frames, flattened data has {data.shape[3]}."
        )
    varying = sum(1 for s in arr.shape[3:] if s > 1)
    if varying >= 2 and data.flags.f_contiguous and data.flags.c_contiguous:
        raise ValueError(
            "per-frame scaling: the order in which -F (flatten_fg) flattened the frame axes "
            f"cannot be told from data of shape {data.shape}; convert without -F, or apply "
            "scale_frames before flattening."
        )
    order = "F" if (data.flags.f_contiguous and not data.flags.c_contiguous) else "C"
    return arr.reshape((*arr.shape[:3], n), order=order)


def scale_frames(
    scan: "ScanLoader",
    reco_id: int,
    dataobjs: Tuple[NDArray, ...],
    *,
    axis: Optional[Union[str, int]] = None,
    frames: Optional[Union[int, List[int], str]] = None,
    cycle_index: Optional[int] = None,
    cycle_count: Optional[int] = None,
) -> Tuple[Tuple[NDArray, ...], bool]:
    """Apply per-frame VisuCoreDataSlope/VisuCoreDataOffs the way convert() does (BRK-0036).

    For converter hooks, which get the data as read: pass the data objects
    (one per slice pack, with the same frame selection as the call) and pass
    the returned flag to ``get_nifti1image(..., scaling_applied=...)``.
    Raises ValueError for ``-F`` data whose flatten order cannot be told (every
    spatial axis 1, two or more varying frame axes; BRK-0051).

    Returns:
        ``(dataobjs, scaling_applied)``. When the values are one per reco, per
        slice pack or per slice, nothing is changed (the header carries them) and
        the flag is False. When they differ per frame, the data are scaled
        (float) and the flag is True (header slope 1, offset 0). When no layout
        matches, a warning is logged, the data stay raw and the flag is True.

        Data flattened by ``flatten_fg`` (``-F``), as brkraw passes them to a
        hook, are accepted: the frame axes of the values are flattened in the
        same order as the data (the order brkraw's flattening used), so the
        result equals the default path, which scales before flattening.
    """
    frame_scaling = _frame_scaling(
        scan, reco_id, axis=axis, frames=frames, cycle_index=cycle_index, cycle_count=cycle_count
    )
    dataobjs = tuple(dataobjs)
    if frame_scaling.mode == "apply":
        assert frame_scaling.packs is not None
        if len(frame_scaling.packs) != len(dataobjs):
            raise ValueError(
                f"per-frame scaling has {len(frame_scaling.packs)} slice packs, data has {len(dataobjs)}."
            )
        packs = frame_scaling.packs
        if any(np.ndim(d) == 4 and a.ndim > 4 for d, pair in zip(dataobjs, packs) for a in pair):
            # flatten_fg: brkraw flattened the frame axes before the hook got the data
            full = _frame_scaling(
                scan, reco_id, axis=axis, frames=frames, cycle_index=cycle_index,
                cycle_count=cycle_count, full_frames=True,
            )
            assert full.packs is not None
            packs = [
                tuple(_flatten_like(a, d) for a in pair) for d, pair in zip(dataobjs, full.packs)
            ]
        return tuple(
            np.asarray(d, dtype=float) * s_arr + o_arr
            for d, (s_arr, o_arr) in zip(dataobjs, packs)
        ), True
    if frame_scaling.mode == "skip":
        return dataobjs, True  # header 1/0, data raw
    return dataobjs, False


def _layout_warnings(scan: "ScanLoader", reco_id: int) -> None:
    """BRK-0037 safeguards: warn when the slice-pack split or a scaling shape looks inconsistent.

    1. With more than one slice pack, the frames assigned to each pack (a
       contiguous split along FG_SLICE by the method's slices per pack) should
       share one orientation (VisuCoreOrientation).
    2. A slope or offset stored with two or more dimensions should list the
       trailing frame axes slowest first (JCAMP stores the last dimension
       fastest); values are always read in stored order.
    Warnings only; conversion is unchanged.
    """
    from ...resolver.helpers import get_reco
    from ...resolver.shape import resolve_frame_group

    try:
        visu_pars = get_file(get_reco(scan, reco_id), "visu_pars")
    except Exception:
        return
    fg = resolve_frame_group(visu_pars) or {}
    fg_shape = [int(n) for n in fg.get("shape", [])]
    fg_ids = [str(i) for i in fg.get("id", [])]
    label = f"scan {getattr(scan, 'scan_id', '?')} reco {reco_id}"

    for key in ("VisuCoreDataSlope", "VisuCoreDataOffs"):
        value = visu_pars.get(key)
        shape = tuple(int(n) for n in np.shape(value)) if value is not None else ()
        if len(shape) >= 2:
            tail = fg_shape[-len(shape):] if len(shape) <= len(fg_shape) else None
            if tail is None or shape != tuple(reversed(tail)):
                logger.warning(
                    "%s: %s is stored with shape %s, which does not match the frame axes %s %s; "
                    "its values are read in stored order.",
                    label, key, shape, fg_ids, fg_shape,
                )

    affine_info = scan.affine_info.get(reco_id) if getattr(scan, "affine_info", None) else None
    if not affine_info:
        return
    num_slices = [int(n) for n in affine_info["num_slices"]]
    if len(num_slices) < 2:
        return
    names = [i.strip("<>") for i in fg_ids]
    if "FG_SLICE" not in names:
        return
    k = names.index("FG_SLICE")
    if sum(num_slices) != fg_shape[k]:
        logger.warning(
            "%s: the slice packs hold %s slices but FG_SLICE has %s; the slice pack split may not match the data.",
            label, sum(num_slices), fg_shape[k],
        )
        return
    orient = visu_pars.get("VisuCoreOrientation")
    n_frames = int(np.prod(fg_shape)) if fg_shape else 0
    if orient is None or np.size(orient) != 9 * n_frames:
        return
    orient = np.asarray(orient, dtype=float).reshape(n_frames, 9)
    frame_idx = np.arange(n_frames).reshape(fg_shape, order="F")
    by_slice = np.moveaxis(frame_idx, k, 0).reshape(fg_shape[k], -1)
    start = 0
    for p, count in enumerate(num_slices, start=1):
        frames = by_slice[start:start + count].ravel()
        if not np.allclose(orient[frames], orient[frames[0]], atol=1e-6):
            logger.warning(
                "%s: the frames of slice pack %s do not share one orientation; the slice pack split "
                "may not match the frame order.",
                label, p,
            )
        start += count


def resolve_data_and_affine(
    scan: "Scan",
    reco_id: Optional[int] = None,
    *,
    affine_decimals: int = 6,
):
    """Populate per-reco image/affine resolver outputs on a scan.

    Args:
        scan: Scan node to attach image/affine info.
        reco_id: Reco identifier to resolve (default: 1).
        affine_decimals: Decimal rounding applied to resolved affines.
    """
    scan = cast(ScanLoader, scan)
    scan.get_fid = MethodType(fid_resolver.resolve, scan)
    scan.image_info = {}
    scan.affine_info = {}

    reco_ids = [reco_id] if reco_id is not None else list(scan.avail.keys())
    if not reco_ids:
        logger.warning("No reco ids available to resolve for scan %s", getattr(scan, "scan_id", "?"))
        return

    for rid in reco_ids:
        if rid not in scan.avail:
            logger.warning(
                "Reco id %s not available for scan %s (available: %s)",
                rid,
                getattr(scan, "scan_id", "?"),
                list(scan.avail.keys()),
            )
            continue
        try:
            image_info = image_resolver.resolve(scan, rid, load_data=False)
        except Exception as exc:
            logger.warning(
                "Failed to resolve image data for scan %s reco %s: %s",
                getattr(scan, "scan_id", "?"),
                rid,
                exc,
            )
            image_info = None
        try:
            # store subject-view affines (scanner unwrap happens in get_affine)
            affine_info = affine_resolver.resolve(
                scan, rid, decimals=affine_decimals, unwrap_pose=False,
            )

        except Exception as exc:
            logger.warning(
                "Failed to resolve affine for scan %s reco %s: %s",
                getattr(scan, "scan_id", "?"),
                rid,
                exc,
            )
            affine_info = None

        scan.image_info[rid] = image_info
        scan.affine_info[rid] = affine_info

def _load_rules(base):
    try:
        rules = load_rules(root=base, validate=False)
    except Exception:
        rules = {}
    return rules


def resolve_converter_hook(
    scan: "Scan",
    base: Path,
    *,
    affine_decimals: int = 6,
):
    scan = cast(ScanLoader, scan)
    rules = _load_rules(base)
    if rules:
        try:
            hook_name = select_rule_use(
                scan,
                rules.get("converter_hook", []),
                base=base,
                resolve_paths=False,
            )
        except Exception as exc:
            logger.debug(
                "Converter hook rule selection failed for scan %s: %s",
                getattr(scan, "scan_id", "?"),
                exc,
                exc_info=True,
            )
            hook_name = None
    
        if isinstance(hook_name, str):
            try:
                entry = converter_core.resolve_hook(hook_name)
            except Exception as exc:
                logger.warning(
                    "Converter hook %r not available: %s",
                    hook_name,
                    exc,
                )
                entry = None
            if entry:
                logger.debug("Applying converter hook: %s", hook_name)
                scan._converter_hook_name = hook_name
                apply_converter_hook(
                    scan,
                    entry,
                    affine_decimals=affine_decimals,
                )
            else:
                logger.debug("Converter hook %r resolved to no entry.", hook_name)
        else:
            logger.debug("No converter hook selected for scan %s.", getattr(scan, "scan_id", "?"))
    scan._hook_resolved = True


def search_parameters(
    self: Union[Study, Scan, Reco],
    key: str,
    file: Optional[Union[str, List[str]]] = None,
    scan_id: Optional[int] = None,
    reco_id: Optional[int] = None,
) -> Optional[dict]:
    """Search parameter files for keys on Study/Scan/Reco objects.

    Results are grouped by filename. When searching a Study/Scan without
    reco_id, scan and reco hits are merged as
    `{filename: {"scan": {...}, "reco_<id>": {...}}}`. With a specific reco_id
    (or Reco), results stay flat as `{filename: {matched_key: value}}`.
    Missing files are ignored; non-parameter files raise TypeError.

    Args:
        self: Study, Scan, or Reco instance.
        key: Parameter key to search for.
        file: Filename or list of filenames to search (default: common set).
        scan_id: Scan id (required when searching from Study).
        reco_id: Reco id (optional; flattens results for that reco).

    Returns:
        Mapping of filename to found values, or None if no hits.
    """

    files = ["method", "acqp", "visu_pars", "reco"] if file is None else file
    files = [files] if isinstance(files, str) else list(files)

    def load_parameters(obj: Union[Study, Scan, Reco], filename: str) -> Optional[Parameters]:
        try:
            params = get_file(obj, filename)
        except FileNotFoundError:
            return None
        if not isinstance(params, Parameters):
            raise TypeError(f"Not a Paravision parameter file: {filename}")
        return params

    def flatten_matches(matches: List[dict]) -> dict:
        flat: dict = {}
        for entry in matches:
            flat.update(entry)
        return flat

    def search_node(node: Union[Study, Scan, Reco]) -> Dict[str, dict]:
        hits: Dict[str, dict] = {}
        for fname in files:
            params = load_parameters(node, fname)
            if params is None:
                continue
            matches = params.search_keys(key)
            if matches:
                hits[fname] = flatten_matches(matches)
        return hits

    def search_recos(scan_obj: Scan) -> Dict[int, Dict[str, dict]]:
        reco_hits: Dict[int, Dict[str, dict]] = {}
        for rid, reco in scan_obj.avail.items():
            hits = search_node(reco)
            if hits:
                reco_hits[rid] = hits
        return reco_hits

    def merge_scan_and_recos(
        scan_hits: Dict[str, dict], reco_hits: Dict[int, Dict[str, dict]]
    ) -> Dict[str, Union[Dict[str, dict], dict]]:
        """Merge scan/reco hits by filename.

        Args:
            scan_hits: Per-filename hits from the scan object.
            reco_hits: Per-reco hits keyed by reco id.

        Returns:
            Merged mapping keyed by filename.
        """
        if not scan_hits and not reco_hits:
            return {}

        merged: Dict[str, Union[Dict[str, dict], dict]] = {}
        all_fnames = set(scan_hits) | {fname for rh in reco_hits.values() for fname in rh}
        for fname in all_fnames:
            scan_hit = scan_hits.get(fname)
            reco_for_fname = {
                f"reco_{rid}": rhits[fname]
                for rid, rhits in reco_hits.items()
                if fname in rhits
            }
            if reco_for_fname:
                merged[fname] = {}
                if scan_hit:
                    merged[fname]["scan"] = scan_hit
                merged[fname].update(reco_for_fname)
            elif scan_hit:
                merged[fname] = scan_hit
        return merged

    if isinstance(self, Study):
        if scan_id is None:
            warn("To search from Study object, specifying <scan_id> is required.")
            return None
        scan = cast(ScanLoader, self.get_scan(scan_id))
        scan_hits = search_node(scan)
        if reco_id is None:
            reco_hits = search_recos(scan)
            merged = merge_scan_and_recos(scan_hits, reco_hits)
            return merged or None
        # specific reco: keep flat
        result: Dict[str, dict] = {}
        if scan_hits:
            result.update(scan_hits)
        reco = scan.get_reco(reco_id)
        reco_hits = search_node(reco)
        if reco_hits:
            result.update(reco_hits)
        return result or None

    if isinstance(self, Scan):
        scan_hits = search_node(self)
        if reco_id is None:
            reco_hits = search_recos(self)
            merged = merge_scan_and_recos(scan_hits, reco_hits)
            return merged or None
        # specific reco: keep flat
        result: Dict[str, dict] = {}
        if scan_hits:
            result.update(scan_hits)
        reco_hits = search_node(self.get_reco(reco_id))
        if reco_hits:
            result.update(reco_hits)
        return result or None

    if isinstance(self, Reco):
        reco_hits = search_node(self)
        return reco_hits or None

    return None


def _finalize_affines(
    affines: List[NDArray],
    num_slice_packs: int,
    decimals: Optional[int],
) -> Affines:
    if num_slice_packs == 1:
        affine = affines[0]
        if decimals is not None:
            affine = np.round(affine, decimals=decimals)
        return affine

    if decimals is not None:
        return tuple(np.round(a, decimals=decimals) for a in affines)

    return tuple(affines)



def _selection_flags(
    shape_info: Any,
    shape: Sequence[int],
    num_slices: Sequence[int],
    ax: int,
    index: Any,
) -> List[Tuple[bool, bool, bool]]:
    """(f_contiguous, c_contiguous, writeable) of each slice pack's selection, without any data.

    Builds a read-only stand-in with the strides of a Fortran-ordered array of
    ``shape`` (one element of memory), then runs the same z-axis swap, slice pack
    split and basic index (int or slice) that get_dataobj runs on the data.
    """
    from numpy.lib.stride_tricks import as_strided

    shape = tuple(int(n) for n in shape)
    strides = tuple(int(np.prod(shape[:i], dtype=np.int64)) * 2 for i in range(len(shape)))
    proxy = as_strided(np.zeros(1, dtype="<i2"), shape=shape, strides=strides, writeable=False)
    data, _ = image_resolver.ensure_3d_spatial_data(proxy, shape_info)
    flags = []
    start = 0
    for count in num_slices:
        pack = data[:, :, slice(start, start + int(count))]
        start += int(count)
        sel: List[Any] = [slice(None)] * pack.ndim
        sel[ax] = index
        view = pack[tuple(sel)]
        flags.append((bool(view.flags.f_contiguous), bool(view.flags.c_contiguous), bool(view.flags.writeable)))
    return flags


def _partial_frames(
    scan: "ScanLoader",
    reco_id: int,
    num_slices: Sequence[int],
    axis: Any,
    frames: Any,
) -> Optional[Tuple[Any, int, Any, List[str]]]:
    """Read only the asked frames of 2dseq (WI-0083, D-0106), or None to read all like 0.6.0.

    Returns ``(image info with only those frames on the axis, axis, index into
    that smaller axis, notes)``. None when the selection is bad (the full path
    then raises its usual error), covers every frame, or when cutting the smaller
    array would give different ``flags`` than cutting the full array: ``convert -F``
    chooses its flatten order from the flags, so they must stay as in 0.6.0.
    """
    from ...resolver.shape import resolve as shape_resolve
    from ...specs.context_map.output import parse_frames, pick_axis

    try:
        shape_info = shape_resolve(scan, reco_id=reco_id)
        if not shape_info:
            return None
        shape, desc = image_resolver.normalized_layout(shape_info)
        if len(shape) < 4 or len(shape) != len(desc):
            return None
        ax = pick_axis(desc, axis)
        index, _keep, norm, notes = parse_frames(frames, int(shape[ax]))
    except Exception:
        return None
    need = sorted(set(norm))
    if len(need) >= int(shape[ax]):
        return None
    position = {v: i for i, v in enumerate(need)}
    if isinstance(index, slice):
        new_index: Any = slice(None, None, -1) if (index.step or 1) < 0 else slice(None)
    elif isinstance(index, (list, tuple)):
        new_index = [position[v] for v in norm]
    else:
        new_index = position[norm[0]]
    if not isinstance(new_index, list):
        # int and slice give views, whose flags follow the strides of the whole array
        pre_shape = [int(n) for n in shape_info["shape"]]
        swapped = image_resolver.z_swap_axis(list(shape_info["shape_desc"]))
        pre_ax = ax
        if swapped is not None and ax in (2, swapped):
            pre_ax = swapped if ax == 2 else 2
        small = list(pre_shape)
        small[pre_ax] = len(need)
        try:
            same = _selection_flags(shape_info, pre_shape, num_slices, ax, index) == \
                _selection_flags(shape_info, small, num_slices, ax, new_index)
        except Exception:
            same = False
        if not same:
            logger.debug("partial 2dseq read skipped: the array flags would differ from a full read")
            return None
    info = image_resolver.resolve_frames(scan, reco_id, ax, need, shape_info=shape_info)
    if info is None or info.get("dataobj") is None:
        return None
    return info, ax, new_index, list(notes)


def get_dataobj(
    self: "ScanLoader",
    reco_id: Optional[int] = None,
    axis: Optional[Union[str, int]] = None,
    frames: Optional[Union[int, List[int], str]] = None,
    **kwargs: Dict[str, Any]
) -> Dataobjs:
    """Return reconstructed data for a reco, split by slice pack if needed.

    Args:
        self: Scan or ScanLoader instance.
        reco_id: Reco identifier to read (defaults to the first available).
        axis: Frame axis for ``frames``: a lowercase name from the scan's frame
            groups (``echo``, ``cycle`` ...; see "Frame axes" in ``brkraw info``)
            or a data-axis number >= 3. Omitted: the scan's only frame axis.
        frames: Frames to keep, numpy rules: an int picks one frame and removes
            the axis, a list keeps the axis in that order, ``"start:stop[:step]"``
            is a Python slice. Applied to each slice pack.
        cycle_index, cycle_count: Legacy (0.5) cycle block read on the last axis;
            deprecated, removed in 0.7.0 (use ``axis="cycle", frames="a:b"``).

    Returns:
        Single ndarray when one slice pack exists; otherwise a tuple of arrays.
        Returns None when required metadata is unavailable.
    """
    cycle_index = cast(Optional[int], kwargs.get('cycle_index'))
    cycle_count = cast(Optional[int], kwargs.get('cycle_count'))
    if cycle_index is not None or cycle_count is not None:
        if axis is not None or frames is not None:
            raise ValueError("Use axis/frames or the legacy cycle_index/cycle_count, not both.")
        start = 0 if cycle_index is None else int(cycle_index)
        stop = "" if cycle_count is None else str(start + int(cycle_count))
        message = (
            "cycle_index/cycle_count are deprecated and will be removed in brkraw 0.7.0; "
            f'use axis="cycle", frames="{start}:{stop}"'
        )
        warn(message, DeprecationWarning, stacklevel=2)
    if axis is not None and frames is None:
        raise ValueError("axis needs frames (which frames of that axis to keep).")
    resolved_reco_id = resolve_reco_id(self, reco_id)
    if resolved_reco_id is None:
        return None
    
    affine_info = self.affine_info.get(resolved_reco_id)
    if affine_info is None:
        logger.warning(
            "affine_info is not available for scan %s",
            getattr(self, "scan_id", "?")
        )
        return None
    image_info = self.image_info.get(resolved_reco_id)
    if image_info is None:
        logger.warning(
            "image_info is not available for scan %s",
            getattr(self, "scan_id", "?")
        )
        return None

    # Normalize cycle arguments if provided.
    cycle_args_requested = cycle_index is not None or cycle_count is not None
    if cycle_index is None and cycle_count is not None:
        cycle_index = 0

    # If the dataset has <= 1 cycle, ignore cycle slicing to avoid block reads.
    if cycle_args_requested:
        total_cycles = int(image_info["num_cycles"])
        if total_cycles <= 1:
            cycle_index = None
            cycle_count = None
            cycle_args_requested = False

    partial = None
    if (
        frames is not None
        and image_resolver.PARTIAL_READ
        and not cycle_args_requested
        and image_info.get("dataobj") is None
    ):
        # read only the asked frames; the smaller array is not kept as the scan's data
        partial = _partial_frames(self, resolved_reco_id, affine_info["num_slices"], axis, frames)

    if partial is not None:
        image_info = partial[0]
    elif cycle_args_requested or image_info.get("dataobj") is None:
        image_info = image_resolver.resolve(
            self,
            resolved_reco_id,
            load_data=True,
            cycle_index=cycle_index,
            cycle_count=cycle_count,
        )
        if not cycle_args_requested:
            # A legacy cycle block is returned to this caller only; keeping it
            # would make later plain get_dataobj() calls return the block.
            self.image_info[resolved_reco_id] = image_info

    num_slices = affine_info["num_slices"]
    dataobj = cast(dict, image_info).get("dataobj")
    slice_pack = []
    slice_offset = 0
    for _num_slices in num_slices:
        _dataobj = cast(NDArray, dataobj)[:, :, slice(slice_offset, slice_offset + _num_slices)]
        slice_offset += _num_slices
        slice_pack.append(_dataobj)

    if frames is not None and partial is not None:
        # the data hold only the asked frames on this axis; cut them like the full array
        _, part_ax, part_index, part_notes = partial
        selected = []
        for pack in slice_pack:
            cut: List[Any] = [slice(None)] * pack.ndim
            cut[part_ax] = part_index
            for note in part_notes:
                logger.warning("scan %s: %s", getattr(self, "scan_id", "?"), note)
            selected.append(pack[tuple(cut)])
        slice_pack = selected
    elif frames is not None:
        # Slice packs first, then the frame selection inside each pack (BRK-0024).
        from ...specs.context_map.output import select_frames

        shape_desc = cast(dict, image_info).get("shape_desc") or []
        selected = []
        for pack in slice_pack:
            part, notes = select_frames(pack, shape_desc, axis, frames)
            for note in notes:
                logger.warning("scan %s: %s", getattr(self, "scan_id", "?"), note)
            selected.append(part)
        slice_pack = selected

    if len(slice_pack) == 1:
        return slice_pack[0]
    return tuple(slice_pack)


def get_affine(
    self: "ScanLoader",
    reco_id: Optional[int] = None,
    *,
    space: AffineSpace = "subject_ras",
    override_subject_type: Optional["SubjectType"] = None,
    override_subject_pose: Optional["SubjectPose"] = None,
    decimals: Optional[int] = None,
    **kwargs: Any,
) -> Affines:
    """
    Return affine(s) for a reco in the requested coordinate space.

    Spaces:
      - "raw": Return the affine(s) as stored (no transforms applied).
      - "scanner": Return affine(s) in scanner XYZ (unwrapped).
      - "subject_ras": Return affine(s) in subject-view RAS (wrap to subject pose/type).

    Overrides:
      - override_subject_type and override_subject_pose are only valid when space="subject_ras".
        Overrides are applied during wrapping to subject RAS.

    Args:
        self: Scan or ScanLoader instance.
        reco_id: Reco identifier to read (defaults to the first available).
        space: Output space: "raw", "scanner", or "subject_ras" (default: "subject_ras").
        override_subject_type: Optional subject type override (only for "subject_ras").
        override_subject_pose: Optional subject pose override (only for "subject_ras").
        decimals: Optional decimal rounding applied to returned affines.

    Returns:
        Single affine matrix when one slice pack exists; otherwise a tuple of affines.
        Returns None when affine info is unavailable.

    Raises:
        ValueError: If overrides are provided when space is not "subject_ras".
    """
    if not hasattr(self, "affine_info"):
        return None

    self = cast("ScanLoader", self)
    resolved_reco_id = resolve_reco_id(self, reco_id)
    if resolved_reco_id is None:
        return None

    affine_info = self.affine_info.get(resolved_reco_id)
    if affine_info is None:
        return None

    num_slice_packs = affine_info["num_slice_packs"]
    affines = list(affine_info["affines"])  # make a copy-like list

    is_override = (override_subject_type is not None) or (override_subject_pose is not None)
    if is_override and space != "subject_ras":
        raise ValueError(
            "override_subject_type/override_subject_pose is only supported when space='subject_ras'."
        )

    # "raw" does not need subject info
    if space == "raw":
        result = _finalize_affines(affines, num_slice_packs, decimals)
        return _apply_affine_post_transform(result, kwargs=kwargs)

    # Need subject type/pose for unwrap and wrap
    visu_pars = get_file(self.avail[resolved_reco_id], "visu_pars")
    subj_type, subj_pose = affine_resolver.get_subject_type_and_position(visu_pars)

    # Step 1: unwrap to scanner XYZ
    affines_scanner = [
        affine_resolver.unwrap_to_scanner_xyz(affine, subj_type, subj_pose)
        for affine in affines
    ]

    if space == "scanner":
        result = _finalize_affines(affines_scanner, num_slice_packs, decimals)
        return _apply_affine_post_transform(result, kwargs=kwargs)

    # Step 2: wrap to subject RAS (optionally with override)
    use_type = override_subject_type or subj_type
    use_pose = override_subject_pose or subj_pose

    affines_subject_ras = [
        affine_resolver.wrap_to_subject_ras(affine, use_type, use_pose)
        for affine in affines_scanner
    ]
    result = _finalize_affines(affines_subject_ras, num_slice_packs, decimals)
    return _apply_affine_post_transform(result, kwargs=kwargs)


def _apply_affine_post_transform(affines: Affines, *, kwargs: Mapping[str, Any]) -> Affines:
    """Apply optional flips/rotations to affines right before returning.

    These transforms are applied in world space and do not depend on output
    `space`. They are controlled via extra kwargs (intentionally not strict):

    - flip_x / flip_y / flip_z: bool-like
    - rad_x / rad_y / rad_z: radians (float-like)
    """

    def as_bool(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
        return bool(value)

    def as_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    flip_x = as_bool(kwargs.get("flip_x", False))
    flip_y = as_bool(kwargs.get("flip_y", False))
    flip_z = as_bool(kwargs.get("flip_z", False))
    rad_x = as_float(kwargs.get("rad_x", 0.0))
    rad_y = as_float(kwargs.get("rad_y", 0.0))
    rad_z = as_float(kwargs.get("rad_z", 0.0))

    if not (flip_x or flip_y or flip_z or rad_x or rad_y or rad_z):
        return affines

    def apply_one(a: NDArray) -> NDArray:
        out = np.asarray(a, dtype=float)
        if flip_x or flip_y or flip_z:
            out = affine_resolver.flip_affine(out, flip_x=flip_x, flip_y=flip_y, flip_z=flip_z)
        if rad_x or rad_y or rad_z:
            out = affine_resolver.rotate_affine(out, rad_x=rad_x, rad_y=rad_y, rad_z=rad_z)
        return np.asarray(out, dtype=float)

    if isinstance(affines, tuple):
        return tuple(apply_one(np.asarray(a)) for a in affines)
    return apply_one(np.asarray(affines))


def get_nifti1image(
    self: Union["Scan", "ScanLoader"],
    reco_id: int,
    dataobjs: Tuple[NDArray, ...],
    affines: Tuple[NDArray, ...],
    *,
    xyz_units: XYZUNIT = "mm",
    t_units: TUNIT = "sec",
    override_header: Optional[Nifti1HeaderContents] = None,
    scaling_applied: bool = False,
) -> ConvertedObj:
    """Return NIfTI image(s) for a reco.

    Args:
        self: Scan or ScanLoader instance.
        reco_id: Reco identifier to read (defaults to the first available).
        xyz_units: Spatial units for NIfTI header.
        t_units: Temporal units for NIfTI header.
        override_header: Optional header values to apply.
        scaling_applied: The data objects already carry the slope/offset
            (per-frame scaling, BRK-0035); the header gets slope 1, offset 0.

    Returns:
        Output object(s) supporting to_filename(). Returns None when required
        metadata is unavailable.
    """
    self = cast(ScanLoader, self)

    image_info = self.image_info.get(reco_id)
    if image_info is None:
        return None

    if dataobjs is None or affines is None:
        return None

    affine_info = self.affine_info.get(reco_id)
    if affine_info is not None:
        pack_sizes = [int(size) for size in affine_info["num_slices"]]
    else:
        pack_sizes = [int(dataobj.shape[2]) if dataobj.ndim >= 3 else 1 for dataobj in dataobjs]
    if len(pack_sizes) != len(dataobjs):
        raise ValueError(
            f"Slice-pack metadata mismatch: {len(pack_sizes)} pack sizes for {len(dataobjs)} data objects."
        )

    raw_slope = 1.0 if scaling_applied else image_info.get("slope")
    raw_offset = 0.0 if scaling_applied else image_info.get("offset")
    slope_packs = _normalize_pack_scaling(
        raw_slope,
        pack_sizes,
        name="VisuCoreDataSlope",
        default=1.0,
    )
    offset_packs = _normalize_pack_scaling(
        raw_offset,
        pack_sizes,
        name="VisuCoreDataOffs",
        default=0.0,
    )
    niiobjs = []
    for i, dataobj in enumerate(dataobjs):
        affine = affines[i]
        niiobj = Nifti1Image(dataobj, affine)
        output_image_info = cast("ResolvedImage", dict(image_info))
        output_image_info["dataobj"] = dataobj
        output_image_info["slope"] = slope_packs[i]
        output_image_info["offset"] = offset_packs[i]
        nifti1header_contents = nifti_resolver.resolve(
            output_image_info, xyz_units=xyz_units, t_units=t_units
        )
        if override_header:
            for key, value in override_header.items():
                if value is not None:
                    nifti1header_contents[key] = value
        niiobj = nifti_resolver.update(niiobj, nifti1header_contents)
        niiobjs.append(niiobj)

    if len(niiobjs) == 1:
        return niiobjs[0]
    return tuple(niiobjs)


def convert(
    self: "ScanLoader",
    reco_id: Optional[int] = None,
    *,
    space: AffineSpace = "subject_ras",
    override_header: Optional[Nifti1HeaderContents] = None,
    override_subject_type: Optional[SubjectType] = None,
    override_subject_pose: Optional[SubjectPose] = None,
    flatten_fg: bool = False,
    hook_args_by_name: Optional[Mapping[str, Mapping[str, Any]]] = None,
    **kwargs: Any,
) -> ConvertedObj:
    """Convert a reco to output object(s).
    
    Args:
        space: Output affine space ("raw", "scanner", "subject_ras").
        override_header: Optional header values to apply.
        override_subject_type: Subject type override for subject-view wrapping.
        override_subject_pose: Subject pose override for subject-view wrapping.
        flatten_fg: If True, flatten foreground dimensions.
        hook_args_by_name: Optional hook args mapping (split per helper signature).
        flatten_fg: If True, flatten foreground dimensions.
    Returns:
        Single NIfTI image when one slice pack exists; otherwise a tuple of
        images. Returns None when required metadata is unavailable.
    """
    if not all(
        hasattr(self, attr) for attr in ["image_info", "affine_info", "get_dataobj", "get_affine"]
    ):
        return None
    
    self = cast(ScanLoader, self)
    resolved_reco_id = resolve_reco_id(self, reco_id)
    logger.debug("Resolved reco_id = %s", resolved_reco_id)
    if resolved_reco_id is None:
        return None

    hook_name = getattr(self, "_converter_hook_name", None)
    if isinstance(hook_name, str) and hook_name:
        logger.debug(
            "Convert starting for scan %s reco %s with hook %s",
            getattr(self, "scan_id", "?"),
            resolved_reco_id,
            hook_name,
        )
    else:
        logger.debug(
            "Convert starting for scan %s reco %s (no hook)",
            getattr(self, "scan_id", "?"),
            resolved_reco_id,
        )
    
    hook_kwargs = _resolve_hook_kwargs(self, hook_args_by_name)

    # Merge explicit **kwargs (CLI/user) with hook kwargs. Explicit kwargs win.
    merged_kwargs: Dict[str, Any] = dict(hook_kwargs) if hook_kwargs else {}
    merged_kwargs.update(kwargs)

    data_kwargs = _filter_read_kwargs(self.get_dataobj, merged_kwargs)
    # flip_* are affine-only options; never pass them to get_dataobj.
    for key in ("flip_x", "flip_y", "flip_z"):
        data_kwargs.pop(key, None)
    
    convert_kwargs = {key: value for key, value in merged_kwargs.items() if key not in data_kwargs}
    if data_kwargs:
        logger.debug(
            "Calling get_dataobj for scan %s reco %s with args %s",
            getattr(self, "scan_id", "?"),
            resolved_reco_id,
            data_kwargs,
        )
        dataobjs = self.get_dataobj(resolved_reco_id, **data_kwargs)
    else:
        logger.debug(
            "Calling get_dataobj for scan %s reco %s (no args)",
            getattr(self, "scan_id", "?"),
            resolved_reco_id,
        )
        dataobjs = self.get_dataobj(resolved_reco_id)

    affine_kwargs = _filter_read_kwargs(self.get_affine, merged_kwargs)
    convert_kwargs = {
        key: value
        for key, value in convert_kwargs.items()
        if key not in affine_kwargs
    }
    if affine_kwargs:
        logger.debug(
            "Calling get_affine for scan %s reco %s with args %s",
            getattr(self, "scan_id", "?"),
            resolved_reco_id,
            affine_kwargs,
        )
        affines = self.get_affine(
            resolved_reco_id,
            space=space,
            override_subject_type=override_subject_type,
            override_subject_pose=override_subject_pose,
            **affine_kwargs,
        )
    else:
        logger.debug(
            "Calling get_affine for scan %s reco %s (no args)",
            getattr(self, "scan_id", "?"),
            resolved_reco_id,
        )
        affines = self.get_affine(
            resolved_reco_id,
            space=space,
            override_subject_type=override_subject_type,
            override_subject_pose=override_subject_pose,
        )
    
    if dataobjs is None or affines is None:
        return None
    
    if not isinstance(dataobjs, tuple):
        dataobjs = (dataobjs,)
    if not isinstance(affines, tuple):
        affines = (affines,)
    
    dataobjs = list(dataobjs)
    # -F flattens like numpy order="A" on the data as read; keep that order after scaling
    flatten_orders = [
        "F" if (d.flags.f_contiguous and not d.flags.c_contiguous) else "C" for d in dataobjs
    ]
    # different per-frame slope/offset: apply to the data before flattening
    # (BRK-0035 option C); converter hooks get the raw data as before
    converter_func = getattr(self, "converter_func", None)
    scaling_applied = False
    if not isinstance(converter_func, ConvertType):
        _layout_warnings(self, resolved_reco_id)
        scaled, scaling_applied = scale_frames(
            self,
            resolved_reco_id,
            tuple(dataobjs),
            axis=merged_kwargs.get("axis"),
            frames=merged_kwargs.get("frames"),
            cycle_index=merged_kwargs.get("cycle_index"),
            cycle_count=merged_kwargs.get("cycle_count"),
        )
        dataobjs = list(scaled)
    for i, dataobj in enumerate(dataobjs):
        if flatten_fg and dataobj.ndim > 4:
            spatial_shape = dataobj.shape[:3]
            flattened = int(np.prod(dataobj.shape[3:]))
            dataobjs[i] = dataobj.reshape((*spatial_shape, flattened), order=flatten_orders[i])
    dataobjs = tuple(dataobjs)

    if isinstance(converter_func, ConvertType):
        # the hook gets the reco id and the frame selection when it takes them or **kwargs
        # (BRK-0046); the data stay as read, and helper.scale_frames applies the per-frame
        # rule with the same selection if the hook wants it
        selection = {
            key: merged_kwargs[key]
            for key in ("axis", "frames", "cycle_index", "cycle_count")
            if merged_kwargs.get(key) is not None
        }
        # the NIfTI output options always go to the hook's convert when it takes them
        # or **kwargs, even when get_dataobj/get_affine named them (WI-0110)
        output = {key: merged_kwargs[key] for key in ("xyz_units", "t_units") if key in merged_kwargs}
        header = override_header if override_header is not None else merged_kwargs.get("override_header")
        if header is not None:
            output["override_header"] = header
        hook_call_kwargs = _filter_hook_kwargs(
            converter_func,
            {**convert_kwargs, **output, **selection, "reco_id": resolved_reco_id},
        )
        logger.debug(
            "Calling converter hook for scan %s reco %s with args %s",
            getattr(self, "scan_id", "?"),
            resolved_reco_id,
            hook_call_kwargs,
        )
        return converter_func(
            dataobj=dataobjs,
            affine=affines,
            **hook_call_kwargs,
        )

    nifti1image_kwargs = {
        "override_header": override_header,
        **kwargs,
    }
    nifti1image_kwargs = _filter_hook_kwargs(get_nifti1image, nifti1image_kwargs)
    nifti1image_kwargs["scaling_applied"] = scaling_applied
    return get_nifti1image(
        self,
        reco_id=resolved_reco_id,
        dataobjs=dataobjs,
        affines=affines,
        **nifti1image_kwargs,
    )

def _resolve_hook_kwargs(
    scan: Union["Scan", "ScanLoader"],
    hook_args_by_name: Optional[Mapping[str, Mapping[str, Any]]],
) -> Dict[str, Any]:
    if not hook_args_by_name:
        return {}
    hook_name = getattr(scan, "_converter_hook_name", None)
    if not isinstance(hook_name, str) or not hook_name:
        return {}
    logger.debug(
        "Resolving hook args for scan %s hook %s (available: %s)",
        getattr(scan, "scan_id", "?"),
        hook_name,
        sorted(hook_args_by_name.keys()),
    )
    values = hook_args_by_name.get(hook_name)
    if values is None:
        seen: set[str] = set()

        def _add(candidate: str) -> None:
            cand = candidate.strip()
            if not cand or cand in seen:
                return
            seen.add(cand)

        _add(hook_name)
        _add(hook_name.lower())
        _add(hook_name.replace("_", "-"))
        _add(hook_name.replace("-", "_"))
        _add(hook_name.lower().replace("_", "-"))
        _add(hook_name.lower().replace("-", "_"))
        _add(f"brkraw-{hook_name}")
        _add(f"brkraw_{hook_name}")
        _add(f"brkraw-{hook_name.lower()}")
        _add(f"brkraw_{hook_name.lower()}")
        _add(f"brkraw-{hook_name.lower().replace('_', '-')}")
        _add(f"brkraw_{hook_name.lower().replace('-', '_')}")

        for candidate in sorted(seen):
            if candidate == hook_name:
                continue
            candidate_values = hook_args_by_name.get(candidate)
            if candidate_values is not None:
                logger.debug(
                    "Using hook args for %r from alias %r.",
                    hook_name,
                    candidate,
                )
                values = candidate_values
                break
    resolved = dict(values) if isinstance(values, Mapping) else {}
    if resolved:
        logger.debug("Resolved hook args for %s: %s", hook_name, resolved)
    else:
        logger.debug("No hook args resolved for %s.", hook_name)
    return resolved


def _filter_hook_kwargs(func: Any, hook_kwargs: Mapping[str, Any]) -> Dict[str, Any]:
    """Drop unsupported hook kwargs for a callable.

    This keeps YAML/CLI presets safe when converter hooks do not accept
    arbitrary kwargs.
    """
    if not hook_kwargs:
        return {}
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return dict(hook_kwargs)
    for param in sig.parameters.values():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return dict(hook_kwargs)
    allowed = {
        param.name
        for param in sig.parameters.values()
        if param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        and param.name != "self"
    }
    filtered = {key: value for key, value in hook_kwargs.items() if key in allowed}
    dropped = [key for key in hook_kwargs.keys() if key not in allowed]
    if dropped:
        logger.debug(
            "Ignoring unsupported hook args for %s: %s",
            getattr(func, "__name__", "<callable>"),
            ", ".join(sorted(dropped)),
        )
    return filtered


# NIfTI output options: they describe the written file, not how the data or the
# affine are read (WI-0110, D-0180).
OUTPUT_KWARGS = ("xyz_units", "t_units", "override_header")


def _filter_read_kwargs(func: Any, kwargs: Mapping[str, Any]) -> Dict[str, Any]:
    """Kwargs for ``get_dataobj``/``get_affine``.

    Like :func:`_filter_hook_kwargs`, but the NIfTI output options are passed
    only when ``func`` names them as parameters, never through ``**kwargs``:
    a hook that takes ``**kwargs`` for its own options would otherwise take
    them away from ``convert``.
    """
    filtered = _filter_hook_kwargs(func, kwargs)
    try:
        named = {
            param.name
            for param in inspect.signature(func).parameters.values()
            if param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        }
    except (TypeError, ValueError):
        named = set()
    for key in OUTPUT_KWARGS:
        if key in filtered and key not in named:
            del filtered[key]
    return filtered


def _resolve_metadata_spec(
    scan: "ScanLoader",
    spec: Optional[Union[Mapping[str, Any], str, Path]],
    *,
    base: Path,
) -> Optional[Tuple[Mapping[str, Any], Dict[str, Any], Optional[Path]]]:
    """Resolve a metadata spec and its transforms for a scan.

    Args:
        scan: Scan instance to evaluate rules against.
        spec: Optional spec mapping or spec path override.
        base: Config root directory for rule resolution.

    Returns:
        Tuple of (spec, transforms, spec_path) or None when no spec matches.
    """
    if spec is None:
        try:
            rules = load_rules(root=base, validate=False)
        except Exception:
            return None
        spec_path = select_rule_use(
            scan,
            rules.get("metadata_spec", []),
            base=base,
            resolve_paths=True,
        )
        if not isinstance(spec_path, Path) or not spec_path.exists():
            return None
        spec_data, transforms = load_spec(spec_path, validate=False)
        return spec_data, transforms, spec_path
    if isinstance(spec, (str, Path)):
        spec_path = Path(spec)
        spec_data, transforms = load_spec(spec_path, validate=False)
        return spec_data, transforms, spec_path
    if isinstance(spec, Mapping):
        return spec, {}, None
    raise TypeError(f"Unsupported spec type: {type(spec)!r}")


def get_metadata(
    self,
    reco_id: Optional[int] = None,
    spec: Optional[Union[Mapping[str, Any], str, Path]] = None,
    return_spec: bool = False,
) -> Metadata:
    """Resolve metadata using a remapper spec.

    A context map's ``sidecar`` fields are applied by the caller with
    ``brkraw.specs.context_map.plan_scan`` (0.6.0: no ``context_map`` argument).

    Args:
        self: Scan instance.
        reco_id: Reco identifier (defaults to the first available).
        spec: Optional spec mapping or spec file path.
        return_spec: If True, return spec info alongside metadata.

    Returns:
        Mapping of metadata fields, or None when no spec matches. When
        return_spec is True, returns (metadata, spec_info).
    """
    scan = cast(ScanLoader, self)
    resolved_reco_id = resolve_reco_id(scan, reco_id)
    if resolved_reco_id is None:
        if return_spec:
            return None, None
        return None
    base = resolve_root(None)
    resolved = _resolve_metadata_spec(scan, spec, base=base)
    if resolved is None:
        if return_spec:
            return None, None
        return None
    spec_data, transforms, spec_path = resolved
    metadata = map_parameters(
        scan,
        spec_data,
        transforms,
        validate=False,
        context={"scan_id": getattr(scan, "scan_id", None), "reco_id": resolved_reco_id},
    )
    if not return_spec:
        return metadata
    meta = spec_data.get("__meta__")
    name = meta.get("name") if isinstance(meta, dict) else None
    version = meta.get("version") if isinstance(meta, dict) else None
    spec_info = {"path": spec_path, "name": name, "version": version}
    return metadata, spec_info


def apply_converter_hook(
    scan: "ScanLoader",
    converter_hook: Mapping[str, Any],
    *,
    affine_decimals: Optional[int] = None,
) -> None:
    """Override scan conversion helpers using a converter hook."""
    converter_core.validate_hook(converter_hook)
    plugin = dict(converter_hook)
    logger.debug(
        "Binding converter hook for scan %s: %s",
        getattr(scan, "scan_id", "?"),
        sorted(plugin.keys()),
    )
    if "get_dataobj" in plugin and not isinstance(plugin["get_dataobj"], GetDataobjType):
        raise TypeError("Converter hook 'get_dataobj' must match GetDataobjType.")
    if "get_affine" in plugin and not isinstance(plugin["get_affine"], GetAffineType):
        raise TypeError("Converter hook 'get_affine' must match GetAffineType.")
    if "convert" in plugin and not isinstance(plugin["convert"], ConvertType):
        raise TypeError("Converter hook 'convert' must match ConvertType.")
    scan._converter_hook = plugin
    if "get_dataobj" in plugin:
        scan.get_dataobj = MethodType(plugin["get_dataobj"], scan)
    if "get_affine" in plugin:
        get_affine = plugin["get_affine"]
        if affine_decimals is not None:
            get_affine = partial(get_affine, decimals=affine_decimals)
        scan.get_affine = MethodType(get_affine, scan)
    if "convert" in plugin:
        scan.converter_func = MethodType(plugin["convert"], scan)
    else:
        scan.converter_func = None
    logger.debug(
        "Converter hook bound for scan %s (hook=%s)",
        getattr(scan, "scan_id", "?"),
        getattr(scan, "_converter_hook_name", None),
    )
