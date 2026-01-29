"""Typing helpers for app-level loader interfaces.

Last updated: 2025-12-30
"""

from __future__ import annotations

from typing import Any, Union, Tuple, Dict, Optional, Protocol, Literal, Mapping, List, TYPE_CHECKING, runtime_checkable
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
from ...resolver.affine import SubjectType, SubjectPose
import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from pathlib import Path
    from ...core.parameters import Parameters
    from ...resolver.image import ResolvedImage
    from ...resolver.affine import ResolvedAffine
    from ...resolver.nifti import Nifti1HeaderContents, XYZUNIT, TUNIT


InfoScope: TypeAlias = Literal['full', 'study', 'scan']
Dataobjs = Optional[Union[NDArray, Tuple[NDArray, ...]]]
Affines = Optional[Union[NDArray, Tuple[NDArray, ...]]]
AffineSpace: TypeAlias = Literal["raw", "scanner", "subject_ras"]
ConvertedObj = Optional[Union["ToFilename", Tuple["ToFilename", ...]]]
Metadata = Optional[Union[Dict, Tuple[Optional[Dict], ...]]]
HookArgs = Optional[Mapping[str, Mapping[str, Any]]]


P = ParamSpec("P")


@runtime_checkable
class GetDataobjType(Protocol[P]):
    """Callable signature for get_dataobj overrides."""
    def __call__(
        self,
        scan: "Scan",
        reco_id: Optional[int],
        cycle_index: Optional[int],
        cycle_count: Optional[int],
        *args: P.args,
        **kwargs: P.kwargs
    ) -> Dataobjs:
        ...


@runtime_checkable
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
    ) -> Affines:
        ...


@runtime_checkable
class ConvertType(Protocol):
    """Callable signature for convert overrides."""
    def __call__(
        self,
        scan: "Scan",
        dataobj: Union[Tuple["np.ndarray", ...], "np.ndarray"],
        affine: Union[Tuple["np.ndarray", ...], "np.ndarray"],
        **kwargs: Any,
    ) -> ConvertedObj:
        ...

class ToFilename(Protocol):
    """Result object that can be written to disk."""
    def to_filename(self, filename: Union[str, "Path"], *args: Any, **kwargs: Any) -> Any:
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
    converter_func: Optional[ConvertType]
    _converter_hook: Optional[ConverterHook]
    _converter_hook_name: Optional[str]
    _hook_resolved: bool = False
    
    
    def get_fid(self, 
                buffer_start: Optional[int], 
                buffer_size: Optional[int], 
                *, 
                as_complex: bool) -> Optional[np.ndarray]:
        ...

    def get_dataobj(
            self, 
            reco_id: Optional[int] = None,
            *,
            cycle_index: Optional[int] = None,
            cycle_count: Optional[int] = None,
            **kwargs: Any
            ) -> Dataobjs: 
        ...

    def get_affine(
            self, 
            reco_id: Optional[int] = None,
            *,
            space: AffineSpace = "subject_ras",
            override_subject_type: Optional[SubjectType],
            override_subject_pose: Optional[SubjectPose],
            decimals: Optional[int] = None,
            **kwargs: Any,
            ) -> Affines:
        ...

    def get_nifti1image(
            self,
            reco_id: int, 
            dataobjs: Tuple["np.ndarray", ...],
            affines: Tuple["np.ndarray", ...],
            *, 
            override_header: Optional[Union[dict, "Nifti1HeaderContents"]],
            xyz_units: XYZUNIT, 
            t_units: TUNIT
            ) -> ConvertedObj:
        ...

    def convert(
            self,
            reco_id: Optional[int] = None,
            *,
            space: AffineSpace = "subject_ras",
            override_header: Optional[Union[dict, "Nifti1HeaderContents"]],
            override_subject_type: Optional[SubjectType],
            override_subject_pose: Optional[SubjectPose],
            flatten_fg: bool,
            xyz_units: XYZUNIT,
            t_units: TUNIT,
            hook_args_by_name: HookArgs = None,
            **kwargs: Any,
            ) -> ConvertedObj:
        ...

    def get_metadata(
            self, 
            reco_id: Optional[int] = None,
            spec: Optional[Union[Mapping[str, Any], str, "Path"]] = None,
            context_map: Optional[Union[str, "Path"]] = None,
            return_spec: bool = False,
            ) -> Metadata:
        ...


class RecoLoader(Reco, BaseLoader):
    """Reco with attached loader helpers."""
    ...


ConverterHook: TypeAlias = Mapping[str, Union[GetDataobjType[Any], GetAffineType, ConvertType]]
"""Mapping of converter hook keys to override callables."""


__all__ = [
    'GetDataobjType',
    'GetAffineType',
    'ConvertType',
    'ToFilename',
    'ConverterHook',
    'StudyLoader',
    'ScanLoader',
    'RecoLoader',
    'SubjectType',
    'SubjectPose',
    'Affines',
    'Dataobjs',
    'Metadata',
    'ConvertedObj',
    'HookArgs',
    'AffineSpace',
]

def __dir__() -> List[str]:
    return sorted(__all__)
