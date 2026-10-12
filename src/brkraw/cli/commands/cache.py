from __future__ import annotations

import argparse
import logging
from typing import Optional

from ...core import cache
from ..cache_check import entry_label, entry_table, format_size

logger = logging.getLogger(__name__)


def cmd_cache(args: argparse.Namespace) -> int:
    handler = getattr(args, "cache_func", None)
    if handler is None:
        args.parser.print_help()
        return 2
    return handler(args)


def cmd_info(args: argparse.Namespace) -> int:
    info = cache.get_info(root=args.root, by_entry=True)
    print(f"Path:  {info['path']}")
    print(f"Size:  {format_size(info['size'])}")
    print(f"Files: {info['count']}")
    lines = entry_table(info["entries"])
    if lines:
        print("Entries:")
        for line in lines:
            print(line)
    return 0


def _ask(prompt: str) -> bool:
    try:
        reply = input(prompt).strip().lower()
    except EOFError:
        reply = ""
    return reply in {"y", "yes"}


def cmd_clear(args: argparse.Namespace) -> int:
    only = getattr(args, "only", None)
    if only:
        info = cache.get_info(root=args.root, by_entry=True)
        # a real subfolder named like the loose-files group cannot be chosen by name:
        # FILES_ENTRY always means the loose files (wi-0074-choi-2 finding 1)
        by_name = {e["name"]: e for e in info["entries"]
                   if not (e["is_dir"] and e["name"] == cache.FILES_ENTRY)}
        unknown = [name for name in only if name not in by_name]
        if unknown:
            known = ", ".join(entry_label(e) for e in info["entries"]) or "none"
            logger.error("No cache entry %s in %s (entries: %s); nothing was deleted.",
                         ", ".join(repr(n) for n in unknown), info["path"], known)
            return 1
        chosen = [by_name[name] for name in dict.fromkeys(only)]
        if not args.yes:
            names = ", ".join(entry_label(e) for e in chosen)
            size = sum(int(e["size"]) for e in chosen)
            count = sum(int(e["count"]) for e in chosen)
            if not _ask(f"Clear {names} ({format_size(size)}, {count} files) from {info['path']}? [y/N]: "):
                return 1
        try:
            cache.clear(root=args.root, only=[e["name"] for e in chosen])
        except ValueError as exc:
            logger.error("%s; nothing was deleted.", exc)
            return 1
        print(f"Cleared {', '.join(entry_label(e) for e in chosen)}.")
        return 0

    if not args.yes:
        info = cache.get_info(root=args.root)
        if info["count"] == 0:
            print("Cache is already empty.")
            return 0
        path = info["path"]
        if not _ask(f"Clear {info['count']} files from {path}? [y/N]: "):
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

    info_parser = cache_sub.add_parser(
        "info", help="Show cache information (total and one line per subfolder).")
    info_parser.set_defaults(cache_func=cmd_info)

    clear_parser = cache_sub.add_parser("clear", help="Clear cache contents.")
    clear_parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Do not prompt for confirmation.",
    )
    clear_parser.add_argument(
        "--only",
        action="append",
        metavar="NAME",
        help=(f"Clear only this entry: a subfolder name such as 'sordino', or '{cache.FILES_ENTRY}' "
              "for the files directly in the cache folder (see 'brkraw cache info'). Repeat for more."),
    )
    clear_parser.set_defaults(cache_func=cmd_clear)
