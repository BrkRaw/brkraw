from __future__ import annotations

"""Convert a scan/reco to NIfTI with optional metadata sidecar.

Last updated: 2026-01-06
"""

import argparse
import copy
import inspect
import json
import logging
import os
import re
import warnings
from pathlib import Path
from typing import Any, Mapping, Optional, Dict, List, Tuple, Sequence, Union, cast, get_args

import sys

import numpy as np
from brkraw.apps.loader.helper import _resolve_hook_kwargs
from brkraw.cli import cache_check
from brkraw.cli.utils import add_root_argument, load, parse_scan_ids
from brkraw.cli.hook_args import load_hook_args_yaml, merge_hook_args
from brkraw.core import config as config_core
from brkraw.core import layout as layout_core
from brkraw.resolver import nifti as nifti_resolver
from brkraw.specs import context_map as context_map_core
from brkraw.specs.context_map import output as cm_output
from brkraw.resolver.nifti import XYZUNIT, TUNIT, Nifti1HeaderContents
from brkraw.resolver.affine import SubjectPose, SubjectType
from brkraw.apps.loader.types import AffineSpace


logger = logging.getLogger(__name__)

_INVALID_CHARS = re.compile(r"[^A-Za-z0-9._-]+")

_COUNTER_TAG = re.compile(r"\{(?:Counter|counter)\}")


def _convert_scan(loader: Any, scan_id: Any, reco_id: Any, convert_kwargs: Mapping[str, Any],
                  selection: Mapping[str, Any]) -> Any:
    """``loader.convert``, with one confirmed retry when a hook stops for memory (WI-0074).

    Contract with converter hooks: a hook that refuses to start because its
    memory estimate is above its limit raises a ``MemoryError`` whose
    ``retry_kwargs`` attribute is a dict of hook arguments that would pass (for
    example ``{"max_memory_gb": 7.5}``). In a terminal (stdin and stderr are a
    terminal) the CLI shows the message and asks "Proceed anyway with ...?
    [y/N]"; on ``y``/``yes`` it converts once more with those arguments added to
    that hook's arguments. Otherwise (no terminal, another answer, no
    ``retry_kwargs``, or a second stop) the error goes to the caller as before.
    """
    try:
        return loader.convert(scan_id, reco_id=reco_id, **convert_kwargs, **selection)
    except MemoryError as exc:
        retry = getattr(exc, "retry_kwargs", None)
        if not isinstance(retry, Mapping) or not retry:
            raise
        try:
            scan = loader.get_scan(scan_id)
        except Exception:  # noqa: BLE001 - keep the hook's own error (wi-0074-choi-1)
            raise exc from None
        hook_name = getattr(scan, "_converter_hook_name", None)
        if not isinstance(hook_name, str) or not hook_name or not cache_check.is_interactive():
            raise
        sys.stderr.write(f"{exc}\n")
        text = ", ".join(f"{key}={value}" for key, value in retry.items())
        if not cache_check.ask_yes(f"Proceed anyway with {text} for scan {scan_id}? [y/N]: "):
            raise
        by_name = dict(convert_kwargs.get("hook_args_by_name") or {})
        current = _resolve_hook_kwargs(scan, by_name)   # the arguments the hook got, under any alias
        by_name[hook_name] = {**current, **dict(retry)}
        logger.info("Retrying scan %s with %s.", scan_id, text)
        retry_kwargs = dict(convert_kwargs, hook_args_by_name=by_name)
        return loader.convert(scan_id, reco_id=reco_id, **retry_kwargs, **selection)


def cmd_convert(args: argparse.Namespace) -> int:
    """Entry point of `brkraw convert`: one dataset, or every dataset in a folder with --batch."""
    if getattr(args, "batch", False):
        return _convert_batch(args)
    return _convert_one(args)


