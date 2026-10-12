from __future__ import annotations

import os
import argparse
import sys
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple
from ..core.entrypoints import list_entry_points as _iter_entry_points

from brkraw import __version__
from brkraw.core import config as config_core
from brkraw.cli import cache_check, pvcmd

PLUGIN_GROUP = "brkraw.cli"
HELP_CATEGORY_ORDER = ("Data", "Workspace", "Extensions")

# The one table of brkraw's own commands: help group and order in `brkraw -h`
# and in the parser's command list. Plugin commands follow, in load order.
CORE_COMMANDS: Tuple[Tuple[str, str], ...] = (
    ("info", "Data"),
    ("params", "Data"),
    ("convert", "Data"),
    ("prune", "Data"),
    ("init", "Workspace"),
    ("config", "Workspace"),
    ("cache", "Workspace"),
    ("session", "Workspace"),
    ("addon", "Extensions"),
    ("hook", "Extensions"),
)
HELP_COMMAND_ORDER: Dict[str, int] = {name: index for index, (name, _) in enumerate(CORE_COMMANDS)}
HELP_CATEGORY_BY_COMMAND: Dict[str, str] = dict(CORE_COMMANDS)

HELP_EPILOG = """\
Get started:
  brkraw init                              create the config folder
  brkraw info /path/to/study               what is in the study
  brkraw convert /path/to/study -s 3       convert scan 3 to NIfTI
  brkraw prune /path/to/study --dry-run    what a zip of the study would hold

For details on a command, run: brkraw <command> -h
Documentation: https://brkraw.github.io/"""


def order_commands(names: Iterable[str]) -> List[str]:
    """Core commands in ``CORE_COMMANDS`` order, then the other names as given."""
    given = list(names)
    core_names = [name for name, _ in CORE_COMMANDS]
    result = [name for name in core_names if name in given]
    core_set = set(core_names)
    result += [name for name in given if name not in core_set]
    return result


def _apply_root(args: argparse.Namespace) -> bool:
    """Use ``--root DIR`` as the config folder for the whole run (wins over BRKRAW_CONFIG_HOME)."""
    root = getattr(args, "root", None)
    if not root:
        return False
    os.environ[config_core.ENV_CONFIG_HOME] = str(Path(root).expanduser())
    return True

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

    ordered = order_commands(subparsers.choices.keys())
    subparsers.choices = {name: subparsers.choices[name] for name in ordered}
    choices_actions = getattr(subparsers, "_choices_actions", None)
    if choices_actions:
        action_map = {action.dest: action for action in choices_actions}
        ordered_actions = [action_map[name] for name in ordered if name in action_map]
        ordered_actions += [
            action for action in choices_actions if action.dest not in ordered
        ]
        subparsers._choices_actions = ordered_actions  # type: ignore[attr-defined]


def _help_category_for_command(name: str, parser: argparse.ArgumentParser) -> str:
    category = getattr(parser, "_brkraw_help_category", None)
    if isinstance(category, str) and category.strip():
        return category.strip()

    category = getattr(parser, "help_category", None)
    if isinstance(category, str) and category.strip():
        return category.strip()

    return HELP_CATEGORY_BY_COMMAND.get(name, "Extensions")


def _help_order_for_command(name: str) -> Tuple[int, str]:
    return (HELP_COMMAND_ORDER.get(name, 999), name)


def _render_help(
    parser: argparse.ArgumentParser,
    subparsers: argparse._SubParsersAction,  # type: ignore[name-defined]
) -> str:
    formatter = parser._get_formatter()
    formatter.add_usage(parser.usage, parser._actions, parser._mutually_exclusive_groups)
    if parser.description is not None:
        formatter.add_text(parser.description)

    option_groups = [group for group in parser._action_groups if group.title == "options"]
    for group in option_groups:
        formatter.start_section(group.title)
        if group.description is not None:
            formatter.add_text(group.description)
        formatter.add_arguments(
            action
            for action in group._group_actions
            if action is not subparsers
        )
        formatter.end_section()

    actions_by_name = {action.dest: action for action in getattr(subparsers, "_choices_actions", [])}
    grouped: Dict[str, List[argparse.Action]] = {}
    for name, action in actions_by_name.items():
        command_parser = subparsers.choices.get(name)
        if command_parser is None:
            continue
        category = _help_category_for_command(name, command_parser)
        grouped.setdefault(category, []).append(action)

    categories = [category for category in HELP_CATEGORY_ORDER if category in grouped]
    categories.extend(sorted(category for category in grouped if category not in HELP_CATEGORY_ORDER))

    for category in categories:
        formatter.start_section(category)
        formatter.add_arguments(sorted(grouped[category], key=lambda action: _help_order_for_command(action.dest)))
        formatter.end_section()

    formatter.add_text(parser.epilog)
    return formatter.format_help()


def _print_help(
    parser: argparse.ArgumentParser,
    subparsers: argparse._SubParsersAction,  # type: ignore[name-defined]
) -> None:
    print(_render_help(parser, subparsers), end="")


def build_parser() -> Tuple[argparse.ArgumentParser, "argparse._SubParsersAction"]:  # type: ignore[name-defined]
    """Build the ``brkraw`` parser with every registered command (core and plugins)."""
    parser = argparse.ArgumentParser(
        prog="brkraw",
        description="BrkRaw command-line interface.",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,  # keep the epilog's lines
    )
    parser.add_argument(
        "-v", "--version", action="version", version="%(prog)s v{}".format(__version__)
    )

    subparsers = parser.add_subparsers(
        title="Commands",
        description=(
            "Choose one of the commands below. For details on a command, "
            "run: brkraw <command> -h."
        ),
        dest="command",
        metavar="command",
    )

    _register_entry_point_commands(subparsers)
    return parser, subparsers


def main(argv: Optional[List[str]] = None) -> int:
    config_core.configure_logging()
    parser, subparsers = build_parser()

    argv_list = list(sys.argv[1:] if argv is None else argv)
    if not argv_list:
        _print_help(parser, subparsers)
        return 2
    if argv_list[0] in {"-h", "--help"}:
        _print_help(parser, subparsers)
        return 0

    args = parser.parse_args(argv_list)
    if not hasattr(args, "func"):
        _print_help(parser, subparsers)
        return 2
    if _apply_root(args):
        # logging settings come from the chosen config folder
        config_core.configure_logging()
    # Only after parsing: -h/--version never get here, and only commands whose
    # dataset path is empty ask ParaVision (BRK-0030 ①, BRK-0031 ③).
    pvcmd.autoset_path_from_paravision(args)
    # A cache larger than cache.warn_size_gb: warn, and in a terminal offer to
    # clear it entry by entry (WI-0074). run_check never raises, so the command
    # always runs and keeps its own result.
    cache_check.run_check(getattr(args, "command", None))
    func: Callable[[argparse.Namespace], int] = args.func
    return func(args)


if __name__ == "__main__":
    raise SystemExit(main())
