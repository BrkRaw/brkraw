from __future__ import annotations
from typing import Optional, Dict, Any
from pprint import pprint

import argparse
import logging
import os
from datetime import date
from pathlib import Path

import yaml

from brkraw.core import config as config_core
from brkraw.apps import addon as addon_app

logger = logging.getLogger(__name__)


def cmd_init(args: argparse.Namespace) -> int:
    if args.config:
        config_core.init(
            root=args.root,
            create_config=False,
            exist_ok=not args.no_exist_ok,
        )
        paths = config_core.paths(root=args.root)
        existing = config_core.load(root=args.root)
        if paths.config_file.exists():
            pprint(existing or {})
            replace = _prompt_bool(
                "Replace existing config.yaml?",
                default=False,
            )
            if not replace:
                return 0
            defaults = existing
        else:
            defaults = config_core.default_config()
        config_values = _prompt_config_values(defaults=defaults)
        config_core.write_config(config_values, root=args.root)
        logger.info("Wrote config at %s", config_core.paths(root=args.root).config_file)
        return 0

    interactive = not args.yes
    create_config = True
    install_defaults = args.install_default
    shellrc = Path(args.shellrc) if args.shellrc else _default_shell_rc()
    explicit_actions = args.install_default or args.shellrc
    config_values: Optional[Dict[str, Any]] = None

    if interactive and explicit_actions:
        interactive = False
        create_config = False
        install_defaults = args.install_default
        shellrc = Path(args.shellrc) if args.shellrc else None

    if interactive:
        create_config = _prompt_bool("Create config.yaml?", default=create_config)
        if create_config:
            config_values = _prompt_config_values()
        install_defaults = _prompt_bool(
            "Install default specs/rules?", default=install_defaults
        )
        install_helpers = _prompt_bool(
            "Install shell helpers?", default=shellrc is not None
        )
        if install_helpers:
            if shellrc is None:
                shellrc = _prompt_path("Shell rc path", default=None)
            if shellrc is not None:
                _install_shell_helpers(shellrc)
        else:
            shellrc = None

    config_core.init(
        root=args.root,
        create_config=False,
        exist_ok=not args.no_exist_ok,
    )
    logger.info("Initialized config at %s", config_core.paths(root=args.root).root)
    if create_config:
        if config_values is None:
            config_values = config_core.default_config()
        config_core.write_config(config_values, root=args.root)
    if install_defaults:
        installed = addon_app.install_defaults(root=args.root)
        if installed:
            logger.info("Installed %d default file(s).", len(installed))
    if not interactive and shellrc is not None:
        _install_shell_helpers(shellrc)
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize config and install defaults.",
    )
    init_parser.add_argument(
        "--root",
        help="Override config root directory (default: BRKRAW_CONFIG_HOME or ~/.brkraw).",
    )
    init_parser.add_argument(
        "--no-exist-ok",
        action="store_true",
        help="Fail if the root directory already exists.",
    )
    init_parser.add_argument(
        "--config",
        action="store_true",
        help="Create or replace config.yaml only.",
    )
    init_parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip prompts and use defaults.",
    )
    init_parser.add_argument(
        "--install-default",
        action="store_true",
        help="Install default specs and rules.",
    )
    init_parser.add_argument(
        "--shell-rc",
        dest="shellrc",
        help="Append shell helpers to the specified rc file (defaults to ~/.zshrc or ~/.bashrc).",
    )
    init_parser.set_defaults(func=cmd_init)


def _prompt_bool(label: str, *, default: bool) -> bool:
    prompt = "Y/n" if default else "y/N"
    while True:
        reply = input(f"{label} [{prompt}]: ").strip().lower()
        if not reply:
            return default
        if reply in {"y", "yes"}:
            return True
        if reply in {"n", "no"}:
            return False


def _prompt_config_values(*, defaults: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base = config_core.default_config()
    if defaults:
        base.update(defaults)
    result: Dict[str, Any] = {}
    keys = list(base.keys())
    for key in keys:
        if key == "config_version":
            result[key] = base.get(key)
            continue
        default = base.get(key)
        display = "null" if default is None else str(default)
        reply = input(f"{key} [{display}]: ").strip()
        if reply == "":
            result[key] = default
        else:
            result[key] = yaml.safe_load(reply)
    return result


def _prompt_path(label: str, *, default: Optional[Path]) -> Optional[Path]:
    display = str(default) if default else ""
    reply = input(f"{label} [{display}]: ").strip()
    if not reply:
        return default
    return Path(reply).expanduser()


def _install_shell_helpers(path: Path) -> None:
    marker = "# brkraw shell helpers"
    snippet = "\n".join(
        [
            f"{marker} (added {date.today().isoformat()})",
            "brkraw-set() {",
            "  if [ \"$#\" -eq 0 ]; then",
            "    brkraw session set",
            "  else",
            "    eval \"$(brkraw session set \"$@\")\"",
            "  fi",
            "}",
            "brkraw-unset() {",
            "  if [ \"$#\" -eq 0 ]; then",
            "    eval \"$(brkraw session unset)\"",
            "  elif [ \"$1\" = \"-h\" ] || [ \"$1\" = \"--help\" ]; then",
            "    brkraw session unset \"$@\"",
            "  else",
            "    eval \"$(brkraw session unset \"$@\")\"",
            "  fi",
            "}",
            "",
        ]
    )
    if path.exists():
        content = path.read_text(encoding="utf-8")
        if marker in content:
            logger.info("Shell helpers already present in %s", path)
            return
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = ""
    path.write_text(content + ("\n" if content and not content.endswith("\n") else "") + snippet, encoding="utf-8")
    logger.info("Appended shell helpers to %s", path)


def _default_shell_rc() -> Optional[Path]:
    shell = os.environ.get("SHELL", "")
    home = Path.home()
    if shell.endswith("zsh"):
        return home / ".zshrc"
    if shell.endswith("bash"):
        return home / ".bashrc"
    return None
