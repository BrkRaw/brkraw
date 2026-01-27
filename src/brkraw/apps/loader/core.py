"""Loader utilities that attach conversion helpers to Bruker scans.

This module binds helper methods onto Scan/Reco objects so callers can fetch
reconstructed data, affines, NIfTI images, metadata, and parameter search
results with a simple API.
"""

from __future__ import annotations

from types import MethodType
import re
import logging
import sys
from functools import partial
from typing import (
    TYPE_CHECKING, cast, 
    Optional, Union, 
    Any, Iterable,
    Tuple, List, Mapping, Dict, Literal,
)
from pathlib import Path

from ...core import config as config_core
from ...core.config import resolve_root
from ...specs.pruner import prune_dataset_to_zip
from ...specs.rules import load_rules, select_rule_use
from ...dataclasses import Study
from .types import (
    StudyLoader, 
    ScanLoader, 
    RecoLoader,
)
from .formatter import format_info_tables

from . import info as info_resolver
from .helper import (
    make_dir,
    convert as _convert,
    get_affine as _get_affine,
    get_dataobj as _get_dataobj,
    get_metadata as _get_metadata,
    get_nifti1image as _get_nifti1image,
    resolve_reco_id as _resolve_reco_id,
    search_parameters as _search_parameters,
    apply_converter_hook as _apply_converter_hook,
    resolve_converter_hook as _resolve_converter_hook,
    resolve_data_and_affine as _resolve_data_and_affine,
)

if TYPE_CHECKING:
    import numpy as np
    from pathlib import Path
    from .types import (
        XYZUNIT, 
        TUNIT, 
        SubjectType, 
        SubjectPose, 
        InfoScope, 
        AffineSpace,
        Dataobjs,
        Affines,
        ConvertedObj,
        Metadata,
    )
    from ...resolver.nifti import Nifti1HeaderContents
    
logger = logging.getLogger(__name__)


