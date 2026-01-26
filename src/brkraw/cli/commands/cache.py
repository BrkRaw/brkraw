from __future__ import annotations

import argparse
import logging
from typing import Optional

from ...core import cache

logger = logging.getLogger(__name__)


def cmd_cache(args: argparse.Namespace) -> int:
    handler = getattr(args, "cache_func", None)
    if handler is None:
        args.parser.print_help()
        return 2
    return handler(args)


def cmd_info(args: argparse.Namespace) -> int:
    info = cache.get_info(root=args.root)
    path = info["path"]
    size = info["size"]
    count = info["count"]

    # Format size
    unit = "B"
    size_f = float(size)
    for u in ["B", "KB", "MB", "GB", "TB"]:
        unit = u
        if size_f < 1024:
            break
        size_f /= 1024

    print(f"Path:  {path}")
    print(f"Size:  {size_f:.2f} {unit}")
    print(f"Files: {count}")
    return 0


def cmd_clear(args: argparse.Namespace) -> int:
    if not args.yes:
        info = cache.get_info(root=args.root)
        if info["count"] == 0:
            print("Cache is already empty.")
            return 0
        path = info["path"]
        prompt = f"Clear {info['count']} files from {path}? [y/N]: "
        try:
            reply = input(prompt).strip().lower()
        except EOFError:
            reply = ""
        if reply not in {"y", "yes"}:
            return 1
    
    cache.clear(root=args.root)
    print("Cache cleared.")
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
    cache_parser = subparsers.add_parser(
        "cache",
        help="Manage brkraw cache.",
    )
    cache_parser.add_argument(
        "--root",
        help="Override config root directory (default: BRKRAW_CONFIG_HOME or ~/.brkraw).",
    )
    cache_parser.set_defaults(func=cmd_cache, parser=cache_parser)
    cache_sub = cache_parser.add_subparsers(dest="cache_command")

    info_parser = cache_sub.add_parser("info", help="Show cache information.")
    info_parser.set_defaults(cache_func=cmd_info)

    clear_parser = cache_sub.add_parser("clear", help="Clear cache contents.")
    clear_parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Do not prompt for confirmation.",
    )
    clear_parser.set_defaults(cache_func=cmd_clear)
