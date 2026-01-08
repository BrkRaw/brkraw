from __future__ import annotations

from typing import Dict

import argparse
import logging

from brkraw.apps import hook as hook_app
from brkraw.core import config as config_core
from brkraw.core import formatter

logger = logging.getLogger("brkraw")


def cmd_hook(args: argparse.Namespace) -> int:
    handler = getattr(args, "hook_func", None)
    if handler is None:
        args.parser.print_help()
        return 2
    return handler(args)


def _normalize_row(row: Dict[str, str]) -> Dict[str, object]:
    name = row.get("name", "")
    version = row.get("version", "")
    entrypoints = row.get("entrypoints", "")
    description = row.get("description", "")
    install_status = row.get("install_status", "")
    name_cell: object = name
    version_cell: object = version
    entrypoints_cell: object = entrypoints
    description_cell: object = description
    install_cell: object = install_status
    if row.get("name_unknown") == "1":
        name_cell = {"value": name, "color": "gray"}
    if row.get("version_unknown") == "1":
        version_cell = {"value": version, "color": "gray"}
    if row.get("entrypoints_unknown") == "1":
        entrypoints_cell = {"value": entrypoints, "color": "gray"}
    if row.get("description_unknown") == "1":
        description_cell = {"value": description, "color": "gray"}
    if row.get("install_status_color"):
        install_cell = {"value": install_status, "color": row["install_status_color"]}
    return {
        "name": name_cell,
        "version": version_cell,
        "entrypoints": entrypoints_cell,
        "description": description_cell,
        "installed": install_cell,
    }


def cmd_list(args: argparse.Namespace) -> int:
    hooks = hook_app.list_hooks(root=args.root)
    width = config_core.output_width(root=args.root)
    rows = []
    for hook in hooks:
        install_status = hook.get("install_status", "No")
        if install_status == "Yes":
            status_color = "green"
        elif install_status == "Partially":
            status_color = "yellow"
        else:
            status_color = "red"
        rows.append(
            _normalize_row(
                {
                    "name": hook.get("name", "<Unknown>"),
                    "version": hook.get("version", "<Unknown>"),
                    "entrypoints": ", ".join(hook.get("entrypoints") or []) or "<Unknown>",
                    "description": hook.get("description", "<Unknown>"),
                    "install_status": install_status,
                    "install_status_color": status_color,
                    "name_unknown": "1" if hook.get("name") in (None, "<Unknown>") else "0",
                    "version_unknown": "1" if hook.get("version") in (None, "<Unknown>") else "0",
                    "entrypoints_unknown": "1"
                    if not hook.get("entrypoints")
                    else "0",
                    "description_unknown": "1"
                    if hook.get("description") in (None, "<Unknown>")
                    else "0",
                }
            )
        )
    columns = ("name", "version", "installed", "entrypoints", "description")
    table = formatter.format_table(
        "Hooks",
        columns,
        rows,
        width=width,
        colors={"name": "cyan", "description": "gray", "entrypoints": "yellow"},
        title_color="cyan",
        col_widths=formatter.compute_column_widths(columns, rows),
        min_last_col_width=40,
    )
    logger.info("%s", table)
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    if args.target == "all":
        result = hook_app.install_all(root=args.root, upgrade=args.upgrade, force=args.force)
        logger.info("Installed %d hook(s).", len(result["installed"]))
        if result["skipped"]:
            logger.info("Skipped %d hook(s).", len(result["skipped"]))
        return 0
    status = hook_app.install_hook(
        args.target,
        root=args.root,
        upgrade=args.upgrade,
        force=args.force,
    )
    if status == "installed":
        logger.info("Installed hook: %s", args.target)
    else:
        logger.info("Hook already installed: %s", args.target)
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    try:
        hook_name, removed = hook_app.uninstall_hook(
            args.target,
            root=args.root,
            force=args.force,
        )
    except LookupError as exc:
        logger.error("%s", exc)
        return 2
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 2
    removed_count = sum(len(items) for items in removed.values())
    logger.info("Removed %d file(s).", removed_count)
    logger.info("To uninstall the package, run: pip uninstall %s", hook_name)
    return 0


def cmd_docs(args: argparse.Namespace) -> int:
    try:
        hook_name, text = hook_app.read_hook_docs(args.target, root=args.root)
    except (LookupError, FileNotFoundError) as exc:
        logger.error("%s", exc)
        return 2
    logger.info("[Hook Docs] %s", hook_name)
    if args.render:
        try:
            from rich.console import Console
            from rich.markdown import Markdown
        except Exception:
            logger.warning("rich is not available; printing raw text.")
            print(text)
            return 0
        console = Console()
        console.print(Markdown(text))
        return 0
    print(text)
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
    hook_parser = subparsers.add_parser(
        "hook",
        help="Manage converter hook packages.",
    )
    hook_parser.add_argument(
        "--root",
        help="Override config root directory (default: BRKRAW_CONFIG_HOME or ~/.brkraw).",
    )
    hook_parser.set_defaults(func=cmd_hook, parser=hook_parser)
    hook_sub = hook_parser.add_subparsers(dest="hook_command")

    list_parser = hook_sub.add_parser("list", help="List installed hook packages.")
    list_parser.set_defaults(hook_func=cmd_list)

    install_parser = hook_sub.add_parser("install", help="Install hook addons.")
    install_parser.add_argument("target", help="Hook name or entrypoint name, or 'all'.")
    install_parser.add_argument(
        "--upgrade",
        action="store_true",
        help="Reinstall when a newer version is available.",
    )
    install_parser.add_argument(
        "--force",
        action="store_true",
        help="Reinstall even if the same or older version is installed.",
    )
    install_parser.set_defaults(hook_func=cmd_install)

    uninstall_parser = hook_sub.add_parser("uninstall", help="Remove hook addons.")
    uninstall_parser.add_argument("target", help="Hook name or entrypoint name.")
    uninstall_parser.add_argument(
        "--force",
        action="store_true",
        help="Remove even if dependencies are detected.",
    )
    uninstall_parser.set_defaults(hook_func=cmd_uninstall)

    docs_parser = hook_sub.add_parser("docs", help="Show hook documentation.")
    docs_parser.add_argument("target", help="Hook name or entrypoint name.")
    docs_parser.add_argument(
        "--render",
        action="store_true",
        help="Render markdown using rich (if installed).",
    )
    docs_parser.set_defaults(hook_func=cmd_docs)
