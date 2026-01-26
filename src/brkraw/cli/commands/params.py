from __future__ import annotations

"""Parameter search command for BrkRaw.

Last updated: 2025-12-30
"""

import argparse
import logging
import os
from pathlib import Path
import yaml
import numpy as np

from brkraw.cli.utils import load

logger = logging.getLogger(__name__)


def cmd_params(args: argparse.Namespace) -> int:
    if args.path is None:
        args.path = os.environ.get("BRKRAW_PATH")
    if args.path is None:
        args.parser.print_help()
        return 2
    if args.key is None:
        args.key = os.environ.get("BRKRAW_PARAM_KEY")
    if args.key is None:
        logger.error("Missing --key (or BRKRAW_PARAM_KEY).")
        return 2
    if args.scan_id is None:
        env_scan = os.environ.get("BRKRAW_SCAN_ID")
        if env_scan:
            try:
                args.scan_id = int(env_scan)
            except ValueError:
                logger.error("Invalid BRKRAW_SCAN_ID: %s", env_scan)
                return 2
    if args.reco_id is None:
        env_reco = os.environ.get("BRKRAW_RECO_ID")
        if env_reco:
            try:
                args.reco_id = int(env_reco)
            except ValueError:
                logger.error("Invalid BRKRAW_RECO_ID: %s", env_reco)
                return 2
    if args.file is None:
        env_file = os.environ.get("BRKRAW_PARAM_FILE")
        if env_file:
            args.file = [p.strip() for p in env_file.split(",") if p.strip()]
    if not Path(args.path).exists():
        logger.error("Path not found: %s", args.path)
        return 2
    loader = load(args.path, prefix="Loading")
    result = loader.search_params(
        args.key,
        file=args.file,
        scan_id=args.scan_id,
        reco_id=args.reco_id,
    )
    if result is None:
        logger.info("(none)")
        return 0
    def _to_yaml_safe(value):
        if isinstance(value, dict):
            return {k: _to_yaml_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_to_yaml_safe(v) for v in value]
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    logger.info("%s", yaml.safe_dump(_to_yaml_safe(result), sort_keys=False))
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
    params_parser = subparsers.add_parser(
        "params",
        help="Search parameter files for key matches.",
    )
    params_parser.add_argument("path", nargs="?", help="Path to the Bruker study.")
    params_parser.add_argument(
        "-k",
        "--key",
        help="Parameter key to search for.",
    )
    params_parser.add_argument(
        "-s",
        "--scan-id",
        type=int,
        help="Scan id to search (required for study-level search).",
    )
    params_parser.add_argument(
        "-r",
        "--reco-id",
        type=int,
        help="Reco id to search within a scan.",
    )
    params_parser.add_argument(
        "-f",
        "--file",
        nargs="*",
        help="Parameter file(s) to search (method, acqp, visu_pars, reco).",
    )
    params_parser.set_defaults(func=cmd_params, parser=params_parser)
