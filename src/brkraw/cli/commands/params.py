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

from brkraw.cli.utils import add_root_argument, load, parse_scan_ids

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
        if env_scan and env_scan.strip():
            # one scan-id rule (cli.utils.parse_scan_ids); params searches one scan
            try:
                ids = parse_scan_ids([env_scan])
            except ValueError as exc:
                logger.error("BRKRAW_SCAN_ID: %s", exc)
                return 2
            if len(ids) > 1:
                logger.error(
                    "params searches one scan id; BRKRAW_SCAN_ID holds %s. Give one with -s/--scan-id.",
                    ", ".join(str(i) for i in ids),
                )
                return 2
            args.scan_id = ids[0]
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
    # the result is the command's output: stdout, whatever the logging level
    if result is None:
        print("(none)")
        return 0
    def _to_yaml_safe(value):
        if isinstance(value, dict):
            return {k: _to_yaml_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_to_yaml_safe(v) for v in value]
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    print(yaml.safe_dump(_to_yaml_safe(result), sort_keys=False), end="")
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
        help="Scan id to search (one; also BRKRAW_SCAN_ID). A study path needs it: without a scan id nothing is found.",
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
    add_root_argument(params_parser)
    params_parser.set_defaults(func=cmd_params, parser=params_parser)
