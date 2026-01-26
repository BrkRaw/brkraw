from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from brkraw.core import config as config_core
from brkraw.cli.utils import load

logger = logging.getLogger(__name__)


def cmd_info(args: argparse.Namespace) -> int:
    if args.path is None:
        args.path = os.environ.get("BRKRAW_PATH")
    if args.path is None:
        args.parser.print_help()
        return 2
    if args.scan_id is None:
        env_scan = os.environ.get("BRKRAW_SCAN_ID")
        if env_scan:
            parts = [p.strip() for p in env_scan.split(",") if p.strip()]
            try:
                args.scan_id = [int(p) for p in parts]
            except ValueError:
                logger.error("Invalid BRKRAW_SCAN_ID: %s", env_scan)
                return 2
    if not Path(args.path).exists():
        logger.error("Path not found: %s", args.path)
        return 2
    loader = load(args.path, prefix="Loading")
    width = config_core.output_width(root=args.root)
    text = loader.info(
        scope=args.scope,
        scan_id=args.scan_id,
        as_dict=False,
        scan_transpose=True,
        show_reco=args.show_reco,
        width=width,
    )
    if text is not None:
        logger.info("%s", text)
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
    info_parser = subparsers.add_parser(
        "info",
        help="Show scan/study info from a dataset path.",
    )
    info_parser.add_argument("path", nargs="?", help="Path to the Bruker study.")
    info_parser.add_argument(
        "--scope",
        choices=["full", "study", "scan"],
        default="full",
        help="Select info scope (default: full).",
    )
    info_parser.add_argument(
        "-s",
        "--scan-id",
        nargs="*",
        type=int,
        help="Scan id(s) to include when scope is scan/full.",
    )
    info_parser.add_argument(
        "--show-reco",
        action="store_true",
        help="Include reco entries in output.",
    )
    info_parser.add_argument(
        "--root",
        help="Override config root directory (default: BRKRAW_CONFIG_HOME or ~/.brkraw).",
    )
    info_parser.set_defaults(func=cmd_info, parser=info_parser)