def _convert_one(args: argparse.Namespace) -> int:
    """Convert one dataset (scan/reco) to NIfTI with optional metadata sidecars.

    Args:
        args: Parsed CLI arguments for the convert subcommand.

    Returns:
        Exit status code (0 on success, non-zero on failure).
    """
    # resolve core paths
    if args.path is None:
        args.path = os.environ.get("BRKRAW_PATH")
    if args.path is None:
        args.parser.print_help()
        return 2
    if not Path(args.path).exists():
        logger.error("Path not found: %s", args.path)
        return 2

    if args.output is None:
        args.output = os.environ.get("BRKRAW_CONVERT_OUTPUT")
    if args.prefix is None:
        args.prefix = os.environ.get("BRKRAW_CONVERT_PREFIX")

    # resolve scan/reco ids: -s takes several (one rule, cli.utils.parse_scan_ids),
    # so the session variables give every id they hold
    if args.scan_id is not None:
        try:
            args.scan_id = parse_scan_ids(args.scan_id)
        except ValueError as exc:
            logger.error("-s/--scan-id: %s", exc)
            return 2
    else:
        for env_key in ("BRKRAW_SCAN_ID", "BRKRAW_CONVERT_SCAN_ID"):
            value = os.environ.get(env_key)
            if not value or not value.strip():
                continue
            try:
                args.scan_id = parse_scan_ids([value])
            except ValueError as exc:
                logger.error("%s: %s", env_key, exc)
                return 2
            break
    for env_key in ("BRKRAW_RECO_ID", "BRKRAW_CONVERT_RECO_ID"):
        if args.reco_id is not None:
            break
        value = os.environ.get(env_key)
        if not value:
            continue
        try:
            args.reco_id = int(value)
        except ValueError:
            logger.error("Invalid %s: %s", env_key, value)
            return 2

    # resolve flags + spaces
    if not args.sidecar:
        args.sidecar = _env_flag("BRKRAW_CONVERT_SIDECAR")
    if args.no_convert and not args.sidecar:
        logger.error("--no-convert requires --sidecar.")
        return 2
    if not args.flatten_fg:
        args.flatten_fg = _env_flag("BRKRAW_CONVERT_FLATTEN_FG")

    # resolve cycle_index/cycle_count from env
    if args.cycle_index is None:
        value = os.environ.get("BRKRAW_CONVERT_CYCLE_INDEX")
        if value:
            try:
                args.cycle_index = int(value)
            except ValueError:
                logger.error("Invalid BRKRAW_CONVERT_CYCLE_INDEX: %s", value)
                return 2
    if args.cycle_count is None:
        value = os.environ.get("BRKRAW_CONVERT_CYCLE_COUNT")
        if value:
            try:
                args.cycle_count = int(value)
            except ValueError:
                logger.error("Invalid BRKRAW_CONVERT_CYCLE_COUNT: %s", value)
                return 2
    # if cycle_count is set but cycle_index is not, default cycle_index to 0
    if args.cycle_index is None and args.cycle_count is not None:
        args.cycle_index = 0

    # frame selection: --axis/--frames, or the legacy cycle options (BRK-0032 ①)
    try:
        frames_value = _parse_frames_option(getattr(args, "frames", None))
        axis_value = _parse_axis_option(getattr(args, "axis", None))
    except ValueError as exc:
        logger.error("%s", exc)
        return 2
    legacy_cycles = args.cycle_index is not None
    if legacy_cycles and (frames_value is not None or axis_value is not None):
        logger.error("Use --axis/--frames or the legacy --cycle-index/--cycle-count, not both.")
        return 2
    if axis_value is not None and frames_value is None:
        logger.error("--axis needs --frames (which frames of that axis to keep).")
        return 2
    if legacy_cycles:
        stop = "" if args.cycle_count is None else str(int(args.cycle_index) + int(args.cycle_count))
        logger.warning(
            "--cycle-index/--cycle-count are deprecated and will be removed in brkraw 0.7.0; "
            "use --axis cycle --frames %s:%s",
            args.cycle_index,
            stop,
        )
    default_selection: Dict[str, Any] = {}
    if frames_value is not None:
        default_selection = {"axis": axis_value, "frames": frames_value}
    elif legacy_cycles:
        default_selection = {"cycle_index": args.cycle_index, "cycle_count": args.cycle_count}

    if args.space is None:
        args.space = os.environ.get("BRKRAW_CONVERT_SPACE")
    if args.override_subject_type is None:
        args.override_subject_type = _coerce_choice(
            "BRKRAW_CONVERT_OVERRIDE_SUBJECT_TYPE",
            os.environ.get("BRKRAW_CONVERT_OVERRIDE_SUBJECT_TYPE"),
            get_args(SubjectType),
        )
    if args.override_subject_pose is None:
        args.override_subject_pose = _coerce_choice(
            "BRKRAW_CONVERT_OVERRIDE_SUBJECT_POSE",
            os.environ.get("BRKRAW_CONVERT_OVERRIDE_SUBJECT_POSE"),
            get_args(SubjectPose),
        )
    if args.xyz_units == "mm":
        args.xyz_units = _coerce_choice(
            "BRKRAW_CONVERT_XYZ_UNITS",
            os.environ.get("BRKRAW_CONVERT_XYZ_UNITS"),
            get_args(XYZUNIT),
            default=args.xyz_units,
        )
    if args.t_units == "sec":
        args.t_units = _coerce_choice(
            "BRKRAW_CONVERT_T_UNITS",
            os.environ.get("BRKRAW_CONVERT_T_UNITS"),
            get_args(TUNIT),
            default=args.t_units,
        )
    if args.space is None:
        args.space = "subject_ras"
    if args.header is None:
        args.header = os.environ.get("BRKRAW_CONVERT_HEADER")
    if args.compress is None:
        if "BRKRAW_CONVERT_COMPRESS" in os.environ:
            args.compress = _env_flag("BRKRAW_CONVERT_COMPRESS")
        else:
            args.compress = True

    output_is_file = False
    if args.output:
        out_path = Path(args.output)
        output_is_file = out_path.suffix in {".nii", ".gz"} or out_path.name.endswith(".nii.gz")
        if output_is_file and args.prefix:
            logger.error("Cannot use --prefix when --output is a file path.")
            return 2

    try:
        render_layout_supports_counter = "counter" in inspect.signature(layout_core.render_layout).parameters
    except (TypeError, ValueError):
        render_layout_supports_counter = True
    try:
        slicepack_supports_counter = (
            "counter" in inspect.signature(layout_core.render_slicepack_suffixes).parameters
        )
    except (TypeError, ValueError):
        slicepack_supports_counter = True

    hook_args_by_name: Dict[str, Dict[str, Any]] = {}
    hook_args_yaml_sources: List[str] = []
    for env_key in ("BRKRAW_CONVERT_HOOK_ARGS_YAML", "BRKRAW_HOOK_ARGS_YAML"):
        value = os.environ.get(env_key)
        if value:
            hook_args_yaml_sources.extend([part.strip() for part in value.split(",") if part.strip()])
    hook_args_yaml_sources.extend(args.hook_args_yaml or [])
    if hook_args_yaml_sources:
        try:
            hook_args_by_name = load_hook_args_yaml(hook_args_yaml_sources)
        except ValueError as exc:
            logger.error("%s", exc)
            return 2

    try:
        hook_args_cli = _parse_hook_args(args.hook_arg or [])
    except ValueError as exc:
        logger.error("%s", exc)
        return 2
    hook_args_by_name = merge_hook_args(hook_args_by_name, hook_args_cli)

    loader = load(args.path, prefix="Loading")
    logger.debug("Dataset: %s loaded", args.path)
    try:
        override_header = nifti_resolver.load_header_overrides(args.header)
    except ValueError:
        return 2
    
    batch_all = args.scan_id is None
    # two or more scans (every scan, or -s 3 4 ...): the output is a folder
    several = batch_all or len(args.scan_id) > 1
    if several and args.output and not output_is_file and not args.output.endswith(os.sep):
        args.output = f"{args.output}{os.sep}"
    if several and output_is_file:
        if batch_all:
            logger.error("When omitting --scan-id, --output must be a folder.")
        else:
            logger.error("With two or more scan ids, --output must be a folder.")
        return 2

    scan_ids = list(loader.avail.keys()) if batch_all else list(args.scan_id)
    if not scan_ids:
        logger.error("No scans available for conversion.")
        return 2
    if not batch_all:
        # scans named with -s: check them all before anything is written (BRK-0040 2)
        unknown = [sid for sid in scan_ids if sid not in loader.avail]
        if unknown:
            logger.error(
                "No scan %s in this dataset (available: %s); nothing was written.",
                ", ".join(str(s) for s in unknown),
                ", ".join(str(s) for s in loader.avail) or "none",
            )
            return 2
        if args.reco_id is not None:
            lacking = []
            for sid in scan_ids:
                scan = loader.get_scan(sid)
                recos = list(scan.avail.keys())
                if not recos and getattr(scan, "_converter_hook", None):
                    continue  # a converter hook without recos decides for itself
                if args.reco_id not in recos:
                    lacking.append(f"scan {sid} (recos: {', '.join(str(r) for r in recos) or 'none'})")
            if lacking:
                logger.error(
                    "reco %s is missing in %s; nothing was written.",
                    args.reco_id,
                    "; ".join(lacking),
                )
                return 2
    elif args.reco_id is not None:
        # every scan with -r: skip the scans without that reco and say which (BRK-0040)
        keep = []
        skipped = []
        for sid in scan_ids:
            scan = loader.get_scan(sid)
            recos = list(scan.avail.keys())
            if args.reco_id in recos or (not recos and getattr(scan, "_converter_hook", None)):
                keep.append(sid)
            else:
                skipped.append(sid)
        if not keep:
            logger.error("reco %s is in no scan of this dataset; nothing was written.", args.reco_id)
            return 2
        if skipped:
            logger.warning(
                "reco %s is missing in scan %s; skipped (name scans with -s to stop instead).",
                args.reco_id,
                ", ".join(str(s) for s in skipped),
            )
        scan_ids = keep

    root = None
    layout_entries = config_core.layout_entries(root=root)
    layout_template = config_core.layout_template(root=root)
    slicepack_suffix = config_core.output_slicepack_suffix(root=root)

    # context map v3: same-name file next to the dataset, -M FILE, or none
    map_data: Optional[Dict[str, Any]] = None
    try:
        if getattr(args, "no_context_map", False):
            map_data = None
        elif args.context_map:
            map_data = context_map_core.load_context_map(args.context_map)
        else:
            map_data = context_map_core.resolve_context_map(args.path)
    except (context_map_core.ContextMapError, OSError) as exc:
        logger.error("Context map: %s", exc)
        return 2
    map_meta: Dict[str, Any] = dict((map_data or {}).get("__meta__") or {})
    map_template = map_meta.get("layout_template") if map_data else None
    if map_template and args.prefix:
        logger.info("--prefix given: the context map's layout_template is not used for file names.")
        map_template = None
    convert_kwargs: Dict[str, Any] = {
        "space": cast(AffineSpace, args.space),
        "override_header": cast(Nifti1HeaderContents, override_header) if override_header else None,
        "override_subject_type": cast(Optional[SubjectType], args.override_subject_type),
        "override_subject_pose": cast(Optional[SubjectPose], args.override_subject_pose),
        "flatten_fg": args.flatten_fg,
        "xyz_units": cast(XYZUNIT, args.xyz_units),
        "t_units": cast(TUNIT, args.t_units),
        "hook_args_by_name": hook_args_by_name,
    }
    if map_data is not None and map_template:
        if output_is_file:
            logger.error("With a context map layout_template, --output must be a folder.")
            return 2
        return _convert_with_map_template(
            args,
            loader,
            scan_ids,
            map_data,
            map_template,
            map_meta,
            convert_kwargs=convert_kwargs,
            default_selection=default_selection,
        )
    namespace_names = [k for k in (map_data or {}) if k not in context_map_core.RESERVED and k != "__meta__"]

    total_written = 0
    reserved_paths: set = set()
    for scan_id in scan_ids:
        if scan_id is None:
            continue
        scan = loader.get_scan(scan_id)
        logger.debug("Processing scan %s.", scan_id)
        reco_ids = [args.reco_id] if args.reco_id is not None else list(scan.avail.keys())
        logger.debug("Recos: %s", reco_ids or "None")
        if not reco_ids:
            if getattr(scan, "_converter_hook", None):
                reco_ids = [None]
            else:
                continue
        for reco_id in reco_ids:
            # context map without its own layout_template: convert/split/sidecar and
            # namespace values for the config layout's tags
            plan: Optional[context_map_core.ScanPlan] = None
            jobs: List[Tuple[Optional[int], Optional[Mapping[str, Any]]]] = [(None, None)]
            if map_data is not None:
                try:
                    plan_info, _ = layout_core.load_layout_info_parts(loader, scan_id, reco_id=reco_id)
                    meta_base = _metadata_for_rules(loader, scan_id, reco_id, strict=bool(args.sidecar))
                    plan = context_map_core.plan_scan(
                        plan_info, map_data, scan_id=scan_id, reco_id=reco_id, metadata=meta_base
                    )
                    if plan.convert and plan.split is not None:
                        _check_split(loader, scan_id, reco_id, plan.split, namespace_names)
                        jobs = [(k, part) for k, part in enumerate(plan.split, start=1)]
                except context_map_core.ContextMapError as exc:
                    logger.error("Context map, scan %s reco %s: %s", scan_id, reco_id, exc)
                    return 2
                if not plan.convert:
                    logger.info("Skipping scan %s reco %s (context map: convert false).", scan_id, reco_id)
                    continue

            for part_no, part in jobs:
                selection = _selection_for(part, default_selection)
                extra = _namespaces_for_part(plan, part) if plan is not None else None
                if args.no_convert:
                    nii_list: List[Any] = []
                    output_count = 1
                else:
                    try:
                        with warnings.catch_warnings():
                            # the CLI already logged the legacy-option notice
                            warnings.simplefilter("ignore", DeprecationWarning)
                            nii = _convert_scan(loader, scan_id, reco_id, convert_kwargs, selection)
                    except Exception as exc:
                        logger.error("Conversion failed for scan %s reco %s: %s", scan_id, reco_id, exc)
                        if not several and args.reco_id is not None:
                            return 2
                        continue
                    if nii is None:
                        if not several and args.reco_id is not None:
                            logger.error("No NIfTI output generated for scan %s reco %s.", scan_id, reco_id)
                            return 2
                        continue
                    nii_list = list(nii) if isinstance(nii, tuple) else [nii]
                    output_count = len(nii_list)

                slicepack_suffixes: Optional[List[str]] = None
                output_paths: Optional[List[Path]] = None
                uses_counter_tag = _uses_counter_tag(
                    layout_template=layout_template,
                    layout_entries=layout_entries,
                    prefix_template=args.prefix,
                )
                counter_enabled = bool(uses_counter_tag and render_layout_supports_counter)

                for counter in range(1, 1000):
                    layout_kwargs: Dict[str, Any] = {"counter": counter} if counter_enabled else {}
                    if extra:
                        layout_kwargs["extra"] = extra
                    try:
                        candidate_base_name = layout_core.render_layout(
                            loader,
                            scan_id,
                            layout_entries=layout_entries,
                            layout_template=layout_template,
                            reco_id=reco_id,
                            **layout_kwargs,
                        )
                    except Exception as exc:
                        logger.error("%s", exc)
                        return 2
                    if args.prefix:
                        candidate_base_name = layout_core.render_layout(
                            loader,
                            scan_id,
                            layout_entries=None,
                            layout_template=args.prefix,
                            reco_id=reco_id,
                            **layout_kwargs,
                        )
                    if several and args.prefix:
                        candidate_base_name = f"{candidate_base_name}_scan-{scan_id}"
                    if args.reco_id is None and len(reco_ids) > 1:
                        candidate_base_name = f"{candidate_base_name}_reco-{reco_id}"
                    candidate_base_name = _sanitize_filename(candidate_base_name)

                    if not counter_enabled and counter > 1:
                        candidate_base_name = f"{candidate_base_name}_{counter}"

                    slicepack_suffixes = None
                    if not args.no_convert and output_count > 1:
                        info = layout_core.load_layout_info(
                            loader,
                            scan_id,
                            reco_id=reco_id,
                        )
                        slicepack_suffixes = layout_core.render_slicepack_suffixes(
                            info,
                            count=len(nii_list),
                            template=slicepack_suffix,
                            **({"counter": counter} if slicepack_supports_counter and counter_enabled else {}),
                        )
                    output_paths = _resolve_output_paths(
                        args.output,
                        candidate_base_name,
                        count=output_count,
                        compress=bool(args.compress),
                        slicepack_suffix=slicepack_suffix,
                        slicepack_suffixes=slicepack_suffixes,
                    )
                    if output_paths is None:
                        return 2
                    if len(output_paths) != output_count:
                        logger.error("Output path count does not match NIfTI outputs.")
                        return 2
                    if _paths_collide(output_paths, reserved_paths):
                        continue
                    break
                else:
                    logger.error("Could not resolve unique output name after many attempts.")
                    return 2

                if output_paths is None:
                    logger.error("Output paths could not be resolved.")
                    return 2
                for path in output_paths:
                    reserved_paths.add(path)

                _ensure_output_dirs(output_paths)

                sidecar_meta = None
                if args.sidecar:
                    if plan is not None:
                        sidecar_meta = _sidecar_for_part(plan, part)
                    else:
                        sidecar_meta = loader.get_metadata(scan_id, reco_id=reco_id)

                if args.no_convert:
                    for path in output_paths:
                        _write_sidecar(path, sidecar_meta)
                        total_written += 1
                else:
                    for path, obj in zip(output_paths, nii_list):
                        obj.to_filename(str(path))
                        logger.info("Wrote NIfTI: %s", path)
                        total_written += 1
                        if args.sidecar:
                            _write_sidecar(path, sidecar_meta)
    if total_written == 0:
        if args.no_convert:
            logger.error("No sidecar outputs generated.")
        else:
            logger.error("No NIfTI outputs generated.")
        return 2
    return 0


