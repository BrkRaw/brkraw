from __future__ import annotations
from typing import Optional, Union, TypedDict, Tuple, Literal, List, Any, TYPE_CHECKING
from typing import cast
if TYPE_CHECKING:
    from typing_extensions import TypeAlias
else:
    try:
        from typing import TypeAlias
    except ImportError:  # pragma: no cover - fallback for Python 3.8
        from typing_extensions import TypeAlias
from .helpers import get_file, get_reco, return_alt_val_if_none
import logging
import numpy as np

logger = logging.getLogger("brkraw")

if TYPE_CHECKING:
    from ..dataclasses import Scan, Reco
    from ..core.parameters import Parameters

SubjectType: TypeAlias = Literal["Biped", "Quadruped", "Phantom", "Other", "OtherAnimal"]
SubjectPose: TypeAlias = Literal[
    "Head_Supine", "Head_Prone", "Head_Left", "Head_Right",
    "Foot_Supine", "Foot_Prone", "Foot_Left", "Foot_Right",
]


class ResolvedSlicePack(TypedDict):
    num_slice_packs: int
    num_slices: List[int]
    slice_thickness: List[Union[float, int]]
    slice_gap: List[Union[float, int]]
    unit: str


class ResolvedAffine(TypedDict):
    num_slice_packs: int
    affines: List[np.ndarray]
    num_slices: List[int]
    subject_type: Optional[SubjectType]
    subject_position: SubjectPose
    is_unwrapped: bool


def from_matvec(mat: np.ndarray, vec: np.ndarray) -> np.ndarray:
    """Create a 4x4 affine matrix from a 3x3 rotation/scale matrix and a 3-vector."""
    if mat.shape == (3, 3) and vec.shape == (3,):
        affine = np.eye(4)
        affine[:3, :3] = mat
        affine[:3, 3] = vec
        return affine
    else:
        raise ValueError("Matrix must be 3x3 and vector must be 1x3")
    

