from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    TypedDict,
    Optional,
    Literal,
    Tuple,
    Sequence,
    Mapping,
    Union,
    cast,
    Any,
    get_args,
)
import logging
from pathlib import Path
import numpy as np
from nibabel.spatialimages import HeaderDataError
import yaml

if TYPE_CHECKING:
    from .image import ResolvedImage
    from nibabel.nifti1 import Nifti1Image

SLOPEMODE = Literal['header', 'dataobj', 'ignore']
TUNIT = Literal['sec', 'msec', 'usec', 'hz', 'ppm', 'rads']
XYZUNIT = Literal['unknown', 'meter', 'mm', 'micron']
XYZTUnit = Tuple[XYZUNIT, TUNIT]
DimInfo = Tuple[Optional[int], Optional[int], Optional[int]]

logger = logging.getLogger("brkraw")

class Nifti1HeaderContents(TypedDict, total=False):
    slice_code: int
    slope_inter: Tuple[float, float]
    time_step: Optional[float]
    slice_duration: Optional[float]
    xyzt_unit: XYZTUnit
    qform: np.ndarray
    sform: np.ndarray
    qform_code: int
    sform_code: int
    dim_info: DimInfo
    slice_start: int
    slice_end: int
    intent_code: int
    intent_name: str
    descrip: str
    aux_file: str
    cal_min: float
    cal_max: float
    pixdim: Sequence[float]


_XYZ_UNITS = set(get_args(XYZUNIT))
_T_UNITS = set(get_args(TUNIT))
_HEADER_FIELDS = {
    "slice_code",
    "slope_inter",
    "time_step",
    "slice_duration",
    "xyzt_unit",
    "qform",
    "sform",
    "qform_code",
    "sform_code",
    "dim_info",
    "slice_start",
    "slice_end",
    "intent_code",
    "intent_name",
    "descrip",
    "aux_file",
    "cal_min",
    "cal_max",
    "pixdim",
}


