from __future__ import annotations
from typing import List, Tuple, Optional

import argparse
import logging
from pathlib import Path

import yaml
import shlex
import subprocess

from brkraw.core import config as config_core

logger = logging.getLogger(__name__)


def cmd_config(args: argparse.Namespace) -> int:
    handler = getattr(args, "config_func", None)
    if handler is None:
        args.parser.print_help()
        return 2
    return handler(args)


def cmd_init(args: argparse.Namespace) -> int:
    config_core.init(
        root=args.root,
        create_config=not args.no_config,
        exist_ok=not args.no_exist_ok,
    )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    config = config_core.resolve_config(root=args.root)
    if not config:
        print("config.yaml: <empty>")
        return 0
    ordered = _order_config(config)
    text = yaml.safe_dump(ordered, sort_keys=False)
    print(text.rstrip())
    return 0


def cmd_path(args: argparse.Namespace) -> int:
    path = config_core.get_path(args.name, root=args.root)
    print(path)
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    config = config_core.load(root=args.root) or {}
    key, value = _parse_set_kv(args.key, args.value)
    if "." in key:
        _set_nested(config, key.split("."), value)
    else:
        config[key] = value
    config_core.write_config(config, root=args.root)
    return 0


def cmd_unset(args: argparse.Namespace) -> int:
    config = config_core.load(root=args.root) or {}
    if "." in args.key:
        _unset_nested(config, args.key.split("."))
    elif args.key in config:
        config.pop(args.key)
    config_core.write_config(config, root=args.root)
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    paths = config_core.paths(root=args.root)
    if paths.config_file.exists() and not args.yes:
        prompt = f"Reset config.yaml at {paths.config_file}? [y/N]: "
        reply = input(prompt).strip().lower()
        if reply not in {"y", "yes"}:
            return 1
    config_core.reset_config(root=args.root)
    return 0


def cmd_edit(args: argparse.Namespace) -> int:
    editor = config_core.resolve_editor_binary(root=args.root)
    if not editor:
        logger.error("No editor configured. Set editor or $EDITOR.")
        return 2
    paths = config_core.paths(root=args.root)
    if not paths.config_file.exists():
        config_core.reset_config(root=args.root)
    cmd = shlex.split(editor) + [str(paths.config_file)]
    return subprocess.call(cmd)


def _parse_set_kv(key: str, value: Optional[str]) -> Tuple[str, object]:
    if value is None and "=" in key:
        key, value = key.split("=", 1)
    if value is None:
        raise ValueError("config set requires KEY VALUE or KEY=VALUE.")
    return key, yaml.safe_load(value)


def _format_config_value(value: object) -> str:
    if isinstance(value, (dict, list, tuple)):
        return yaml.safe_dump(value, default_flow_style=True).strip()
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _order_config(config: dict) -> dict:
    order = ["config_version", "editor", "logging", "output"]
    ordered = {key: config[key] for key in order if key in config}
    for key in sorted(k for k in config.keys() if k not in ordered):
        ordered[key] = config[key]
    return ordered


def _set_nested(data: dict, parts: List[str], value: object) -> None:
    current = data
    for part in parts[:-1]:
        node = current.get(part)
        if not isinstance(node, dict):
            node = {}
            current[part] = node
        current = node
    current[parts[-1]] = value


def _unset_nested(data: dict, parts: List[str]) -> None:
    current = data
    stack = []
    for part in parts[:-1]:
        node = current.get(part)
        if not isinstance(node, dict):
            return
        stack.append((current, part))
        current = node
    if parts[-1] in current:
        current.pop(parts[-1])
    for parent, key in reversed(stack):
        child = parent.get(key)
        if isinstance(child, dict) and not child:
            parent.pop(key)
        else:
            break


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
    config_parser = subparsers.add_parser(
        "config",
        help="Manage brkraw config locations.",
    )
    config_parser.add_argument(
        "--root",
        help="Override config root directory (default: BRKRAW_CONFIG_HOME or ~/.brkraw).",
    )
    config_parser.set_defaults(func=cmd_config, parser=config_parser)
    config_sub = config_parser.add_subparsers(dest="config_command")

    init_parser = config_sub.add_parser("init", help="Create the config folders.")
    init_parser.add_argument(
        "--no-config",
        action="store_true",
        help="Do not create config.yaml.",
    )
    init_parser.add_argument(
        "--no-exist-ok",
        action="store_true",
        help="Fail if the root directory already exists.",
    )
    init_parser.set_defaults(config_func=cmd_init)

    show_parser = config_sub.add_parser("show", help="Print resolved config values.")
    show_parser.set_defaults(config_func=cmd_show)

    path_parser = config_sub.add_parser("path", help="Print a specific config path.")
    path_parser.add_argument(
        "name",
        choices=["root", "config", "rules", "specs", "transforms", "cache"],
        help="Path key to print.",
    )
    path_parser.set_defaults(config_func=cmd_path)

    edit_parser = config_sub.add_parser("edit", help="Edit config.yaml in an editor.")
    edit_parser.set_defaults(config_func=cmd_edit)

    set_parser = config_sub.add_parser("set", help="Set a config key.")
    set_parser.add_argument("key", help="Config key to set (or KEY=VALUE).")
    set_parser.add_argument("value", nargs="?", help="Value to set.")
    set_parser.set_defaults(config_func=cmd_set)

    unset_parser = config_sub.add_parser("unset", help="Unset a config key.")
    unset_parser.add_argument("key", help="Config key to remove.")
    unset_parser.set_defaults(config_func=cmd_unset)

    reset_parser = config_sub.add_parser("reset", help="Reset config.yaml to defaults.")
    reset_parser.add_argument(
        "--yes",
        action="store_true",
        help="Do not prompt for confirmation.",
    )
    reset_parser.set_defaults(config_func=cmd_reset)