class BrukerLoader:
    """High-level entrypoint that resolves scans and exposes handy accessors."""

    def __init__(self, 
                 path: Union[str, Path],
                 disable_hook: bool = False,
                 affine_decimals: Optional[int] = None):
        """
        Create a loader for a Bruker study rooted at `path`.

        This resolves image/affine metadata for each available scan and binds
        convenience methods (`get_dataobj`, `get_affine`) directly onto scan
        instances for downstream use.

        Args:
            path: Path to the study root.
            affine_decimals: Decimal rounding applied to resolved affines.
        """
        self._study: Union["Study", "StudyLoader"] = Study.from_path(path)
        if affine_decimals is None:
            affine_decimals = config_core.float_decimals(root=resolve_root(None))
        self._base = resolve_root(None)
        self._scans = {}
        self._affine_decimals = affine_decimals
        self._sw_version: Optional[str] = self._parse_sw_version()
        self._hook_disabled = disable_hook
        self._attach_helpers()

    def _parse_sw_version(self) -> Optional[str]:
        """Resolve Paravision version from subject header or visu_pars."""
        def _clean(value: object) -> Optional[str]:
            if value is None:
                return None
            text = str(value).strip()
            if text.startswith("<") and text.endswith(">"):
                text = text[1:-1]
            return text.strip()

        def _parse_title(text: str) -> Optional[str]:
            if not text:
                return None
            if text == "Parameter List":
                return "5.1"
            match = re.search(r"ParaVision\s+(\d+\.\d+\.\d+)", text)
            if match:
                return match.group(1)
            match = re.search(r"ParaVision\s+360\s+V(\d+)\.(\d+)", text)
            if match:
                return f"360.{match.group(1)}.{match.group(2)}"
            return None

        def _parse_visu(text: str) -> Optional[str]:
            if not text:
                return None
            match = re.search(r"(\d+\.\d+\.\d+)", text)
            if match:
                return match.group(1)
            return None

        study = self._study
        try:
            if getattr(study, "has_subject", False):
                subject = getattr(study, "subject", None)
                title = getattr(subject, "header", {}).get("TITLE")
                cleaned = _clean(title)
                parsed = _parse_title(cleaned or "")
                if parsed:
                    return parsed
        except Exception:
            pass

        try:
            scan = next(iter(study.avail.values()))
            reco = next(iter(scan.avail.values()))
            from ...core.parameters import Parameters

            visu_pars = cast(Parameters, reco.visu_pars)
            value = None
            try:
                value = visu_pars["VisuCoreVersion"]
            except Exception:
                value = None
            if value is None:
                try:
                    value = visu_pars["VisuCreatorVersion"]
                except Exception:
                    value = None
            cleaned = _clean(value)
            parsed = _parse_visu(cleaned or "")
            return parsed
        except Exception:
            return None

    def _attach_helpers(self):
        """Resolve per-scan metadata and bind helper methods."""
        logger.debug("Attaching helpers to study %s", getattr(self._study.fs, "root", "?"))
        self._study = cast(StudyLoader, self._study)
        self._study.search_params = MethodType(_search_parameters, self._study)

        for lazy_scan in self._study.avail.values():
            scan = lazy_scan.materialize()
            _resolve_data_and_affine(
                scan, 
                affine_decimals=self._affine_decimals
                )
            scan = cast(ScanLoader, lazy_scan.materialize())
            self.reset_converter(scan)
            scan.get_metadata = MethodType(_get_metadata, scan)
            scan.search_params = MethodType(_search_parameters, scan)
            scan._hook_resolved = False

            for reco in scan.avail.values():
                reco = cast(RecoLoader, reco)
                reco.search_params = MethodType(_search_parameters, reco)
    
    def _prep_scan(self, scan_id: int, reco_id: Optional[int] = None, **kwargs: Any) -> ScanLoader:
        scan = self.get_scan(scan_id)

        enable_hook = kwargs.get("enable_hook") # force enable
        if enable_hook is not None:
            del kwargs["enable_hook"]
        else:
            enable_hook = False

        hook_is_enabled = enable_hook or not self._hook_disabled 

        if hook_is_enabled:
            if enable_hook:
                logger.debug("hook enabled by optional argument for get_dataobj()")
            if scan._hook_resolved is False:  # prevent multiple execution
                _resolve_converter_hook(scan, self._base, affine_decimals=self._affine_decimals)

        logger.debug(
            "scan=%s reco=%s hook_enabled=%s hook=%s",
            scan_id,
            reco_id,
            hook_is_enabled,
            getattr(scan, "_converter_hook_name", None),
        )
        return scan

    def search_params(self, key: str, 
                      *, 
                      file: Optional[Union[str, List[str]]] = None, 
                      scan_id: Optional[int] = None, 
                      reco_id: Optional[int] = None):
        """Search parameter files for keys on study/scan/reco objects.

        Args:
            key: Parameter key to search for.
            file: Filename or list of filenames to search.
            scan_id: Scan id (required when searching from Study).
            reco_id: Reco id (optional; flattens results for that reco).

        Returns:
            Mapping of filename to found values, or None if no hits.
        """
        self._study = cast(StudyLoader, self._study)
        return self._study.search_params(key, file=file, scan_id=scan_id, reco_id=reco_id)

    def reset_converter(self, scan: ScanLoader) -> None:
        """Restore default conversion methods for a scan.

        Args:
            scan_id: Scan identifier.
        """
        logger.debug("Initializing converter for scan %s", getattr(scan, "scan_id", "?"))
        scan.get_dataobj = MethodType(_get_dataobj, scan)
        scan.get_affine = MethodType(
            partial(_get_affine, decimals=self._affine_decimals),
            scan,
        )
        scan.get_nifti1image = MethodType(_get_nifti1image, scan)
        scan.convert = MethodType(_convert, scan)
        scan._converter_hook = None
        scan._converter_hook_name = None
        scan.converter_func = None

    def get_scan(self, scan_id: int) -> "ScanLoader":
        """Return scan by id.

        Args:
            scan_id: Scan identifier.

        Returns:
            Scan loader instance.
        """
        scan = cast(ScanLoader, self._study.get_scan(scan_id))
        return scan

    def get_fid(
        self,
        scan_id: int,
        buffer_start: Optional[int] = None,
        buffer_size: Optional[int] = None,
        *,
        as_complex: bool = True,
    ) -> Optional["np.ndarray"]:
        """Return FID/rawdata for a scan.

        Args:
            scan_id: Scan identifier.
            buffer_start: Optional byte offset to start reading.
            buffer_size: Optional number of bytes to read.
            as_complex: If True, return complex samples (default: True).

        Returns:
            NumPy array of samples.
        """
        scan = self.get_scan(scan_id)
        if not hasattr(scan, 'get_fid'):
            return None
        return scan.get_fid(
            buffer_start=buffer_start, 
            buffer_size=buffer_size, 
            as_complex=as_complex
        )

    def get_dataobj(
            self, 
            scan_id: int, 
            reco_id: Optional[int] = None, 
            **kwargs: Any
    ) -> Dataobjs:
        """Return reconstructed data for a scan/reco via attached helper.

        Args:
            scan_id: Scan identifier.
            reco_id: Reco identifier (defaults to the first available).

        Returns:
            Single ndarray when one slice pack exists; otherwise a tuple.
        """
        scan = self._prep_scan(scan_id, reco_id, **kwargs)
        return scan.get_dataobj(reco_id, **kwargs)

    def get_affine(
            self, 
            scan_id: int, 
            reco_id: Optional[int] = None,
            *,
            space: AffineSpace = 'subject_ras',
            override_subject_type: Optional[SubjectType] = None,
            override_subject_pose: Optional[SubjectPose] = None,
            decimals: Optional[int] = None,
            **kwargs: Any
    ) -> Affines:
        """Return affine(s) for a scan/reco via attached helper.

        Args:
            scan_id: Scan identifier.
            reco_id: Reco identifier (defaults to the first available).
            space: Output affine space ("raw", "scanner", "subject_ras").
            override_subject_type: Subject type override for subject view.
            override_subject_pose: Subject pose override for subject view.
            decimals: Optional decimal rounding applied to returned affines.

        Returns:
            Single affine matrix when one slice pack exists; otherwise a tuple.
        """
        scan = self._prep_scan(scan_id, reco_id, **kwargs)
        decimals = decimals or self._affine_decimals
        return scan.get_affine(reco_id, 
                               space=space, 
                               override_subject_pose=override_subject_pose, 
                               override_subject_type=override_subject_type,
                               decimals=decimals, **kwargs)
    
    def get_nifti1image(
            self, scan_id: int, reco_id: Optional[int] = None,
                        *, 
                        space: AffineSpace = 'subject_ras',
                        override_header: Optional[Nifti1HeaderContents] = None,
                        override_subject_type: Optional[SubjectType] = None,
                        override_subject_pose: Optional[SubjectPose] = None,
                        flatten_fg: bool = False,
                        xyz_units: XYZUNIT = 'mm', 
                        t_units: TUNIT = 'sec'
    ) -> ConvertedObj:
        """Return NIfTI image(s) for a scan/reco via attached helper.

        Args:
            scan_id: Scan identifier.
            reco_id: Reco identifier (defaults to the first available).
            space: Output affine space ("raw", "scanner", "subject_ras").
            override_header: Optional header values to apply.
            override_subject_type: Subject type override for subject view.
            override_subject_pose: Subject pose override for subject view.
            xyz_units: Spatial units for NIfTI header.
            t_units: Temporal units for NIfTI header.

        Returns:
            Single NIfTI image when one slice pack exists; otherwise a tuple.
        """
        scan = self.get_scan(scan_id)
        dataobj = scan.get_dataobj(reco_id)
        affine = scan.get_affine(reco_id, 
                                 space=space, 
                                 decimals=self._affine_decimals,
                                 override_subject_pose=override_subject_pose,
                                 override_subject_type=override_subject_type,
                                 flatten_fg=flatten_fg,
                                 xyz_units=xyz_units,
                                 t_units=t_units)
        resolved_reco_id = _resolve_reco_id(scan, reco_id)
        if resolved_reco_id is None:
            return None
        return scan.get_nifti1image(
            resolved_reco_id,
            cast(Tuple[np.ndarray, ...], dataobj),
            cast(Tuple[np.ndarray, ...], affine),
            override_header=override_header,
            xyz_units=xyz_units,
            t_units=t_units,
        )

    def convert(
        self,
        scan_id: int,
        reco_id: Optional[int] = None,
        *,
        space: AffineSpace = 'subject_ras',
        override_header: Optional[Nifti1HeaderContents] = None,
        override_subject_type: Optional[SubjectType] = None,
        override_subject_pose: Optional[SubjectPose] = None,
        flatten_fg: bool = False,
        hook_args_by_name: Optional[Mapping[str, Mapping[str, Any]]] = None,
        **kwargs: Any,
    ) -> ConvertedObj:
        """Convert a scan/reco to output object(s) supporting to_filename()."""
        scan = self._prep_scan(scan_id, reco_id, **kwargs)
        return scan.convert(
            reco_id,
            space=space,
            override_header=override_header,
            override_subject_type=override_subject_type,
            override_subject_pose=override_subject_pose,
            flatten_fg=flatten_fg,
            hook_args_by_name=hook_args_by_name,
            **kwargs,
        )

    def get_metadata(
        self,
        scan_id: int,
        reco_id: Optional[int] = None,
        spec: Optional[Union[Mapping[str, Any], str, Path]] = None,
        context_map: Optional[Union[str, Path]] = None,
        return_spec: bool = False,
    ) -> Metadata:
        """Return metadata for a scan/reco.

        Args:
            scan_id: Scan identifier.
            reco_id: Reco identifier (defaults to the first available).
            spec: Optional spec mapping or spec file path.
            context_map: Optional context map override.
            return_spec: If True, return spec info alongside metadata.

        Returns:
            Mapping of metadata fields, or None when no spec matches. When
            return_spec is True, returns (metadata, spec_info).
        """
        scan = self.get_scan(scan_id)
        return scan.get_metadata(
            reco_id=reco_id,
            spec=spec,
            context_map=context_map,
            return_spec=return_spec,
        )

    def prune_to_zip(
        self,
        dest: Union[str, Path],
        files: Iterable[str],
        *,
        mode: Literal["keep", "drop"] = "keep",
        update_params: Optional[Mapping[str, Mapping[str, Optional[str]]]] = None,
        add_root: bool = True,
        root_name: Optional[str] = None,
    ) -> "BrukerLoader":
        """Create a pruned dataset zip and return a loader for it.

        Args:
            dest: Destination zip path.
            files: Filenames or relative paths used by the selection mode.
            mode: "keep" to include only matching files, "drop" to exclude them.
            update_params: Mapping or YAML path of {filename: {key: value}} JCAMP edits.
            add_root: Whether to include a top-level root directory in the zip.
            root_name: Override the root directory name when add_root is True.

        Returns:
            Loader bound to the newly created pruned zip.
        """
        source = self._study.fs.root
        out_path = prune_dataset_to_zip(
            source,
            dest,
            files=files,
            mode=mode,
            update_params=update_params,
            add_root=add_root,
            root_name=root_name,
        )
        return BrukerLoader(out_path, affine_decimals=self._affine_decimals)

    @property
    def avail(self) -> Mapping[int, "ScanLoader"]:
        """Available scans keyed by scan id."""
        if len(self._scans) != len(self._study.avail):
            self._scans = {scan_id: cast(ScanLoader, scan.materialize()) for scan_id, scan in self._study.avail.items()}
        return self._scans
    
    @property
    def subject(self) -> Optional[Dict[str, Any]]:
        """Parsed study/subject info resolved from subject metadata.

        Returns:
            Mapping with Study/Subject entries, or None if resolution fails.
        """
        try:
            return info_resolver.study(self)
        except Exception:
            return None

    @property
    def sw_version(self) -> Optional[str]:
        """Resolved Paravision version string, if available."""
        return self._sw_version

    def info(
        self,
        scope: InfoScope = 'full',
        *,
        scan_id: Optional[Union[int, List[int]]] = None,
        as_dict: bool = False,
        scan_transpose: bool = True,
        float_decimals: Optional[int] = None,
        width: Optional[int] = None,
        show_reco: bool = True,
    ):
        """Return study/scan summaries as a dict or formatted table.

        Args:
            scope: "full", "study", or "scan".
            scan_id: Optional scan id or list of scan ids to include.
            as_dict: If True, return a mapping; otherwise print a table and return None.
            scan_transpose: If True, render scan fields in a transposed layout.
            float_decimals: Decimal precision for floats (defaults to config).
            width: Output table width (defaults to config).
            show_reco: If False, omit reco entries from scan info.

        Returns:
            Mapping of info data, or None when formatted output is printed.
        """
        rules = {}
        base = resolve_root(None)
        scan_info: Dict[int, Any] = {}
        if width is None:
            width = config_core.output_width(root=base)
        if float_decimals is None:
            float_decimals = config_core.float_decimals(root=base)
        try:
            rules = load_rules(root=base, validate=False)
        except Exception:
            rules = {}

        if scope in ['full', 'scan']:
            if scan_id is None:
                scan_ids = list(self.avail.keys())
            elif isinstance(scan_id, list):
                scan_ids = scan_id
            else:
                scan_ids = [scan_id]
            for sid in scan_ids:
                scan = cast(ScanLoader, self.avail[sid])
                spec_path = None
                if rules:
                    try:
                        spec_path = select_rule_use(
                            scan,
                            rules.get("info_spec", []),
                            base=base,
                            resolve_paths=True,
                        )
                    except Exception:
                        spec_path = None

                if isinstance(spec_path, Path) and spec_path.exists():
                    scan_info[sid] = info_resolver.scan(scan, spec_source=spec_path)
                else:
                    scan_info[sid] = info_resolver.scan(scan)

                if not show_reco and isinstance(scan_info[sid], dict):
                    scan_info[sid].pop("Reco(s)", None)

            if scope == 'scan':
                if not as_dict:
                    config_core.configure_logging(root=base, stream=sys.stdout)
                    text = format_info_tables(
                        {"Scan(s)": scan_info},
                        width=width,
                        scan_indent=1,
                        reco_indent=1,
                        scan_transpose=scan_transpose,
                        float_decimals=float_decimals,
                    )
                    logger.info("%s", text)
                    return None
                return scan_info
        
        study_info = dict(self.subject) if self.subject else {}
        if self.sw_version:
            study_block = dict(study_info.get("Study", {}))
            study_block = {"Software": f"Paravision v{self.sw_version}", **study_block}
            study_info["Study"] = study_block
        
        if scope == 'study':
            if not as_dict:
                config_core.configure_logging(root=base, stream=sys.stdout)
                text = format_info_tables(
                    study_info,
                    width=width,
                    float_decimals=float_decimals,
                )
                logger.info("%s", text)
                return None
            return study_info
        
        study_info['Scan(s)'] = scan_info
        if not as_dict:
            config_core.configure_logging(root=base, stream=sys.stdout)
            text = format_info_tables(
                study_info,
                width=width,
                scan_indent=1,
                reco_indent=1,
                scan_transpose=scan_transpose,
                float_decimals=float_decimals,
            )
            logger.info("%s", text)
            return None
        return study_info

__all__ = [
    "BrukerLoader",
]

__dir__ = make_dir(__all__)