def to_matvec(affine: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Decompose a 4x4 affine matrix into a 3x3 matrix and a 3-vector."""
    if affine.shape != (4, 4):
        raise ValueError("Affine matrix must be 4x4")
    mat = affine[:3, :3]
    vec = affine[:3, 3]
    return mat, vec


def rotate_affine(
    affine: np.ndarray,
    rad_x: float = 0.0,
    rad_y: float = 0.0,
    rad_z: float = 0.0,
    pivot: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Rotate a 4x4 affine around a pivot point by given radians along x, y, z axes.

    Parameters
    ----------
    affine : (4,4) ndarray
        Input affine matrix.
    rad_x, rad_y, rad_z : float
        Rotation angles in radians about scanner/world axes.
    pivot : (3,) ndarray or None
        Rotation center in world coordinates (origin if None).

    Returns
    -------
    rotated_affine : (4,4) ndarray
    """

    A = np.asarray(affine, dtype=float)

    # --- rotation matrices ---
    Rx = np.array([
        [1, 0, 0],
        [0,  np.cos(rad_x), -np.sin(rad_x)],
        [0,  np.sin(rad_x),  np.cos(rad_x)],
    ])

    Ry = np.array([
        [ np.cos(rad_y), 0, np.sin(rad_y)],
        [0,              1, 0],
        [-np.sin(rad_y), 0, np.cos(rad_y)],
    ])

    Rz = np.array([
        [np.cos(rad_z), -np.sin(rad_z), 0],
        [np.sin(rad_z),  np.cos(rad_z), 0],
        [0,              0,             1],
    ])

    # rotation order: x -> y -> z
    R = Rz @ Ry @ Rx
    M, t = to_matvec(A)
    M_new = R @ M

    if pivot is None:
        t_new = R @ t
    else:
        p = np.asarray(pivot, dtype=float).reshape(3,)
        t_new = R @ t + (p - R @ p)
    return from_matvec(M_new, t_new)


def flip_affine(
    affine: np.ndarray,
    flip_x: bool = False,
    flip_y: bool = False,
    flip_z: bool = False,
    pivot: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Flip selected world axes of an affine matrix.

    Applies sign flips to the x/y/z directions of the input affine's rotation
    and adjusts the translation either about the origin (default) or about a
    supplied 3D pivot point. This operates purely in world space; voxel shape
    is not required.
    """
    A = np.asarray(affine, dtype=float)
    M, t = to_matvec(A)

    sx = -1.0 if flip_x else 1.0
    sy = -1.0 if flip_y else 1.0
    sz = -1.0 if flip_z else 1.0
    F = np.diag([sx, sy, sz])

    M_new = F @ M

    if pivot is None:
        t_new = F @ t
    else:
        p = np.asarray(pivot, dtype=float).reshape(3,)
        t_new = F @ t + (p - F @ p)

    return from_matvec(M_new, t_new)


def flip_voxel_axis_affine(
    affine: np.ndarray,
    axis: int,
    shape: Tuple[int, ...]
) -> np.ndarray:
    """
    Flip a specific voxel axis in an affine matrix.

    Negates the column corresponding to `axis` in the affine's rotation and
    shifts the translation by `(n-1)` voxels along that axis so the flipped
    coordinates still index the same physical space for an array of `shape`.
    This is voxel-shape aware and differs from `flip_affine`, which flips in
    world space without needing `shape`.
    """
    A = np.asarray(affine, float)
    M = A[:3, :3].copy()
    t = A[:3, 3].copy()

    n = int(shape[axis])
    if n <= 1:
        return A.copy()

    col = M[:, axis].copy()    # original column
    M[:, axis] = -M[:, axis]   # flip direction
    t = t + col * (n - 1)      # translation correction

    out = np.eye(4)
    out[:3, :3] = M
    out[:3, 3] = t
    return out


def unwrap_to_scanner_xyz(
        affine: np.ndarray,
        subject_type: Optional[SubjectType], 
        subject_pose: SubjectPose) -> np.ndarray:
    """Normalize an affine to scanner orientation for a subject pose.

    Args:
        affine: (4, 4) affine in world/scanner space.
        subject_type: Subject category. Supported values include "Biped",
            "Quadruped", "Phantom", "OtherAnimal", and "Other". If ``None``,
            it defaults to ``"Biped"`` for PV5.1 compatibility. Unwrapping is
            only tested for "Biped" and "Quadruped".
        subject_pose: Pose string formatted as
            ``"Head|Foot" + "_" + "Supine|Prone|Left|Right"``. The prefix
            indicates head-first or feet-first entry; the suffix captures the
            gravity orientation.

    Returns:
        Affine reoriented to scanner L-R, bottom-to-top, front-to-back.
    """
    _affine = np.asarray(affine)
    head_or_foot, gravity = subject_pose.split('_', 1)
    subject_type = subject_type or 'Biped' # backward compatibility with PV5.1 (subject_type == None)

    if head_or_foot == "Foot":
        _affine = rotate_affine(_affine, rad_y=np.pi)

    if subject_type == "Biped":
        # Paravision stores affine based on LPS+, but scanner coordinate is LAS+(based on subject orientation)
        # correspond to scanner left to right(x), buttom to top(y), front to back(z) according to the operation's view
        # simply flip y axis unwrap subject to scanner orient
        _affine = flip_affine(_affine, flip_y=True)
        if gravity == "Prone":
            _affine = rotate_affine(_affine, rad_z=np.pi)
        elif gravity == "Left":
            _affine = rotate_affine(_affine, rad_z=-np.pi/2)
        elif gravity == "Right":
            _affine = rotate_affine(_affine, rad_z=np.pi/2)

    elif subject_type == "Quadruped":
        # Paravision convert affine to match LSA+ of Quadruped subject, 
        # but the scanner coordinate is RSA+(based on subject orientation)
        _affine = flip_affine(_affine, flip_x=True)
        if gravity == "Supine":
            _affine = rotate_affine(_affine, rad_z=np.pi)
        elif gravity == "Left":
            _affine = rotate_affine(_affine, rad_z=np.pi/2)
        elif gravity == "Right":
            _affine = rotate_affine(_affine, rad_z=-np.pi/2)
    
    return _affine

def wrap_to_subject_ras(affine: np.ndarray, 
                      subject_type: Optional[SubjectType], 
                      subject_pose: SubjectPose) -> np.ndarray:
    """Reorient an affine from scanner space back to a subject pose.

    Args:
        affine: (4, 4) affine in world/scanner space.
        subject_type: Subject category. Supported values include "Biped",
            "Quadruped", "Phantom", "OtherAnimal", and "Other". If ``None``,
            it defaults to ``"Biped"`` for PV5.1 compatibility.
        subject_pose: Override pose string formatted as
            ``"Head|Foot" + "_" + "Supine|Prone|Left|Right"``. The prefix
            indicates head-first or feet-first entry; the suffix captures the
            gravity orientation.

    Returns:
        Affine reoriented to subject RAS+.
    """
    _affine = np.asarray(affine)
    head_or_foot, gravity = subject_pose.split('_', 1)
    
    # device back: Head / foot
    if head_or_foot == "Foot":
        _affine = rotate_affine(_affine, rad_y=np.pi)
    
    subject_type = subject_type or 'Biped' # backward compatibility with PV5.1 (subject_type == None)

    if subject_type == "Biped":
        # in operators view (scanner), patient is LAS+ in scanner coordinate in "Head_Supine" position (after unwrap)
        # step1. LAS+ (scanner coordinate) to LAI+ (subject coordinate, dicom)
        _affine = flip_affine(_affine, flip_z=True)
        # step2. LAI+ to RAS+
        _affine = rotate_affine(_affine, rad_y=np.pi)
        if gravity == "Prone":
            _affine = rotate_affine(_affine, rad_z=np.pi)
        elif gravity == "Left":
            _affine = rotate_affine(_affine, rad_z=np.pi/2)
        elif gravity == "Right":
            _affine = rotate_affine(_affine, rad_z=-np.pi/2)

    elif subject_type == "Quadruped":
        # in unwrapped view (scanner), subject is RSA+ in "Head_Prone" position
        # step1. RSA+ to RSP+
        _affine = flip_affine(_affine, flip_z=True)
        # step2. RSP+ to RAS+
        _affine = rotate_affine(_affine, rad_x=np.pi/2)
        if gravity == "Supine":
            _affine = rotate_affine(_affine, rad_z=np.pi)
        elif gravity == "Left":
            _affine = rotate_affine(_affine, rad_z=-np.pi/2)
        elif gravity == "Right":
            _affine = rotate_affine(_affine, rad_z=np.pi/2)
    
    return _affine


def resolve_matvec_and_shape(visu_pars, 
                             spack_idx: int,
                             num_slices: List[int],
                             slice_thickness: List[Union[float, int]]) -> Tuple[np.ndarray, np.ndarray, Tuple[int, ...]]:
    """
    Build an affine matrix, origin vector, and volume shape for a Bruker dataset.

    Parameters
    ----------
    visu_pars : mapping
        Must contain `VisuCoreDim`, `VisuCoreOrientation`, `VisuCorePosition`,
        `VisuCoreExtent`, `VisuCoreSize`.
    spack_idx : int
        Slice-package index into `num_slices` and `slice_thickness`.
    num_slices : sequence[int]
        Number of slices per package; length must match available orientations/positions.
    slice_thickness : sequence[float]
        Thickness per slice package (same length as `num_slices`).

    Returns
    -------
    mat : np.ndarray
        3x3 affine matrix whose columns are row/col/slice direction vectors scaled
        by voxel resolutions.
    vec : np.ndarray
        Reference origin (world coordinates) for the chosen slice package.
    shape : Tuple[int]
        3D matrix size

    Raises
    ------
    ValueError on shape mismatch or missing orientations/positions.
    IndexError if `spack_idx` is out of range.
    """
    dim = visu_pars.get("VisuCoreDim")
    rotate = np.asarray(visu_pars.get("VisuCoreOrientation"), dtype=float)
    origin = np.asarray(visu_pars.get("VisuCorePosition"), dtype=float)
    extent = np.asarray(visu_pars.get("VisuCoreExtent"), dtype=float)
    shape  = np.asarray(visu_pars.get("VisuCoreSize"), dtype=float)

    if dim == 2:
        num_slicepack = len(num_slices)

        if spack_idx < 0 or spack_idx >= num_slicepack:
            raise IndexError(f"spack_idx out of range: {spack_idx} (num packs: {num_slicepack})")

        total_slices = int(np.sum(np.asarray(num_slices, dtype=int)))
        spack_slice_start = int(np.sum(np.asarray(num_slices[:spack_idx], dtype=int)))
        spack_slice_end = spack_slice_start + int(num_slices[spack_idx])

        def _select_slice_entries(arr: np.ndarray, *, width: int, name: str) -> np.ndarray:
            arr = np.asarray(arr, dtype=float)
            if arr.ndim == 1:
                if arr.size == width:
                    arr = arr.reshape((1, width))
                else:
                    raise ValueError(f"{name} has shape {arr.shape}, expected (*, {width})")
            if arr.ndim != 2 or arr.shape[1] != width:
                raise ValueError(f"{name} has shape {arr.shape}, expected (*, {width})")

            # Prefer per-slice entries (concatenated across slice packs).
            if arr.shape[0] > total_slices:
                if not np.allclose(arr[:total_slices], arr[0], atol=0, rtol=0):
                    logger.warning(
                        "%s has %s entries but expected %s; using the first %s entries.",
                        name,
                        arr.shape[0],
                        total_slices,
                        total_slices,
                    )
                arr = arr[:total_slices, :]

            if arr.shape[0] == total_slices:
                return arr[spack_slice_start:spack_slice_end, :]

            # Fallback: per-pack entries (one entry per slice pack).
            if arr.shape[0] == num_slicepack:
                if int(num_slices[spack_idx]) != 1:
                    raise ValueError(
                        f"{name} provides one entry per slice pack ({num_slicepack}) "
                        f"but pack {spack_idx} has {num_slices[spack_idx]} slices; "
                        "per-slice entries are required to resolve slice positions."
                    )
                return arr[spack_idx:spack_idx + 1, :]

            raise ValueError(
                f"{name} has {arr.shape[0]} entries, expected {total_slices} (per-slice) "
                f"or {num_slicepack} (per-pack); method num_slices={num_slices}."
            )

        _rotate = _select_slice_entries(rotate, width=9, name="VisuCoreOrientation")
        _origin = _select_slice_entries(origin, width=3, name="VisuCorePosition")
        _num_slices = num_slices[spack_idx]
        _slice_thickness = slice_thickness[spack_idx]
        
        if _rotate.shape[0] > 1 and not np.allclose(_rotate, _rotate[0], atol=0, rtol=0):
            logger.warning(
                "VisuCoreOrientation varies across slices in pack %s; using the first slice orientation.",
                spack_idx,
            )

        row = _rotate[0, 0:3]
        col = _rotate[0, 3:6]
        slc = _rotate[0, 6:9]

        n = slc.astype(float)
        n = n / np.linalg.norm(n)

        if _num_slices > 1:
            # project each slice position onto slice normal
            s = _origin @ n  # shape (num_slices,)
            idx = int(np.argmin(s))
            vec = _origin[idx]
        else:
            vec = _origin[0]
        shape = np.append(shape, _num_slices)
        extent = np.append(extent, _num_slices * _slice_thickness)
    else:
        _rotate = np.squeeze(rotate)
        row = _rotate[0:3]
        col = _rotate[3:6]
        slc = _rotate[6:9]
        vec = np.squeeze(origin)

    rot = np.column_stack([row, col, slc])
    resols = extent / shape
    mat = rot * resols.reshape(1, 3)
    return mat, vec, tuple(shape.astype(int).tolist())


def resolve_slice_pack(
        scan: "Scan",
    ) -> Optional[ResolvedSlicePack]:
    """Compute slice pack layout across Paravision versions.

    Args:
        scan: Scan node providing method.
    Returns:
        SlicePackInfo with pack counts, slices per pack, distances, gaps; None if not a spatial data case.
    """
    try:
        method: "Parameters" = get_file(scan, 'method')
    except FileNotFoundError:
        return None
    
    slice_pack_info = method.search_keys('spack')
    if len(slice_pack_info) == 0:
        # no slice pack
        return None

    num_slice_packs = method.get('PVM_NSPacks') or 1
    num_slices = cast(Union[List[Any], np.ndarray],
                      return_alt_val_if_none(method.get('PVM_SPackArrNSlices'), [1]))
    slice_thickness = cast(Union[List[Any], np.ndarray],
                           return_alt_val_if_none(method.get('PVM_SPackArrSliceDistance'), [0]))
    slice_gap = cast(Union[List[Any], np.ndarray],
                     return_alt_val_if_none(method.get('PVM_SPackArrSliceGap'), [0]))

    def _normalize_ndarray_to_list(val: Union[List[Any], np.ndarray]) -> List[Any]:
        if isinstance(val, np.ndarray):
            return val.tolist()
        return val

    result: ResolvedSlicePack = {
        'num_slice_packs': num_slice_packs,
        'num_slices': _normalize_ndarray_to_list(num_slices),
        'slice_thickness': _normalize_ndarray_to_list(slice_thickness),
        'slice_gap': _normalize_ndarray_to_list(slice_gap),
        'unit': 'mm',
    }
    return result


def get_subject_type_and_position(visu_pars: "Parameters") -> Tuple[Optional[SubjectType], SubjectPose]:
    subj_type = visu_pars.get("VisuSubjectType")
    subj_position = visu_pars.get("VisuSubjectPosition")
    return cast(Optional[SubjectType], subj_type), cast(SubjectPose, subj_position)


def resolve(
    scan: "Scan", 
    reco_id: int = 1, 
    decimals: int = 6, 
    unwrap_pose: bool = False
) -> Optional[ResolvedAffine]:
    """Resolve per-slice-pack affines for a scan.
    
    Args:
        scan: Scan node containing the target reco.
        reco_id: Reco id to process (default: 1).
        decimals: Number of decimals to round affines for stability.
        unwrap_pose: If True, reorient affines to scanner space based on subject pose.

    Returns:
        AffineInfo with per-pack affines, slice counts, subject metadata, and
        whether pose unwrapping was applied; None if required files are missing.
    """
    
    reco: "Reco" = get_reco(scan, reco_id)
    try:
        acqp = get_file(scan, 'acqp')
        method = get_file(scan, 'method')
        visu_pars = get_file(reco, 'visu_pars')
    except FileNotFoundError:
        return None

    slice_orient = method.get('PVM_SPackArrSliceOrient')
    phase_dir = acqp.get('ACQ_scaling_phase') or 1

    slice_info = resolve_slice_pack(scan)
    if not slice_info:
        return None

    num_slice_packs = slice_info['num_slice_packs']
    num_slices = slice_info['num_slices']
    slice_thickness = slice_info['slice_thickness']
    slice_gap = slice_info['slice_gap']

    # slice thickness = image shickness + slice gap
    slice_thickness = [t + slice_gap[i] for i, t in enumerate(slice_thickness)]

    subj_type, subj_position = get_subject_type_and_position(visu_pars)
    
    affines = []
    shape: Optional[Tuple[int, ...]] = None
    for spack_idx in range(num_slice_packs):
        spack_slice_orient = slice_orient if num_slice_packs == 1 else slice_orient[spack_idx]
        spack_mat, spack_vec, shape = resolve_matvec_and_shape(visu_pars, spack_idx, num_slices, slice_thickness)

        affine = from_matvec(spack_mat, spack_vec)
        if phase_dir < 0:
            affine = flip_voxel_axis_affine(affine[:], axis=1, shape=shape)
        if spack_slice_orient == 'coronal':
            affine = flip_voxel_axis_affine(affine[:], axis=2, shape=shape)
        if unwrap_pose:
            affine = unwrap_to_scanner_xyz(affine[:], subj_type, subj_position)
        affines.append(np.round(affine, decimals=decimals))

    if shape is not None and num_slice_packs == 1 and num_slices[0] == 1 and shape[2] != num_slices[0]:
        num_slices = [shape[2]]

    result: ResolvedAffine = {
        'num_slice_packs': num_slice_packs,
        'affines': affines,
        'num_slices': num_slices,
        'subject_type': subj_type,
        'subject_position': subj_position,
        'is_unwrapped': unwrap_pose,
    }
    return result