def load_header_overrides(path: Optional[Union[str, Path]]) -> Optional[Nifti1HeaderContents]:
    if not path:
        return None
    header_path = Path(path).expanduser()
    if not header_path.exists():
        logger.error("Header file not found: %s", header_path)
        raise ValueError("header file not found")
    if header_path.suffix.lower() not in {".yaml", ".yml"}:
        logger.error("Header file must be .yaml/.yml: %s", header_path)
        raise ValueError("header file must be yaml")
    try:
        data = yaml.safe_load(header_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to read header YAML: %s", exc)
        raise ValueError("header yaml read failed") from exc
    if data is None:
        return None
    if not isinstance(data, Mapping):
        logger.error("Header YAML must be a mapping at the top level.")
        raise ValueError("header yaml must be mapping")
    _validate_header_schema(data)
    return _coerce_header_contents(data)


def _load_header_schema() -> Optional[Mapping[str, Any]]:
    schema_path = Path(__file__).resolve().parents[3] / "schema" / "niftiheader.yaml"
    if schema_path.exists():
        return yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    logger.debug("NIfTI header schema not found: %s", schema_path)
    return None


def _validate_header_schema(data: Mapping[str, Any]) -> None:
    schema = _load_header_schema()
    if schema is None:
        _validate_header_minimal(data)
        return
    try:
        import jsonschema
    except Exception:
        _validate_header_minimal(data)
        return
    validator = jsonschema.Draft202012Validator(schema)
    errors = []
    for err in validator.iter_errors(data):
        path = ".".join(str(p) for p in err.path)
        prefix = f"header.{path}" if path else "header"
        errors.append(f"{prefix}: {err.message}")
    if errors:
        raise ValueError("Invalid NIfTI header overrides:\n" + "\n".join(errors))


def _validate_header_minimal(data: Mapping[str, Any]) -> None:
    extra = set(data.keys()) - _HEADER_FIELDS
    if extra:
        raise ValueError(f"Unknown NIfTI header fields: {sorted(extra)}")


def _coerce_bool(value: Any, *, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        val = value.strip().lower()
        if val in {"1", "true", "yes", "y", "on"}:
            return True
        if val in {"0", "false", "no", "n", "off"}:
            return False
        raise ValueError(f"Invalid {name}: {value!r}")
    return bool(value)


def _coerce_header_contents(data: Mapping[str, Any]) -> Nifti1HeaderContents:
    header: Nifti1HeaderContents = {}
    for key, value in data.items():
        if value is None:
            if key in {"time_step", "slice_duration"}:
                header[key] = None
                continue
            raise ValueError(f"{key} cannot be null.")
        if key in {"slice_code", "qform_code", "sform_code", "slice_start", "slice_end", "intent_code"}:
            header[key] = int(value)
        elif key in {"time_step", "slice_duration", "cal_min", "cal_max"}:
            header[key] = float(value)
        elif key == "slope_inter":
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                raise ValueError("slope_inter must be a 2-item list.")
            header[key] = (float(value[0]), float(value[1]))
        elif key == "xyzt_unit":
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                raise ValueError("xyzt_unit must be a 2-item list.")
            xyz, t = value
            if str(xyz) not in _XYZ_UNITS or str(t) not in _T_UNITS:
                raise ValueError("xyzt_unit must be one of supported XYZUNIT/TUNIT values.")
            header[key] = cast(XYZTUnit, (cast(XYZUNIT, str(xyz)), cast(TUNIT, str(t))))
        elif key in {"qform", "sform"}:
            arr = np.asarray(value, dtype=float)
            if arr.shape != (4, 4):
                raise ValueError(f"{key} must be a 4x4 matrix.")
            header[key] = arr
        elif key == "dim_info":
            if not isinstance(value, (list, tuple)) or len(value) != 3:
                raise ValueError("dim_info must be a 3-item list.")
            dim0 = None if value[0] is None else int(value[0])
            dim1 = None if value[1] is None else int(value[1])
            dim2 = None if value[2] is None else int(value[2])
            header[key] = (dim0, dim1, dim2)
        elif key in {"intent_name", "descrip", "aux_file"}:
            header[key] = str(value)
        elif key == "pixdim":
            if not isinstance(value, (list, tuple)) or not value:
                raise ValueError("pixdim must be a non-empty list.")
            header[key] = [float(v) for v in value]
        else:
            raise ValueError(f"Unknown NIfTI header field: {key}")
    return header


def _coerce_scalar(value, *, name: str) -> float:
    if isinstance(value, np.ndarray):
        if value.size == 0:
            return 0.0
        if value.size > 1:
            logger.debug("NIfTI %s array has multiple values; using first element.", name)
        return float(value.flat[0])
    if isinstance(value, (list, tuple)):
        if not value:
            return 0.0
        if len(value) > 1:
            logger.debug("NIfTI %s list has multiple values; using first element.", name)
        seq = cast(Sequence[float], value)
        return float(seq[0])
    return float(value)


def _coerce_int(value, *, name: str) -> int:
    return int(_coerce_scalar(value, name=name))


def _get_slice_code(sliceorder_scheme: Optional[str]) -> int:
    if sliceorder_scheme is None or sliceorder_scheme == "User_defined_slice_scheme":
        return 0
    if sliceorder_scheme == "Sequential":
        return 1
    elif sliceorder_scheme == 'Reverse_sequential':
        return 2
    elif sliceorder_scheme == 'Interlaced':
        return 3
    elif sliceorder_scheme == 'Reverse_interlacesd':
        return 4
    elif sliceorder_scheme == 'Angiopraphy':
        return 5
    else:
        return 0


def _set_dataobj(niiobj: "Nifti1Image", dataobj: np.ndarray) -> None:
    """Update the NIfTI data object, falling back to direct assignment."""
    setter = getattr(niiobj, "set_dataobj", None)
    if callable(setter):
        setter(dataobj)
    else:
        object.__setattr__(niiobj, "_dataobj", dataobj)


def resolve(
    image_info: "ResolvedImage",
    xyz_units: "XYZUNIT" = 'mm',
    t_units: "TUNIT" = 'sec'
) -> Nifti1HeaderContents:
    
    sliceorder_scheme = image_info['sliceorder_scheme']
    num_cycles = image_info['num_cycles']
    
    slice_code = _get_slice_code(sliceorder_scheme)
    if slice_code == 0:
        logger.debug(
            "Failed to identify compatible 'slice_code'. "
            "Please use this header information with care in case slice timing correction is needed."
        )
    
    if num_cycles > 1:
        time_step = cast(float, image_info['time_per_cycle']) / 1000.0
        num_slices = cast(np.ndarray, image_info['dataobj']).shape[2]
        slice_duration = time_step / num_slices
    else:
        time_step = None
        slice_duration = None
    slope = image_info['slope']
    offset = image_info['offset']
    result: Nifti1HeaderContents = {
        'slice_code': slice_code,
        'slope_inter': (slope, offset),
        'time_step': time_step,
        'slice_duration': slice_duration,
        'xyzt_unit': (xyz_units, t_units)
    }
    return result


def update(
    niiobj: "Nifti1Image",
    nifti1header_contents: Nifti1HeaderContents,
    slope_mode: SLOPEMODE = 'header',
):
    qform_code = nifti1header_contents.get("qform_code")
    sform_code = nifti1header_contents.get("sform_code")
    

    for c, val in nifti1header_contents.items():
        if val is None or c in ('qform_code', 'sform_code'):
            continue
        if c == "slice_code":
            if _coerce_int(val, name="slice_code") != 0:
                niiobj.header['slice_code'] = _coerce_int(val, name="slice_code")
        elif c == "slope_inter":
            pair = cast(Sequence[float], val)
            slope_val = _coerce_scalar(pair[0], name="slope")
            inter_val = _coerce_scalar(pair[1], name="intercept")
            if slope_mode == 'header':
                niiobj.header.set_slope_inter(slope_val, inter_val)
            elif slope_mode == 'dataobj':
                dataobj = np.asarray(niiobj._dataobj)
                _set_dataobj(niiobj, dataobj * slope_val + inter_val)
            else:
                pass
            niiobj.header.set_data_dtype(np.asarray(niiobj._dataobj).dtype)
        elif c == "time_step":
            niiobj.header['pixdim'][4] = _coerce_scalar(val, name="time_step")
        elif c == "slice_duration":
            slice_dim = niiobj.header.get_dim_info()[2]
            if slice_dim is None:
                logger.debug("Skipping slice_duration: slice dimension not set.")
                continue
            try:
                niiobj.header.set_slice_duration(_coerce_scalar(val, name="slice_duration"))
            except HeaderDataError as exc:
                logger.debug("Skipping slice_duration: %s", exc)
        elif c == "xyzt_unit":
            units = cast(Sequence[str], val)
            niiobj.header.set_xyzt_units(*units)
        elif c == "qform":
            if qform_code is None:
                niiobj.header.set_qform(val, 1)
            else:
                niiobj.header.set_qform(val, int(qform_code))
        elif c == "sform":
            if sform_code is None:
                niiobj.header.set_sform(val, 1)
            else:
                niiobj.header.set_sform(val, int(sform_code))
        elif c == "dim_info":
            dims = cast(Sequence[Optional[int]], val)
            niiobj.header.set_dim_info(*dims)
        elif c == "slice_start":
            niiobj.header['slice_start'] = _coerce_int(val, name="slice_start")
        elif c == "slice_end":
            niiobj.header['slice_end'] = _coerce_int(val, name="slice_end")
        elif c == "intent_code":
            niiobj.header['intent_code'] = _coerce_int(val, name="intent_code")
        elif c == "intent_name":
            niiobj.header['intent_name'] = str(val)
        elif c == "descrip":
            niiobj.header['descrip'] = str(val)
        elif c == "aux_file":
            niiobj.header['aux_file'] = str(val)
        elif c == "cal_min":
            niiobj.header['cal_min'] = _coerce_scalar(val, name="cal_min")
        elif c == "cal_max":
            niiobj.header['cal_max'] = _coerce_scalar(val, name="cal_max")
        elif c == "pixdim":
            if val:
                niiobj.header['pixdim'][1:1 + len(val)] = val # pyright: ignore[reportArgumentType]
        else:
            raise KeyError(f"Unknown NIfTI header field: {c}")
    return niiobj


__all__ = [
    'resolve',
    'update',
    'load_header_overrides',
]
