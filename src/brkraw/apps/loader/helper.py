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
    Dict
)
from pathlib import Path
from warnings import warn
import logging

import numpy as np
from numpy.typing import NDArray
from nibabel.nifti1 import Nifti1Image

from ...core.config import resolve_root
from ...core.parameters import Parameters
from ...specs.remapper import load_spec, map_parameters, load_context_map, apply_context_map
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


def get_dataobj(
    self: "ScanLoader",
    reco_id: Optional[int] = None,
    **kwargs: Dict[str, Any]
) -> Dataobjs:
    """Return reconstructed data for a reco, split by slice pack if needed.

    Args:
        self: Scan or ScanLoader instance.
        reco_id: Reco identifier to read (defaults to the first available).
        cycle_index: Optional cycle start index (last axis), reads all cycles when None.
        cycle_count: Optional number of cycles to read from cycle_index; reads to end when None.
            Ignored when the dataset reports <= 1 total cycle.

    Returns:
        Single ndarray when one slice pack exists; otherwise a tuple of arrays.
        Returns None when required metadata is unavailable.
    """
    cycle_index = cast(Optional[int], kwargs.get('cycle_index'))
    cycle_count = cast(Optional[int], kwargs.get('cycle_count'))
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

    if cycle_args_requested or image_info.get("dataobj") is None:
        image_info = image_resolver.resolve(
            self,
            resolved_reco_id,
            load_data=True,
            cycle_index=cycle_index,
            cycle_count=cycle_count,
        )
        self.image_info[resolved_reco_id] = image_info

    num_slices = affine_info["num_slices"]
    dataobj = cast(dict, image_info).get("dataobj")
    slice_pack = []
    slice_offset = 0
    for _num_slices in num_slices:
        _dataobj = cast(NDArray, dataobj)[:, :, slice(slice_offset, slice_offset + _num_slices)]
        slice_offset += _num_slices
        slice_pack.append(_dataobj)

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
) -> ConvertedObj:
    """Return NIfTI image(s) for a reco.

    Args:
        self: Scan or ScanLoader instance.
        reco_id: Reco identifier to read (defaults to the first available).
        xyz_units: Spatial units for NIfTI header.
        t_units: Temporal units for NIfTI header.
        override_header: Optional header values to apply.

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

    niiobjs = []
    for i, dataobj in enumerate(dataobjs):
        affine = affines[i]
        niiobj = Nifti1Image(dataobj, affine)
        nifti1header_contents = nifti_resolver.resolve(
            image_info, xyz_units=xyz_units, t_units=t_units
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

    data_kwargs = _filter_hook_kwargs(self.get_dataobj, merged_kwargs)
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

    affine_kwargs = _filter_hook_kwargs(self.get_affine, merged_kwargs)
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
    for i, dataobj in enumerate(dataobjs):
        if flatten_fg and dataobj.ndim > 4:
            spatial_shape = dataobj.shape[:3]
            flattened = int(np.prod(dataobj.shape[3:]))
            dataobjs[i] = dataobj.reshape((*spatial_shape, flattened), order="A")
    dataobjs = tuple(dataobjs)

    converter_func = getattr(self, "converter_func", None)
    if isinstance(converter_func, ConvertType):
        hook_call_kwargs = _filter_hook_kwargs(converter_func, convert_kwargs)
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
    context_map: Optional[Union[str, Path]] = None,
    return_spec: bool = False,
) -> Metadata:
    """Resolve metadata using a remapper spec.

    Args:
        self: Scan instance.
    reco_id: Reco identifier (defaults to the first available).
        spec: Optional spec mapping or spec file path.
    context_map: Optional context map override.
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
        context_map=None,
        context={"scan_id": getattr(scan, "scan_id", None), "reco_id": resolved_reco_id},
    )
    if context_map:
        map_data = load_context_map(context_map)
        metadata = apply_context_map(
            metadata,
            map_data,
            target="metadata_spec",
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