# ---------------------------------------------------------------------------
# Frame selection and context map output (b1 bundle B5)
# ---------------------------------------------------------------------------


def _parse_frames_option(value: Optional[str]) -> Optional[Union[int, List[int], str]]:
    """--frames text: "2" -> 2, "2,0" -> [2, 0], "1:3" -> "1:3" (numpy rules)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        raise ValueError("--frames is empty.")
    if ":" in text:
        bits = text.split(":")
        if len(bits) not in (2, 3) or not all(re.fullmatch(r"\s*-?\d*\s*", b) for b in bits):
            raise ValueError(f"--frames {text!r}: use start:stop[:step].")
        return text
    if "," in text:
        items = [b.strip() for b in text.split(",")]
        if not all(re.fullmatch(r"-?\d+", b) for b in items):
            raise ValueError(f"--frames {text!r}: a list is integers separated by commas.")
        return [int(b) for b in items]
    if not re.fullmatch(r"-?\d+", text):
        raise ValueError(f"--frames {text!r}: use an integer, a list (2,0) or a slice (1:3).")
    return int(text)


def _parse_axis_option(value: Optional[str]) -> Optional[Union[int, str]]:
    """--axis text: a digit string is an axis number, anything else a frame-axis name."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        raise ValueError("--axis is empty.")
    return int(text) if text.isdecimal() else text


