from __future__ import annotations

"""Convert a scan/reco to NIfTI with optional metadata sidecar.

Last updated: 2026-01-06
"""

import argparse
import inspect
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Optional, Dict, List, Tuple, Literal, cast, get_args

import numpy as np
import yaml

from brkraw.cli.utils import load
from brkraw.core import config as config_core
from brkraw.core import layout as layout_core
from brkraw.resolver import nifti as nifti_resolver
from brkraw.specs import remapper as remapper_core
from brkraw.resolver.nifti import XYZUNIT, TUNIT, Nifti1HeaderContents
from brkraw.resolver.affine import SubjectPose, SubjectType
from brkraw.apps.loader.types import AffineSpace


logger = logging.getLogger("brkraw")

_INVALID_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def cmd_convert(args: argparse.Namespace) -> int:
    """Convert a scan/reco to NIfTI with optional metadata sidecars.

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

    # resolve scan/reco ids
    id_sources = (
        ("scan_id", "BRKRAW_SCAN_ID", True),
        ("scan_id", "BRKRAW_CONVERT_SCAN_ID", False),
        ("reco_id", "BRKRAW_RECO_ID", False),
        ("reco_id", "BRKRAW_CONVERT_RECO_ID", False),
    )
    for attr, env_key, split_comma in id_sources:
        if getattr(args, attr) is not None:
            continue
        value = os.environ.get(env_key)
        if not value:
            continue
        text = value.split(",")[0] if split_comma else value
        try:
            setattr(args, attr, int(text))
        except ValueError:
            logger.error("Invalid %s: %s", env_key, value)
            return 2

    # resolve flags + spaces
    if not args.sidecar:
        args.sidecar = _env_flag("BRKRAW_CONVERT_SIDECAR")
    if not args.flip_x:
        args.flip_x = _env_flag("BRKRAW_CONVERT_FLIP_X")
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
    for attr, env_key in (
        ("format", "BRKRAW_CONVERT_FORMAT"),
        ("header", "BRKRAW_CONVERT_HEADER"),
        ("context_map", "BRKRAW_CONVERT_CONTEXT_MAP"),
    ):
        if getattr(args, attr) is None:
            setattr(args, attr, os.environ.get(env_key))
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

    args.format = _coerce_choice(
        "BRKRAW_CONVERT_FORMAT",
        args.format or "nifti",
        ("nifti", "nifti1"),
        default="nifti",
    )

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
            hook_args_by_name = _load_hook_args_yaml(hook_args_yaml_sources)
        except ValueError as exc:
            logger.error("%s", exc)
            return 2

    try:
        hook_args_cli = _parse_hook_args(args.hook_arg or [])
    except ValueError as exc:
        logger.error("%s", exc)
        return 2
    hook_args_by_name = _merge_hook_args(hook_args_by_name, hook_args_cli)

    loader = load(args.path, prefix="Loading")
    try:
        override_header = nifti_resolver.load_header_overrides(args.header)
    except ValueError:
        return 2
    
    batch_all = args.scan_id is None
    if batch_all and args.output and not output_is_file and not args.output.endswith(os.sep):
        args.output = f"{args.output}{os.sep}"
    if batch_all and output_is_file:
        logger.error("When omitting --scan-id, --output must be a directory.")
        return 2
    if not batch_all and args.reco_id is None:
        args.reco_id = 1

    scan_ids = list(loader.avail.keys()) if batch_all else [args.scan_id]
    if not scan_ids:
        logger.error("No scans available for conversion.")
        return 2

    root = None
    layout_entries = config_core.layout_entries(root=root)
    layout_template = config_core.layout_template(root=root)
    layout_meta = {}

    selector_map = None
    if args.context_map:
        # resolve selector
        try:
            selector_map = remapper_core.load_context_map(args.context_map)
        except Exception as exc:
            logger.error("%s", exc)
            return 2
        
        # resolve layout
        layout_meta = layout_core.load_layout_meta(args.context_map)
        if isinstance(layout_meta, dict):
            meta_entries = layout_meta.get("layout_entries")
            if meta_entries is None:
                meta_entries = layout_meta.get("layout_fields")
            if isinstance(meta_entries, list):
                layout_entries = meta_entries
            meta_template = layout_meta.get("layout_template")
            if isinstance(meta_template, str) and meta_template.strip():
                layout_template = meta_template
        
    slicepack_suffix = config_core.output_slicepack_suffix(root=root)
    if isinstance(layout_meta, dict):
        meta_suffix = layout_meta.get("slicepack_suffix")
        if isinstance(meta_suffix, str) and meta_suffix.strip():
            slicepack_suffix = meta_suffix
        
    total_written = 0
    reserved_paths: set = set()
    for scan_id in scan_ids:
        if scan_id is None:
            continue
        scan = loader.get_scan(scan_id)
        reco_ids = [args.reco_id] if args.reco_id is not None else list(scan.avail.keys())
        if not reco_ids:
            if getattr(scan, "_converter_hook", None):
                reco_ids = [None]
            else:
                continue
        for reco_id in reco_ids:
            if selector_map is not None:
                # convert selection by context_map
                selector_info, selector_meta = layout_core.load_layout_info_parts(
                    loader,
                    scan_id,
                    context_map=args.context_map,
                    reco_id=reco_id,
                )
                if not selector_info and not selector_meta:
                    logger.debug("Skipping scan %s reco %s (no metadata).", scan_id, reco_id)
                    continue
                if not remapper_core.matches_context_map_selectors(
                    (selector_info, selector_meta),
                    selector_map,
                ):
                    logger.debug("Skipping scan %s reco %s (selector mismatch).", scan_id, reco_id)
                    continue
            nii = loader.convert(
                scan_id,
                reco_id=reco_id,
                format=cast(Literal["nifti", "nifti1"], args.format),
                space=cast(AffineSpace, args.space),
                override_header=cast(Nifti1HeaderContents, override_header) if override_header else None,
                override_subject_type=cast(Optional[SubjectType], args.override_subject_type),
                override_subject_pose=cast(Optional[SubjectPose], args.override_subject_pose),
                flip_x=args.flip_x,
                xyz_units=cast(XYZUNIT, args.xyz_units),
                t_units=cast(TUNIT, args.t_units),
                hook_args_by_name=hook_args_by_name,
            )
            if nii is None:
                if not batch_all and args.reco_id is not None:
                    logger.error("No NIfTI output generated for scan %s reco %s.", scan_id, reco_id)
                    return 2
                continue

            nii_list = list(nii) if isinstance(nii, tuple) else [nii]

            base_name_base: Optional[str] = None
            slicepack_suffixes: Optional[List[str]] = None
            output_paths: Optional[List[Path]] = None
            for counter in range(1, 1000):
                layout_kwargs: Dict[str, Any] = {}
                if render_layout_supports_counter and args.dedupe:
                    layout_kwargs["counter"] = counter
                try:
                    candidate_base_name = layout_core.render_layout(
                        loader,
                        scan_id,
                        layout_entries=layout_entries,
                        layout_template=layout_template,
                        context_map=args.context_map,
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
                        context_map=args.context_map,
                        reco_id=reco_id,
                        **layout_kwargs,
                    )
                if batch_all and args.prefix:
                    candidate_base_name = f"{candidate_base_name}_scan-{scan_id}"
                if args.reco_id is None and len(reco_ids) > 1:
                    candidate_base_name = f"{candidate_base_name}_reco-{reco_id}"
                candidate_base_name = _sanitize_filename(candidate_base_name)

                if base_name_base is None:
                    base_name_base = candidate_base_name
                elif args.dedupe and candidate_base_name == base_name_base:
                    candidate_base_name = f"{candidate_base_name}_{counter}"

                slicepack_suffixes = None
                if len(nii_list) > 1:
                    info = layout_core.load_layout_info(
                        loader,
                        scan_id,
                        context_map=args.context_map,
                        reco_id=reco_id,
                    )
                    slicepack_suffixes = layout_core.render_slicepack_suffixes(
                        info,
                        count=len(nii_list),
                        template=slicepack_suffix,
                        **({"counter": counter} if slicepack_supports_counter and args.dedupe else {}),
                    )
                output_paths = _resolve_output_paths(
                    args.output,
                    candidate_base_name,
                    count=len(nii_list),
                    compress=bool(args.compress),
                    slicepack_suffix=slicepack_suffix,
                    slicepack_suffixes=slicepack_suffixes,
                )
                if output_paths is None:
                    return 2
                if len(output_paths) != len(nii_list):
                    logger.error("Output path count does not match NIfTI outputs.")
                    return 2
                if not args.dedupe:
                    break
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

            sidecar_meta = None
            if args.sidecar:
                sidecar_meta = loader.get_metadata(
                    scan_id,
                    reco_id=reco_id,
                    context_map=args.context_map,
                )

            for path, obj in zip(output_paths, nii_list):
                path.parent.mkdir(parents=True, exist_ok=True)
                obj.to_filename(str(path))
                logger.info("Wrote NIfTI: %s", path)
                total_written += 1
                if args.sidecar:
                    _write_sidecar(path, sidecar_meta)
    if total_written == 0:
        logger.error("No NIfTI outputs generated.")
        return 2
    return 0


def cmd_convert_batch(args: argparse.Namespace) -> int:
    """Convert all datasets under a root folder.

    Args:
        args: Parsed CLI arguments for the convert-batch subcommand.

    Returns:
        Exit status code (0 on success, non-zero on failure).
    """
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
            logger.error("When using convert batch, --output must be a directory.")
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
        try:
            rc = cmd_convert(dataset_args)
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
        parsed.setdefault(hook_name, {})[key] = _coerce_scalar(value.strip())
    return parsed


def _merge_hook_args(
    base: Mapping[str, Mapping[str, Any]],
    override: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for hook_name, values in base.items():
        if not isinstance(hook_name, str) or not hook_name:
            continue
        if not isinstance(values, Mapping):
            continue
        merged[hook_name] = dict(values)
    for hook_name, values in override.items():
        if not isinstance(hook_name, str) or not hook_name:
            continue
        if not isinstance(values, Mapping):
            continue
        merged.setdefault(hook_name, {}).update(dict(values))
    return merged


def _load_hook_args_yaml(paths: List[str]) -> Dict[str, Dict[str, Any]]:
    """Load hook args mapping from YAML files.

    Supported YAML formats:
      - `{hooks: {hook_name: {key: value}}}`
      - `{hook_name: {key: value}}`
    """

    merged: Dict[str, Dict[str, Any]] = {}

    def normalize_doc(doc: Any, *, source: str) -> Dict[str, Dict[str, Any]]:
        if doc is None:
            return {}
        hooks_obj = doc.get("hooks") if isinstance(doc, Mapping) else None
        if hooks_obj is None and isinstance(doc, Mapping):
            hooks_obj = doc
        if not isinstance(hooks_obj, Mapping):
            raise ValueError(f"Invalid hook args YAML in {source!r}: expected mapping.")

        out: Dict[str, Dict[str, Any]] = {}
        for hook_name, values in hooks_obj.items():
            if not isinstance(hook_name, str) or not hook_name.strip():
                continue
            if values is None:
                continue
            if not isinstance(values, Mapping):
                raise ValueError(
                    f"Invalid hook args YAML in {source!r}: hook {hook_name!r} must map to a dict."
                )
            out[hook_name.strip()] = dict(values)
        return out

    for raw in paths:
        source = raw.strip()
        if not source:
            continue
        if source == "-":
            doc = yaml.safe_load(sys.stdin.read())
        else:
            path = Path(source).expanduser()
            if not path.exists():
                raise ValueError(f"Hook args YAML not found: {source}")
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        parsed = normalize_doc(doc, source=source)
        merged = _merge_hook_args(merged, parsed)

    return merged


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
    if include_scan_reco:
        parser.add_argument(
            "-s",
            "--scan-id",
            type=int,
            help="Scan id to convert.",
        )
        parser.add_argument(
            "-r",
            "--reco-id",
            type=int,
            help="Reco id to convert (default: 1).",
        )
    parser.add_argument(
        "--flip-x",
        action="store_true",
        help="Flip x-axis in NIfTI header.",
    )
    parser.add_argument(
        "--xyz-units",
        choices=list(get_args(XYZUNIT)),
        default="mm",
        help="Spatial units for NIfTI header (default: mm).",
    )
    parser.add_argument(
        "--t-units",
        choices=list(get_args(TUNIT)),
        default="sec",
        help="Temporal units for NIfTI header (default: sec).",
    )
    parser.add_argument(
        "--header",
        help="Path to a YAML file containing NIfTI header overrides.",
    )

    parser.add_argument(
        "-o",
        "--output",
        help=output_help,
    )
    parser.add_argument(
        "--prefix",
        help="Filename prefix (supports {Key} tags from layout info).",
    )
    parser.add_argument(
        "--dedupe",
        action="store_true",
        help="Avoid overwriting when output names collide (uses {Counter} tag or appends _N).",
    )
    parser.add_argument(
        "--sidecar",
        action="store_true",
        help="Write a JSON sidecar using metadata rules.",
    )
    parser.add_argument(
        "--context-map",
        dest="context_map",
        help="Context map YAML for metadata and output mapping.",
    )
    parser.add_argument(
        "--hook-arg",
        action="append",
        default=[],
        help="Hook argument in HOOK:KEY=VALUE format (repeatable).",
    )
    parser.add_argument(
        "--hook-args-yaml",
        action="append",
        default=[],
        help="YAML file containing hook args mapping (repeatable).",
    )
    parser.add_argument(
        "--space",
        choices=list(get_args(AffineSpace)),
        help="Affine space for conversion (default: subject_ras).",
    )
    parser.add_argument(
        "--override-subject-type",
        choices=list(get_args(SubjectType)),
        help="Override subject type for subject-view affines (space=subject_ras).",
    )
    parser.add_argument(
        "--override-subject-pose",
        choices=list(get_args(SubjectPose)),
        help="Override subject pose for subject-view affines (space=subject_ras).",
    )
    parser.add_argument(
        "--format",
        choices=["nifti", "nifti1"],
        help="Output format (default: nifti).",
    )
    parser.add_argument(
        "--no-compress",
        dest="compress",
        action="store_false",
        help="Write .nii instead of .nii.gz (default: compressed).",
    )


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
    """Register convert subcommands on the main CLI parser.

    Args:
        subparsers: Subparser collection from argparse.
    """
    convert_parser = subparsers.add_parser(
        "convert",
        help="Convert a scan/reco to NIfTI.",
    )
    convert_parser.add_argument(
        "path",
        nargs="?",
        help="Path to the Bruker study.",
    )
    _add_convert_args(convert_parser, output_help="Output directory or .nii/.nii.gz file path.")
    convert_parser.set_defaults(func=cmd_convert, parser=convert_parser)

    batch_parser = subparsers.add_parser(
        "convert-batch",
        help="Convert all datasets under a root folder.",
    )
    batch_parser.add_argument("path", help="Root folder containing datasets.")
    _add_convert_args(
        batch_parser,
        output_help="Output directory.",
        include_scan_reco=False,
    )
    batch_parser.set_defaults(func=cmd_convert_batch, parser=batch_parser)
