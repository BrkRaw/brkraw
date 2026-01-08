"""Typing helpers for app-level loader interfaces.

Last updated: 2025-12-30
"""

from __future__ import annotations

from typing import Any, Union, Tuple, Dict, Optional, Protocol, Literal, Mapping, Callable, List, TYPE_CHECKING
if TYPE_CHECKING:
    from typing_extensions import ParamSpec, TypeAlias
else:
    try:
        from typing import ParamSpec, TypeAlias
    except ImportError:  # pragma: no cover - fallback for Python 3.8
        from typing_extensions import ParamSpec, TypeAlias
from ...dataclasses.study import Study
from ...dataclasses.scan import Scan
from ...dataclasses.reco import Reco
import numpy as np

if TYPE_CHECKING:
    from pathlib import Path
    from ...core.parameters import Parameters
    from ...resolver.image import ResolvedImage
    from ...resolver.affine import ResolvedAffine, SubjectType, SubjectPose
    from ...resolver.nifti import Nifti1HeaderContents, XYZUNIT, TUNIT
    from nibabel.nifti1 import Nifti1Image
    


InfoScope = Literal['full', 'study', 'scan']
AffineReturn = Optional[Union[np.ndarray, Tuple[np.ndarray, ...]]]
AffineSpace = Literal["raw", "scanner", "subject_ras"]

P = ParamSpec("P")


class GetDataobjType(Protocol[P]):
    """Callable signature for get_dataobj overrides."""
    def __call__(
        self,
        scan: "Scan",
        reco_id: Optional[int],
        *args: P.args,
        **kwargs: P.kwargs
    ) -> Optional[Union[Tuple["np.ndarray", ...], "np.ndarray"]]:
        ...


class GetAffineType(Protocol):
    """Callable signature for get_affine overrides."""
    def __call__(
        self,
        scan: "Scan",
        reco_id: Optional[int],
        *,
        space: AffineSpace,
        override_subject_type: Optional[SubjectType],
        override_subject_pose: Optional[SubjectPose],
        decimals: Optional[int] = None,
        **kwargs: Any
    ) -> Optional[Union[Tuple["np.ndarray", ...], "np.ndarray"]]:
        ...


class GetNifti1ImageType(Protocol):
    """Callable signature for get_nifti1image overrides."""
    def __call__(
        self,
        scan: "Scan",
        reco_id: Optional[int] = None,
        *,
        override_header: Optional[Union[dict, "Nifti1HeaderContents"]],
        space: AffineSpace,
        override_subject_type: Optional[SubjectType],
        override_subject_pose: Optional[SubjectPose],
        flip_x: bool,
        xyz_units: XYZUNIT,
        t_units: TUNIT,
        **kwargs: Any,
    ) -> Optional[Union[Tuple["Nifti1Image", ...], "Nifti1Image"]]:
        ...


class ConvertType(Protocol):
    """Callable signature for convert overrides."""
    def __call__(
        self,
        scan: "Scan",
        reco_id: Optional[int] = None,
        *,
        format: Union[Literal["nifti", "nifti1"], str],
        override_header: Optional[Union[dict, "Nifti1HeaderContents"]],
        space: AffineSpace,
        override_subject_type: Optional[SubjectType],
        override_subject_pose: Optional[SubjectPose],
        flip_x: bool,
        xyz_units: XYZUNIT,
        t_units: TUNIT,
        **kwargs: Any,
    ) -> Optional[Union[Tuple["Nifti1Image", ...], "Nifti1Image"]]:
        ...


class BaseLoader(Protocol):
    """Base protocol for loader types that can search parameters."""
    def search_params(
            self, key: str, 
            *, 
            file: Optional[Union[str, List[str]]] = None, 
            scan_id: Optional[int] = None, 
            reco_id: Optional[int] = None
            ) -> Optional[dict]:
        ...


class StudyLoader(Study, BaseLoader):
    """Study with attached loader helpers."""
    subject: Parameters


class ScanLoader(Scan, BaseLoader):
    """Scan with attached loader helpers and conversion overrides."""

    image_info: Dict[int, Optional["ResolvedImage"]]
    affine_info: Dict[int, Optional["ResolvedAffine"]]
    _converter_hook: Optional[ConverterHook]
    _converter_hook_name: Optional[str]

    def get_fid(self, 
                buffer_start: Optional[int], 
                buffer_size: Optional[int], 
                *, 
                as_complex: bool) -> Optional[np.ndarray]:
        ...

    def get_dataobj(
            self, 
            reco_id: Optional[int] = None
            ) -> Optional[Union[Tuple["np.ndarray", ...], "np.ndarray"]]: 
        ...

    def get_affine(
            self, 
            reco_id: Optional[int] = None,
            *,
            space: AffineSpace = "subject_ras",
            override_subject_type: Optional[SubjectType],
            override_subject_pose: Optional[SubjectPose],
            decimals: Optional[int] = None
            ) -> Optional[Union[Tuple["np.ndarray", ...], "np.ndarray"]]:
        ...

    def get_nifti1image(
            self, 
            reco_id: Optional[int] = None, 
            *, 
            override_header: Optional[Union[dict, "Nifti1HeaderContents"]],
            space: AffineSpace = "subject_ras",
            override_subject_type: Optional[SubjectType],
            override_subject_pose: Optional[SubjectPose],
            flip_x: bool, 
            xyz_units: XYZUNIT, 
            t_units: TUNIT
            ) -> Optional[Union[Tuple["Nifti1Image", ...], "Nifti1Image"]]:
        ...

    def convert(
            self,
            reco_id: Optional[int] = None,
            *,
            format: Literal["nifti", "nifti1"],
            override_header: Optional[Union[dict, "Nifti1HeaderContents"]],
            space: AffineSpace = "subject_ras",
            override_subject_type: Optional[SubjectType],
            override_subject_pose: Optional[SubjectPose],
            flip_x: bool,
            xyz_units: XYZUNIT,
            t_units: TUNIT,
            hook_args_by_name: Optional[Mapping[str, Mapping[str, Any]]] = None,
            ) -> Optional[Union[Tuple["Nifti1Image", ...], "Nifti1Image"]]:
        ...

    def get_metadata(
            self, 
            reco_id: Optional[int] = None,
            spec: Optional[Union[Mapping[str, Any], str, "Path"]] = None,
            context_map: Optional[Union[str, "Path"]] = None,
            return_spec: bool = False,
            ) -> Optional[Union[dict, Tuple[Optional[dict], Optional[dict]]]]:
        ...


class RecoLoader(Reco, BaseLoader):
    """Reco with attached loader helpers."""
    ...


ConverterHook: TypeAlias = Mapping[str, Union[GetDataobjType[Any], GetAffineType, GetNifti1ImageType, ConvertType]]
"""Mapping of converter hook keys to override callables."""


__all__ = [
    'GetDataobjType',
    'GetAffineType',
    'GetNifti1ImageType',
    'ConvertType',
    'ConverterHook',
    'StudyLoader',
    'ScanLoader',
    'RecoLoader',
]

def __dir__() -> List[str]:
    return sorted(__all__)
