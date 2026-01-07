from __future__ import annotations

import argparse
from typing import Callable, List, Optional
from ..core.entrypoints import list_entry_points as _iter_entry_points

from brkraw import __version__
from brkraw.core import config as config_core

PLUGIN_GROUP = "brkraw.cli"


def _register_entry_point_commands(
    subparsers: argparse._SubParsersAction,  # type: ignore[name-defined]
) -> None:
    for ep in _iter_entry_points(PLUGIN_GROUP):
        try:
            register = ep.load()
        except Exception as exc:  # noqa: BLE001 - best-effort plugin load
            print(f"warning: failed to load entry point {ep.name!r}: {exc}")
            continue
        if not callable(register):
            raise TypeError("entry point must be callable (register(subparsers)).")
        register(subparsers)

    preferred = [
        "init",
        "config",
        "session",
        "info",
        "params",
        "convert",
        "convert-batch",
        "prune",
        "addon",
        "hook",
    ]
    preferred_set = set(preferred)
    ordered = [name for name in preferred if name in subparsers.choices]
    ordered += [name for name in subparsers.choices if name not in preferred_set]
    subparsers.choices = {name: subparsers.choices[name] for name in ordered}
    choices_actions = getattr(subparsers, "_choices_actions", None)
    if choices_actions:
        action_map = {action.dest: action for action in choices_actions}
        ordered_actions = [action_map[name] for name in ordered if name in action_map]
        ordered_actions += [
            action for action in choices_actions if action.dest not in ordered
        ]
        subparsers._choices_actions = ordered_actions  # type: ignore[attr-defined]


def main(argv: Optional[List[str]] = None) -> int:
    config_core.configure_logging()
    parser = argparse.ArgumentParser(
        prog="brkraw",
        description="BrkRaw command-line interface.",
    )
    parser.add_argument(
        "-v", "--version", action="version", version="%(prog)s v{}".format(__version__)
    )

    subparsers = parser.add_subparsers(
        title="Sub-commands",
        description=(
            "Choose one of the sub-commands below. For details on a specific "
            "command, run: brkraw <command> -h."
        ),
        dest="command",
        metavar="command",
    )

    _register_entry_point_commands(subparsers)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    func: Callable[[argparse.Namespace], int] = args.func
    return func(args)


if __name__ == "__main__":
    raise SystemExit(main())
