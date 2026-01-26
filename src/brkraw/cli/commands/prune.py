from __future__ import annotations

"""Create a pruned dataset zip using a prune spec."""

import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from brkraw.cli.utils import spinner
from brkraw.core import config as config_core
from brkraw.specs.pruner import prune_dataset_to_zip_from_spec

logger = logging.getLogger(__name__)


def cmd_prune(args: argparse.Namespace) -> int:
    output = args.output
    root_name_override = None
    dirs_override = _build_dir_override(args.scan_ids, args.reco_ids)
    template_vars = _parse_kv_pairs(args.set_vars)
    try:
        spec_path = _resolve_pruner_spec(
            args.spec_name if args.spec_name else args.spec
        )
    except ValueError as exc:
        logger.error("%s", exc)
        return 2
    if output is None:
        root_name = _load_root_name(spec_path)
        if not root_name:
            logger.error("Prune spec has no root_name; please provide --output.")
            return 2
        output = _default_output_path(Path(args.path), spec_path=spec_path)
    else:
        root_name_override = Path(output).stem
    try:
        logger.info("Pruning dataset: %s", args.path)
        logger.info("Prune spec: %s", spec_path)
        logger.info("Output zip: %s", output)
        with spinner("Pruning"):
            out_path = prune_dataset_to_zip_from_spec(
                spec_path,
                source=args.path,
                dest=output,
                validate=not args.no_validate,
                strip_jcamp_comments=args.strip_jcamp_comments,
                root_name=root_name_override,
                dirs=dirs_override,
                mode=args.mode,
                template_vars=template_vars,
            )
        logger.info("Wrote pruned zip: %s", out_path)
        _write_prune_sidecar(
            out_path=Path(out_path),
            input_path=Path(args.path),
            spec_path=spec_path,
            args=args,
            root_name_override=root_name_override,
            dirs_override=dirs_override,
            template_vars=template_vars,
        )
    except Exception as exc:
        logger.error("%s", exc)
        return 2
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
    prune_parser = subparsers.add_parser(
        "prune",
        help="Create a pruned dataset zip from a prune spec.",
    )
    prune_parser.add_argument(
        "path",
        type=str,
        help="Source dataset path.",
    )
    spec_group = prune_parser.add_mutually_exclusive_group(required=True)
    spec_group.add_argument(
        "--spec",
        dest="spec",
        type=str,
        help="Path to prune spec YAML (or basename of installed spec).",
    )
    spec_group.add_argument(
        "--spec-name",
        dest="spec_name",
        type=str,
        help="Use an installed pruner spec by name (basename, no path).",
    )
    prune_parser.add_argument(
        "-o",
        "--output",
        dest="output",
        type=str,
        help="Output zip path (default: <input>_pruned.*).",
    )
    prune_parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip prune spec validation.",
    )
    prune_parser.add_argument(
        "--strip-jcamp-comments",
        action="store_true",
        help="Remove $$ comment lines from kept JCAMP files.",
    )
    prune_parser.add_argument(
        "--mode",
        choices=["keep", "drop"],
        help="Override spec mode for file selection.",
    )
    prune_parser.add_argument(
        "--set-var",
        dest="set_vars",
        action="append",
        metavar="KEY=VALUE",
        help="Template variable for use in prune spec (can repeat).",
    )
    prune_parser.add_argument(
        "--scan-ids",
        nargs="+",
        metavar="SCAN_ID",
        help="Override scan IDs to keep (space or comma separated).",
    )
    prune_parser.add_argument(
        "--reco-ids",
        nargs="+",
        metavar="RECO_ID",
        help="Override reco IDs to keep (space or comma separated).",
    )
    prune_parser.set_defaults(func=cmd_prune)


def _default_output_path(path: Path, *, spec_path: Path) -> str:
    root_name = _load_root_name(spec_path)
    suffix = path.suffix
    base_dir = Path.cwd()
    base_name = root_name or _stem_or_name(path)
    if path.is_dir():
        return str(base_dir / f"{base_name}.zip")
    if suffix and path.name.endswith(suffix):
        return str(base_dir / f"{base_name}{suffix}")
    return str(base_dir / f"{base_name}.zip")


def _stem_or_name(path: Path) -> str:
    if path.is_dir():
        return f"{path.name}_pruned"
    suffix = path.suffix
    return path.name[:-len(suffix)] if suffix else path.name


def _load_root_name(spec_path: Path) -> Optional[str]:
    try:
        data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    root_name = data.get("root_name")
    if isinstance(root_name, str) and root_name.strip():
        return root_name.strip()
    return None


def _write_prune_sidecar(
    *,
    out_path: Path,
    input_path: Path,
    spec_path: Path,
    args: argparse.Namespace,
    root_name_override: Optional[str],
    dirs_override: Optional[list],
    template_vars: dict,
) -> None:
    sidecar = out_path.with_suffix(".prune.yaml")
    spec_summary = _load_prune_spec_summary(spec_path)
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "command": "brkraw prune",
        "input_path": str(input_path),
        "output_path": str(out_path),
        "spec_path": str(spec_path),
        "spec": spec_summary,
        "mode": args.mode,
        "strip_jcamp_comments": bool(args.strip_jcamp_comments),
        "scan_ids": args.scan_ids,
        "reco_ids": args.reco_ids,
        "set_vars": args.set_vars,
        "template_vars": template_vars,
        "root_name_override": root_name_override,
        "dirs_override": dirs_override,
    }
    sidecar.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _resolve_pruner_spec(value: Optional[str]) -> Path:
    if value is None:
        raise ValueError("A prune spec is required (use --spec or --spec-name).")
    raw = Path(value).expanduser()
    candidates = []
    if raw.suffix:
        candidates.append(raw)
    else:
        candidates.append(raw)
        candidates.append(raw.with_suffix(".yaml"))
        candidates.append(raw.with_suffix(".yml"))

    if raw.is_absolute():
        for cand in candidates:
            if cand.exists():
                return cand
        raise ValueError(f"Prune spec not found: {value}")

    search_roots = [Path.cwd(), config_core.paths().pruner_specs_dir]
    for base in search_roots:
        for cand in candidates:
            path = (base / cand).resolve()
            if path.exists():
                return path
    raise ValueError(f"Prune spec not found: {value}")




def _load_prune_spec_summary(spec_path: Path) -> dict:
    try:
        data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        "__meta__": data.get("__meta__", {}),
        "mode": data.get("mode"),
        "files": data.get("files"),
        "dirs": data.get("dirs"),
        "update_params_keys": list((data.get("update_params") or {}).keys()),
        "add_root": data.get("add_root"),
        "root_name": data.get("root_name"),
        "strip_jcamp_comments": data.get("strip_jcamp_comments"),
    }


def _build_dir_override(
    scan_ids: Optional[list[str]],
    reco_ids: Optional[list[str]],
) -> Optional[list[dict[str, object]]]:
    scan_list = _parse_id_list(scan_ids)
    reco_list = _parse_id_list(reco_ids)
    rules: list[dict[str, object]] = []
    if scan_list:
        rules.append({"level": 1, "dirs": scan_list})
    if reco_list:
        rules.append({"level": 3, "dirs": reco_list})
    return rules or None


def _parse_id_list(values: Optional[list[str]]) -> list[str]:
    if not values:
        return []
    result: list[str] = []
    for value in values:
        for part in str(value).split(","):
            part = part.strip()
            if part:
                result.append(part)
    return result


def _parse_kv_pairs(items: Optional[list[str]]) -> dict[str, str]:
    if not items:
        return {}
    pairs: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            continue
        pairs[key] = value
    return pairs
