from __future__ import annotations

"""Create a pruned dataset zip using a prune spec."""

import argparse
import logging
from pathlib import Path
from typing import Optional, Union

import yaml

from brkraw.cli.utils import spinner
from brkraw.specs.pruner import prune_dataset_to_zip_from_spec

logger = logging.getLogger("brkraw")


def cmd_prune(args: argparse.Namespace) -> int:
    output = args.output
    root_name_override = None
    dirs_override = _build_dir_override(args.scan_ids, args.reco_ids)
    if output is None:
        output = _default_output_path(Path(args.path), spec_path=Path(args.spec))
    else:
        root_name_override = Path(output).stem
    try:
        logger.info("Pruning dataset: %s", args.path)
        logger.info("Prune spec: %s", args.spec)
        logger.info("Output zip: %s", output)
        with spinner("Pruning"):
            out_path = prune_dataset_to_zip_from_spec(
                args.spec,
                source=args.path,
                dest=output,
                validate=not args.no_validate,
                strip_jcamp_comments=args.strip_jcamp_comments,
                root_name=root_name_override,
                dirs=dirs_override,
                mode=args.mode,
            )
        logger.info("Wrote pruned zip: %s", out_path)
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
    prune_parser.add_argument(
        "--spec",
        dest="spec",
        type=str,
        required=True,
        help="Path to prune spec YAML.",
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