def _selection_for(part: Optional[Mapping[str, Any]], default: Mapping[str, Any]) -> Dict[str, Any]:
    """Frame selection kwargs for loader.convert: a split part wins over --axis/--frames."""
    if part is None:
        return dict(default)
    return {"axis": part.get("axis"), "frames": part["frames"]}


def _namespaces_for_part(
    plan: context_map_core.ScanPlan, part: Optional[Mapping[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """Namespace values of a scan with one split part's field overrides."""
    merged = copy.deepcopy(plan.namespaces)
    for key, value in (part or {}).items():
        if key in ("axis", "frames", "sidecar") or not isinstance(value, Mapping):
            continue
        merged.setdefault(key, {}).update(copy.deepcopy(dict(value)))
    return merged


def _sidecar_for_part(plan: context_map_core.ScanPlan, part: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Sidecar of a scan with one split part's sidecar fields (an empty value removes a key)."""
    sidecar = copy.deepcopy(plan.sidecar)
    for key, value in ((part or {}).get("sidecar") or {}).items():
        if value is None or value == "":
            sidecar.pop(key, None)
        else:
            sidecar[key] = copy.deepcopy(value)
    return sidecar


def _flatten(values: Mapping[str, Any], prefix: str = "") -> Dict[str, Any]:
    """{"bids": {"sub": "01"}} -> {"bids.sub": "01"} (nested mappings only)."""
    flat: Dict[str, Any] = {}
    for key, value in values.items():
        name = f"{prefix}{key}"
        if isinstance(value, Mapping):
            flat.update(_flatten(value, f"{name}."))
        else:
            flat[name] = value
    return flat


def _frame_layout(loader: Any, scan_id: int, reco_id: Optional[int]) -> Tuple[List[int], List[str]]:
    """(shape, shape_desc) of a reco without reading its data (frame axes from index 3)."""
    from brkraw.resolver import image as image_resolver
    from brkraw.resolver import shape as shape_resolver

    scan = loader.get_scan(scan_id)
    shape_info = shape_resolver.resolve(scan, reco_id=reco_id if reco_id is not None else 1)
    if not shape_info:
        return [], []
    return image_resolver.normalized_layout(shape_info)


def _metadata_for_rules(loader: Any, scan_id: int, reco_id: Optional[int], *, strict: bool) -> Dict[str, Any]:
    """Sidecar metadata for context map rules, read with or without -c.

    ``convert``/``split``/``sidecar`` rules may read metadata fields, so the
    result must not depend on -c. With -c a metadata error stops as before;
    without it the error is logged and the rules see no metadata.
    """
    try:
        return dict(loader.get_metadata(scan_id, reco_id=reco_id) or {})
    except Exception as exc:
        if strict:
            raise
        logger.warning("scan %s reco %s: metadata not available for context map rules: %s", scan_id, reco_id, exc)
        return {}


def _check_split(
    loader: Any, scan_id: int, reco_id: Optional[int], parts: Any, namespace_names: Sequence[str]
) -> None:
    """Check split parts against the scan's frame layout before any data is read (both convert paths)."""
    cm_output.validate_split_parts(parts, namespace_names)
    shape, shape_desc = _frame_layout(loader, scan_id, reco_id)
    _, notes = cm_output.plan_split(shape_desc, shape, parts)
    for note in notes:
        logger.info("scan %s reco %s: %s", scan_id, reco_id, note)


def _pack_count(loader: Any, scan_id: int, reco_id: Optional[int]) -> int:
    """Number of slice packs of a reco (1 when unknown)."""
    scan = loader.get_scan(scan_id)
    affine_info = getattr(scan, "affine_info", None)
    try:
        info = affine_info.get(reco_id) if affine_info is not None else None
        return max(1, len(info["num_slices"])) if info else 1
    except (TypeError, KeyError, AttributeError):
        return 1


def _convert_with_map_template(
    args: argparse.Namespace,
    loader: Any,
    scan_ids: Sequence[int],
    map_data: Mapping[str, Any],
    template: str,
    map_meta: Mapping[str, Any],
    *,
    convert_kwargs: Mapping[str, Any],
    default_selection: Mapping[str, Any],
) -> int:
    """Convert with the context map's layout_template (BRK-0021 ... BRK-0024).

    Every output name is planned first: convert/split per scan, ``utils``
    values, the template, then collisions (error by default, ``on_collision:
    suffix`` adds ``_2``, ``_3`` ...). Nothing is written when a name
    collides. Slice packs come first, then split parts within each pack.
    """
    mode = str(map_meta.get("on_collision") or "error")
    namespace_names = [k for k in map_data if k not in context_map_core.RESERVED and k != "__meta__"]
    tags = set(cm_output.template_tags(template))
    uses_counter = "utils.counter" in tags
    out_dir = Path(args.output) if args.output else Path.cwd()
    ext = ".json" if args.no_convert else (".nii.gz" if args.compress else ".nii")

    # 1) plan every output
    groups: List[Dict[str, Any]] = []
    outputs: List[Dict[str, Any]] = []
    for scan_id in scan_ids:
        if scan_id is None:
            continue
        scan = loader.get_scan(scan_id)
        reco_ids: List[Optional[int]] = [args.reco_id] if args.reco_id is not None else list(scan.avail.keys())
        if not reco_ids:
            if getattr(scan, "_converter_hook", None):
                reco_ids = [None]
            else:
                continue
        for reco_id in reco_ids:
            try:
                info, _ = layout_core.load_layout_info_parts(loader, scan_id, reco_id=reco_id)
                meta_base = _metadata_for_rules(loader, scan_id, reco_id, strict=bool(args.sidecar))
                plan = context_map_core.plan_scan(
                    info, map_data, scan_id=scan_id, reco_id=reco_id, metadata=meta_base
                )
                if not plan.convert:
                    logger.info("Skipping scan %s reco %s (context map: convert false).", scan_id, reco_id)
                    continue
                parts: List[Tuple[Optional[int], Optional[Mapping[str, Any]]]] = [(None, None)]
                if plan.split is not None:
                    _check_split(loader, scan_id, reco_id, plan.split, namespace_names)
                    parts = [(k, part) for k, part in enumerate(plan.split, start=1)]
            except context_map_core.ContextMapError as exc:
                logger.error("Context map, scan %s reco %s: %s", scan_id, reco_id, exc)
                return 2
            packs = 1 if args.no_convert else _pack_count(loader, scan_id, reco_id)
            label = f"scan {scan_id}" + (f" reco {reco_id}" if reco_id is not None else "")
            base = _flatten(info)
            base.setdefault("ScanID", scan_id)
            base.setdefault("RecoID", reco_id)
            for part_no, part in parts:
                group = {
                    "scan_id": scan_id,
                    "reco_id": reco_id,
                    "label": label + (f" part {part_no}" if part_no else ""),
                    "selection": _selection_for(part, default_selection),
                    "sidecar": _sidecar_for_part(plan, part) if args.sidecar else None,
                    "outputs": [],
                }
                groups.append(group)
                values = dict(base)
                values.update(_flatten(_namespaces_for_part(plan, part)))
                for pack in range(1, packs + 1):
                    item = {
                        "label": group["label"] + (f" pack {pack}" if packs > 1 else ""),
                        "values": values,
                        "utils": cm_output.utils_values(
                            slicepack=pack if packs > 1 else None, split=part_no
                        ),
                    }
                    group["outputs"].append(item)
                    outputs.append(item)

    if not outputs:
        logger.error("No outputs to convert (context map convert: false for every scan?).")
        return 2

    # 2) names: template, utils.counter, sanitize
    # every file an output writes counts: the NIfTI and, with -c, its sidecar
    exts = [ext] + ([".json"] if args.sidecar and ext != ".json" else [])

    def exists(name: str) -> bool:
        return any((out_dir / f"{name}{e}").exists() for e in exts)

    rendered: List[str] = []
    for item in outputs:
        for counter in range(1, 10000):
            values = dict(item["values"])
            values.update(item["utils"])
            if uses_counter:
                values["utils.counter"] = counter
            try:
                text, notes = cm_output.render_template(template, values)
            except ValueError as exc:
                logger.error("Context map layout_template: %s", exc)
                return 2
            name = _sanitize_filename(text)
            if not uses_counter or (name not in rendered and not exists(name)):
                break
        for note in notes:
            logger.warning("%s: layout_template %s", item["label"], note)
        rendered.append(name)
    try:
        names = cm_output.resolve_names(
            [(item["label"], name) for item, name in zip(outputs, rendered)],
            mode=mode,
            taken=set(),
            exists=exists,
        )
    except ValueError as exc:
        hints = []
        if any("part " in item["label"] for item in outputs) and "utils.split" not in tags:
            hints.append("split parts need distinct names: add [_part{utils.split}] to layout_template "
                         "or give each part its own namespace values")
        if any(" pack " in item["label"] for item in outputs) and "utils.slicepack" not in tags:
            hints.append("slice packs need distinct names: add [_sp{utils.slicepack}] to layout_template")
        logger.error("Context map: %s%s", exc, "".join(f"\n  hint: {h}" for h in hints))
        return 2
    for item, name in zip(outputs, names):
        item["path"] = out_dir / f"{name}{ext}"

    # 3) convert and write
    strict = args.scan_id is not None and len(args.scan_id) == 1 and args.reco_id is not None
    total_written = 0
    for group in groups:
        scan_id, reco_id = group["scan_id"], group["reco_id"]
        paths = [item["path"] for item in group["outputs"]]
        _ensure_output_dirs(paths)
        if args.no_convert:
            for path in paths:
                _write_sidecar(path, group["sidecar"])
                total_written += 1
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                nii = _convert_scan(loader, scan_id, reco_id, convert_kwargs, group["selection"])
        except Exception as exc:
            # as without a template: one failed scan stops only an explicit -s/-r request
            logger.error("Conversion failed for %s: %s", group["label"], exc)
            if strict:
                return 2
            continue
        if nii is None:
            logger.error("No NIfTI output generated for %s.", group["label"])
            if strict:
                return 2
            continue
        nii_list = list(nii) if isinstance(nii, tuple) else [nii]
        if len(nii_list) != len(paths):
            logger.error("%s: %d outputs planned, %d converted.", group["label"], len(paths), len(nii_list))
            return 2
        for path, obj in zip(paths, nii_list):
            obj.to_filename(str(path))
            logger.info("Wrote NIfTI: %s", path)
            total_written += 1
            if args.sidecar:
                _write_sidecar(path, group["sidecar"])
    if total_written == 0:
        logger.error("No outputs generated.")
        return 2
    return 0


def _convert_batch(args: argparse.Namespace) -> int:
    """Convert all datasets under a root folder.

    Args:
        args: Parsed CLI arguments for the convert --batch.

    Returns:
        Exit status code (0 on success, non-zero on failure).
    """
    if getattr(args, "scan_id", None) is not None or getattr(args, "reco_id", None) is not None:
        logger.error("--batch converts every dataset in the folder; -s/--scan-id and -r/--reco-id cannot be used with it.")
        return 2
    if getattr(args, "context_map", None):
        logger.error("--batch cannot apply one --context-map to every dataset; convert datasets one by one to use -M/--context-map.")
        return 2
    if args.path is None:
        args.path = os.environ.get("BRKRAW_PATH")
    if args.path is None:
        args.parser.print_help()
        return 2
    root = Path(args.path).expanduser()
    if not root.exists():
        logger.error("Path not found: %s", root)
        return 2
    if args.output:
        out_path = Path(args.output)
        if out_path.suffix in {".nii", ".gz"} or out_path.name.endswith(".nii.gz"):
            logger.error("With --batch, --output must be a directory.")
            return 2
        if not args.output.endswith(os.sep):
            args.output = f"{args.output}{os.sep}"
    args.scan_id = None
    args.reco_id = None
    candidates = _iter_dataset_paths(root)
    if not candidates:
        logger.error("No datasets found under %s", root)
        return 2
    failures = 0
    successes = 0
    for dataset_path in candidates:
        logger.info("Converting dataset: %s", dataset_path)
        dataset_args = argparse.Namespace(**vars(args))
        dataset_args.path = str(dataset_path)
        dataset_args.batch = False
        try:
            rc = _convert_one(dataset_args)
        except Exception as exc:
            logger.error("Failed to convert %s: %s", dataset_path, exc)
            failures += 1
            continue
        if rc != 0:
            failures += 1
        else:
            successes += 1
    if successes == 0:
        logger.error("No datasets were converted.")
        return 2
    if failures:
        logger.info("Converted %d dataset(s); %d failed.", successes, failures)
    return 0


def _sanitize_filename(name: str) -> str:
    """Return a filesystem-safe name by replacing invalid characters.

    Args:
        name: Input filename or prefix.

    Returns:
        Sanitized filename string.
    """
    parts = []
    for raw in re.split(r"[\\/]+", name.strip()):
        if not raw:
            continue
        cleaned = _INVALID_CHARS.sub("_", raw)
        cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
        if cleaned:
            parts.append(cleaned)
    return os.sep.join(parts) or "scan"


def _iter_dataset_paths(root: Path) -> List[Path]:
    """Enumerate dataset roots under a folder or file input.

    Args:
        root: Root folder or dataset path.

    Returns:
        List of dataset paths.
    """
    if root.is_file():
        return [root]
    candidates: List[Path] = []
    try:
        for entry in root.iterdir():
            if entry.is_dir():
                candidates.append(entry)
                continue
            if entry.is_file() and _is_zip_file(entry):
                candidates.append(entry)
    except PermissionError:
        logger.error("Permission denied while reading %s", root)
    return candidates


def _is_zip_file(path: Path) -> bool:
    """Return True when a path looks like a zip archive.

    Args:
        path: Filesystem path to inspect.

    Returns:
        True if the file has a zip signature.
    """
    try:
        with path.open("rb") as handle:
            sig = handle.read(4)
    except OSError:
        return False
    return sig in {b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"}


def _resolve_output_paths(
    output: Optional[str],
    base_name: str,
    *,
    count: int,
    compress: bool,
    slicepack_suffix: str,
    slicepack_suffixes: Optional[List[str]],
) -> Optional[List[Path]]:
    """Resolve output file paths based on CLI inputs.

    Args:
        output: Output path from CLI.
        base_name: Base filename without extension.
        count: Number of slice packs to write.
        compress: Whether to use .nii.gz.
        slicepack_suffix: Default suffix template for slice packs.
        slicepack_suffixes: Optional explicit suffix list.

    Returns:
        List of output paths or None when invalid.
    """
    if output is None:
        base_dir = Path.cwd()
        base = base_name
        ext = ".nii.gz" if compress else ".nii"
        return _expand_output_paths(
            base_dir,
            base,
            ext,
            count=count,
            slicepack_suffix=slicepack_suffix,
            slicepack_suffixes=slicepack_suffixes,
        )
    else:
        out_path = Path(output).expanduser()
        if output.endswith(os.sep) or (out_path.exists() and out_path.is_dir()):
            base_dir = out_path
            base = base_name
            ext = ".nii.gz" if compress else ".nii"
            return _expand_output_paths(
                base_dir,
                base,
                ext,
                count=count,
                slicepack_suffix=slicepack_suffix,
                slicepack_suffixes=slicepack_suffixes,
            )
        if out_path.suffix in {".nii", ".gz"} or out_path.name.endswith(".nii.gz"):
            base_dir = out_path.parent
            name = out_path.name
            if name.endswith(".nii.gz"):
                base, ext = name[:-7], ".nii.gz"
            elif name.endswith(".nii"):
                base, ext = name[:-4], ".nii"
            else:
                base, ext = name, ".nii.gz"
            return _expand_output_paths(
                base_dir,
                base,
                ext,
                count=count,
                slicepack_suffix=slicepack_suffix,
                slicepack_suffixes=slicepack_suffixes,
            )
        base_dir = out_path
        base = base_name
    ext = ".nii.gz" if compress else ".nii"
    return _expand_output_paths(
        base_dir,
        base,
        ext,
        count=count,
        slicepack_suffix=slicepack_suffix,
        slicepack_suffixes=slicepack_suffixes,
    )


def _expand_output_paths(
    base_dir: Path,
    base: str,
    ext: str,
    *,
    count: int,
    slicepack_suffix: str,
    slicepack_suffixes: Optional[List[str]],
) -> List[Path]:
    """Expand output filenames for slice packs.

    Args:
        base_dir: Output directory.
        base: Base filename.
        ext: File extension.
        count: Number of slice packs to write.
        slicepack_suffix: Default suffix template for slice packs.
        slicepack_suffixes: Optional explicit suffix list.

    Returns:
        List of output paths.
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    if count <= 1:
        return [base_dir / f"{base}{ext}"]
    if slicepack_suffixes:
        return [
            base_dir / f"{base}{slicepack_suffixes[i]}{ext}"
            for i in range(min(count, len(slicepack_suffixes)))
        ]
    suffix = slicepack_suffix or "_slpack{index}"
    if "{index}" not in suffix:
        suffix = f"{suffix}{{index}}"
    return [base_dir / f"{base}{suffix.format(index=i + 1)}{ext}" for i in range(count)]


def _paths_collide(paths: List[Path], reserved: set) -> bool:
    if len(set(paths)) != len(paths):
        return True
    for path in paths:
        if path in reserved or path.exists():
            return True
    return False


def _env_flag(name: str) -> bool:
    """Return True when an env var is set to a truthy value.

    Args:
        name: Environment variable name.

    Returns:
        True if the env var is truthy.
    """
    value = os.environ.get(name)
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _coerce_choice(name: str, value: Optional[str], choices: Tuple[str, ...], *, default=None):
    """Validate a value against allowed choices.

    Args:
        name: Label used for error reporting.
        value: Input value to validate.
        choices: Allowed string values.
        default: Default when value is None.

    Returns:
        The validated value or default.

    Raises:
        ValueError: If value is not in choices.
    """
    if value is None:
        return default
    value = value.strip()
    if value in choices:
        return value
    logger.error("Invalid %s: %s", name, value)
    raise ValueError(f"Invalid {name}: {value}")


def _parse_hook_args(values: List[str]) -> Dict[str, Dict[str, Any]]:
    parsed: Dict[str, Dict[str, Any]] = {}
    for raw in values:
        if ":" not in raw or "=" not in raw:
            raise ValueError("Hook args must be in HOOK:KEY=VALUE format.")
        hook_name, rest = raw.split(":", 1)
        key, value = rest.split("=", 1)
        hook_name = hook_name.strip()
        key = key.strip()
        if not hook_name or not key:
            raise ValueError("Hook args must include hook name and key.")
        coerced_value = _coerce_hook_value(value.strip())
        logger.debug("Parsed hook arg %s:%s=%s", hook_name, key, coerced_value)
        parsed.setdefault(hook_name, {})[key] = coerced_value
    logger.debug("Parsed hook args: %s", parsed)
    return parsed


def _ensure_output_dirs(paths: Sequence[Path]) -> None:
    for path in paths:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.error("Failed to create output directory %s: %s", path.parent, exc)
            raise


def _uses_counter_tag(
    *,
    layout_template: Optional[str],
    layout_entries: List[Any],
    prefix_template: Optional[str],
) -> bool:
    if isinstance(layout_template, str) and _COUNTER_TAG.search(layout_template):
        return True
    if isinstance(prefix_template, str) and _COUNTER_TAG.search(prefix_template):
        return True
    for field in layout_entries or []:
        if not isinstance(field, Mapping):
            continue
        key = field.get("key")
        if isinstance(key, str) and key.strip() in {"Counter", "counter"}:
            return True
    return False


def _coerce_scalar(value: str) -> Any:
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _coerce_hook_value(value: str) -> Any:
    if value.startswith("[") and value.endswith("]"):
        return _coerce_bracketed_value(value, list)
    if value.startswith("(") and value.endswith(")"):
        return _coerce_bracketed_value(value, tuple)
    if "," in value:
        return tuple(_coerce_scalar(part.strip()) for part in value.split(",") if part.strip())
    return _coerce_scalar(value)


def _coerce_bracketed_value(value: str, expected_type: type) -> Any:
    import ast

    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError) as exc:
        raise ValueError(f"Invalid hook arg list/tuple: {value}") from exc
    if not isinstance(parsed, expected_type):
        label = "list" if expected_type is list else "tuple"
        raise ValueError(f"Hook arg must be {label}: {value}")
    return parsed


def _to_json_safe(value: Any) -> Any:
    """Convert values to JSON-serializable types.

    Args:
        value: Input value to normalize.

    Returns:
        JSON-serializable value.
    """
    if isinstance(value, Mapping):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def _write_sidecar(path: Path, meta: Any) -> None:
    """Write sidecar JSON metadata next to a NIfTI path.

    Args:
        path: NIfTI file path.
        meta: Metadata to serialize.
    """
    sidecar = path.with_suffix(".json")
    if path.name.endswith(".nii.gz"):
        sidecar = path.with_name(path.name[:-7] + ".json")
    payload = _to_json_safe(meta or {})
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    logger.info("Wrote sidecar: %s", sidecar)


def _add_convert_args(
    parser: argparse.ArgumentParser,
    *,
    output_help: str,
    include_scan_reco: bool = True,
) -> None:
    """Register convert-related CLI arguments on a parser.

    Args:
        parser: Target argument parser.
        output_help: Help text for the output argument.
        include_scan_reco: Whether to add scan/reco options.
    """
    selection = parser.add_argument_group("selection")
    output = parser.add_argument_group("output")
    metadata = parser.add_argument_group("metadata")
    orientation = parser.add_argument_group("orientation")
    data = parser.add_argument_group("data")
    hooks = parser.add_argument_group("hooks")
    header = parser.add_argument_group("nifti header")

    if include_scan_reco:
        selection.add_argument(
            "-s",
            "--scan-id",
            nargs="+",
            metavar="ID",
            help=(
                "Scan id(s) to convert, for example -s 3 or -s 3 4 5 or -s 3,4,5 "
                "(all scans when omitted). With two or more, --output must be a folder."
            ),
        )
        selection.add_argument(
            "-r",
            "--reco-id",
            type=int,
            help="Reco id to convert (defaults to all recos when omitted).",
        )

    output.add_argument(
        "-o",
        "--output",
        help=output_help,
    )
    output.add_argument(
        "--prefix",
        help="Filename prefix (supports {Key} tags from layout info).",
    )
    output.add_argument(
        "--no-compress",
        dest="compress",
        action="store_false",
        help="Write .nii instead of .nii.gz (default: compressed).",
    )
    output.add_argument(
        "-M",
        "--context-map",
        dest="context_map",
        help="Context map YAML to use instead of the same-name file next to the dataset.",
    )
    output.add_argument(
        "--no-context-map",
        dest="no_context_map",
        action="store_true",
        help="Do not use a context map, not even the same-name file next to the dataset.",
    )

    metadata.add_argument(
        "-c",
        "--sidecar",
        action="store_true",
        help="Write a JSON sidecar using metadata rules.",
    )
    metadata.add_argument(
        "--no-convert",
        action="store_true",
        help="Skip NIfTI conversion and only write sidecar metadata (requires --sidecar).",
    )

    orientation.add_argument(
        "-S",
        "--space",
        choices=list(get_args(AffineSpace)),
        help="Affine space for conversion (default: subject_ras).",
    )
    orientation.add_argument(
        "-T",
        "--override-subject-type",
        choices=list(get_args(SubjectType)),
        help="Override subject type for subject-view affines (space=subject_ras).",
    )
    orientation.add_argument(
        "-P",
        "--override-subject-pose",
        choices=list(get_args(SubjectPose)),
        help="Override subject pose for subject-view affines (space=subject_ras).",
    )

    data.add_argument(
        "-F",
        "--flatten-fg",
        action="store_true",
        help="Flatten frame-group dimensions to 4D when data is 5D or higher.",
    )
    data.add_argument(
        "--axis",
        help="Frame axis for --frames: a name shown by 'brkraw info' (echo, cycle, ...) or an axis "
             "number (3 or more). May be omitted when the data has one frame axis.",
    )
    data.add_argument(
        "--frames",
        help="Frames to keep on --axis, numpy style: 2 (one frame, axis removed), 2,0 (list, axis kept) "
             "or 1:3 (slice start:stop[:step], axis kept).",
    )
    data.add_argument(
        "-I",
        "--cycle-index",
        type=int,
        help="Deprecated (removed in 0.7.0): use --axis cycle --frames START:STOP.",
    )
    data.add_argument(
        "-N",
        "--cycle-count",
        type=int,
        help="Deprecated (removed in 0.7.0): use --axis cycle --frames START:STOP.",
    )

    hooks.add_argument(
        "-H",
        "--hook-arg",
        action="append",
        default=[],
        help="Hook argument in HOOK:KEY=VALUE format (repeatable).",
    )
    hooks.add_argument(
        "--hook-args-yaml",
        action="append",
        default=[],
        help="YAML file containing hook args mapping (repeatable).",
    )

    header.add_argument(
        "--xyz-units",
        choices=list(get_args(XYZUNIT)),
        default="mm",
        help="Spatial units for NIfTI header (default: mm).",
    )
    header.add_argument(
        "--t-units",
        choices=list(get_args(TUNIT)),
        default="sec",
        help="Temporal units for NIfTI header (default: sec).",
    )
    header.add_argument(
        "--header",
        help="Path to a YAML file containing NIfTI header overrides.",
    )


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
    """Register the convert command on the main CLI parser.

    Args:
        subparsers: Subparser collection from argparse.
    """
    convert_parser = subparsers.add_parser(
        "convert",
        help="Convert scans to NIfTI (one, several or all; --batch for a folder of studies).",
    )
    convert_parser.add_argument(
        "path",
        nargs="?",
        help="Path to the Bruker study (with --batch: a folder of studies).",
    )
    convert_parser.add_argument("--batch", action="store_true", help="Convert every dataset in the folder PATH (not with -s, -r or -M).")
    _add_convert_args(convert_parser, output_help="Output directory or .nii/.nii.gz file path.")
    add_root_argument(convert_parser)
    convert_parser.set_defaults(func=cmd_convert, parser=convert_parser)
