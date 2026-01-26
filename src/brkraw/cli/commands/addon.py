from __future__ import annotations
from typing import Dict, Optional

import argparse
import logging
import shlex
import subprocess
from pathlib import Path
from brkraw.core import config as config_core
from brkraw.core import formatter
from brkraw.apps import addon as addon_app

logger = logging.getLogger(__name__)


def cmd_addon(args: argparse.Namespace) -> int:
    handler = getattr(args, "addon_func", None)
    if handler is None:
        args.parser.print_help()
        return 2
    return handler(args)


def _normalize_row(row: Dict[str, str]) -> Dict[str, object]:
    name = row.get("name", "")
    desc = row.get("description", "")
    category = row.get("category", "")
    version = row.get("version", "")
    name_cell: object = name
    desc_cell: object = desc
    category_cell: object = category
    version_cell: object = version
    if row.get("name_unknown") == "1":
        name_cell = {"value": name, "color": "gray"}
    if row.get("version_unknown") == "1":
        version_cell = {"value": version, "color": "gray"}
    if row.get("description_unknown") == "1":
        desc_cell = {"value": desc, "color": "gray"}
    if row.get("category_unknown") == "1":
        category_cell = {"value": category, "color": "gray"}
    return {
        "file": row.get("file", ""),
        "category": category_cell,
        "name": name_cell,
        "version": version_cell,
        "description": desc_cell,
    }

def _normalize_pruner_row(row: Dict[str, str]) -> Dict[str, object]:
    name = row.get("name", "")
    desc = row.get("description", "")
    version = row.get("version", "")
    name_cell: object = name
    desc_cell: object = desc
    version_cell: object = version
    if row.get("name_unknown") == "1":
        name_cell = {"value": name, "color": "gray"}
    if row.get("version_unknown") == "1":
        version_cell = {"value": version, "color": "gray"}
    if row.get("description_unknown") == "1":
        desc_cell = {"value": desc, "color": "gray"}
    return {
        "file": row.get("file", ""),
        "name": name_cell,
        "version": version_cell,
        "description": desc_cell,
    }


def _normalize_rule_row(row: Dict[str, str]) -> Dict[str, object]:
    name = row.get("name", "")
    desc = row.get("description", "")
    category = row.get("category", "")
    name_cell: object = name
    desc_cell: object = desc
    category_cell: object = category
    if row.get("name_unknown") == "1":
        name_cell = {"value": name, "color": "gray"}
    if row.get("description_unknown") == "1":
        desc_cell = {"value": desc, "color": "gray"}
    if row.get("category_unknown") == "1":
        category_cell = {"value": category, "color": "gray"}
    return {
        "file": row.get("file", ""),
        "category": category_cell,
        "name": name_cell,
        "description": desc_cell,
    }


def _normalize_transform_row(row: Dict[str, str]) -> Dict[str, object]:
    spec = row.get("spec", "")
    spec_cell: object = spec
    if row.get("spec_unknown") == "1":
        spec_cell = {"value": spec, "color": "gray"}
    return {
        "file": row.get("file", ""),
        "spec": spec_cell,
    }


def cmd_add(args: argparse.Namespace) -> int:
    installed = addon_app.add(args.filename, root=args.root)
    logger.info("Installed %d file(s).", len(installed))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    data = addon_app.list_installed(root=args.root)
    width = config_core.output_width(root=args.root)
    rules = data["rules"]
    pruner_specs = data.get("pruner_specs", [])
    columns = ("file", "category", "name", "version", "description")
    pruner_columns = ("file", "name", "version", "description")
    rule_columns = ("file", "category", "name", "description")
    transform_columns = ("file", "spec")
    spec_rows = [_normalize_row(row) for row in data["specs"]]
    pruner_rows = [_normalize_pruner_row(row) for row in pruner_specs]
    rules_rows = [_normalize_rule_row(row) for row in rules]
    transform_rows = [_normalize_transform_row(row) for row in data["transforms"]]
    category_order = {"info_spec": 0, "metadata_spec": 1, "converter_hook": 2, "<Unknown>": 9}
    spec_rows.sort(
        key=lambda row: (
            category_order.get(str(row.get("category", "")), 9),
            str(row.get("name", "")),
        )
    )
    pruner_rows.sort(
        key=lambda row: (
            str(row.get("name", "")),
            str(row.get("version", "")),
        )
    )
    spec_widths = formatter.compute_column_widths(columns, spec_rows)
    col_widths = formatter.compute_column_widths(columns, spec_rows)
    pruner_widths = formatter.compute_column_widths(pruner_columns, pruner_rows)
    spec_table = formatter.format_table(
        "Specs",
        columns,
        spec_rows,
        width=width,
        colors={"file": "gray", "name": "cyan", "description": "gray"},
        title_color="cyan",
        col_widths=col_widths,
    )
    rules_table = formatter.format_table(
        "Rules",
        rule_columns,
        rules_rows,
        width=width,
        colors={"file": "gray", "name": "yellow", "description": "gray"},
        title_color="yellow",
        col_widths=formatter.compute_column_widths(rule_columns, rules_rows),
    )
    pruner_table = formatter.format_table(
        "Pruner Specs",
        pruner_columns,
        pruner_rows,
        width=width,
        colors={"file": "gray", "name": "magenta", "description": "gray"},
        title_color="magenta",
        col_widths=pruner_widths,
        min_last_col_width=40,
    )
    transforms_table = formatter.format_table(
        "Transforms",
        transform_columns,
        transform_rows,
        width=width,
        colors={"file": "gray", "spec": "cyan"},
        title_color="cyan",
    )
    logger.info("%s", rules_table)
    logger.info("")
    logger.info("%s", spec_table)
    if pruner_rows:
        logger.info("")
        logger.info("%s", pruner_table)
    if transform_rows:
        logger.info("")
        logger.info("%s", transforms_table)
    return 0


def cmd_rm(args: argparse.Namespace) -> int:
    try:
        removed = addon_app.remove(
            args.filename,
            root=args.root,
            kind=args.kind,
            force=args.force,
        )
    except FileNotFoundError as exc:
        logger.error("No matching addon files found: %s", exc)
        return 2
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 2
    logger.info("Removed %d file(s).", len(removed))
    return 0




def cmd_edit(args: argparse.Namespace) -> int:
    editor = config_core.resolve_editor_binary(root=args.root)
    if not editor:
        logger.error("No editor configured. Set editor or $EDITOR.")
        return 2
    paths = config_core.paths(root=args.root)
    target = _resolve_edit_target(
        args.target,
        kind=args.kind,
        category=args.category,
        root=args.root,
        paths=paths,
    )
    cmd = shlex.split(editor) + [str(target)]
    return subprocess.call(cmd)


def _resolve_edit_target(
    target: str,
    *,
    kind: Optional[str],
    category: Optional[str],
    root: Optional[str],
    paths: config_core.ConfigPaths,
) -> Path:
    candidate = Path(target).expanduser()
    if candidate.exists():
        return candidate.resolve()
    if kind == "spec":
        return addon_app.resolve_spec_reference(target, category=category, root=root)
    if kind == "pruner":
        return addon_app.resolve_pruner_spec_reference(target, root=root)
    if kind == "rule":
        return _resolve_rule_target(target, category=category, rules_dir=paths.rules_dir)
    if kind == "transform":
        return (paths.transforms_dir / target).resolve()
    transform_candidate = (paths.transforms_dir / target).resolve()
    if transform_candidate.exists():
        return transform_candidate
    pruner_candidate = (paths.pruner_specs_dir / target).resolve()
    if pruner_candidate.exists():
        return pruner_candidate
    try:
        return addon_app.resolve_spec_reference(target, category=category, root=root)
    except Exception:
        try:
            return addon_app.resolve_pruner_spec_reference(target, root=root)
        except Exception:
            return _resolve_rule_target(target, category=category, rules_dir=paths.rules_dir)


def _resolve_spec_path(target: str, *, category: Optional[str], root: Optional[str]) -> Path:
    return addon_app.resolve_spec_reference(target, category=category, root=root)


def _resolve_rule_target(target: str, *, category: Optional[str], rules_dir: Path) -> Path:
    candidate = (rules_dir / target).resolve()
    if candidate.exists():
        return candidate
    rules = addon_app.list_installed(root=str(rules_dir.parent)).get("rules", [])
    matches = [
        entry for entry in rules
        if entry.get("name") == target and (category is None or entry.get("category") == category)
    ]
    file_set = {
        file
        for entry in matches
        if isinstance((file := entry.get("file")), str) and file
    }
    files = sorted(file_set)
    if len(files) == 1:
        return (rules_dir / files[0]).resolve()
    if not files:
        raise FileNotFoundError(target)
    raise ValueError(f"Multiple rule files match {target}: {', '.join(files)}")


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
    addon_parser = subparsers.add_parser(
        "addon",
        help="Manage info specs and rules.",
    )
    addon_parser.add_argument(
        "--root",
        help="Override config root directory (default: BRKRAW_CONFIG_HOME or ~/.brkraw).",
    )
    addon_parser.set_defaults(func=cmd_addon, parser=addon_parser)
    addon_sub = addon_parser.add_subparsers(dest="addon_command")

    add_parser = addon_sub.add_parser("add", help="Install a spec or rule file.")
    add_parser.add_argument("filename", help="Spec/rule YAML.")
    add_parser.set_defaults(addon_func=cmd_add)

    list_parser = addon_sub.add_parser("list", help="List installed specs and rules.")
    list_parser.set_defaults(addon_func=cmd_list)

    rm_parser = addon_sub.add_parser("rm", help="Remove an installed spec or rule file.")
    rm_parser.add_argument("filename", help="Spec/rule filename to remove.")
    rm_parser.add_argument(
        "--kind",
        choices=["spec", "pruner", "rule", "transform"],
        help="Limit removal to a specific kind.",
    )
    rm_parser.add_argument(
        "--force",
        action="store_true",
        help="Remove even if dependencies are detected.",
    )
    rm_parser.set_defaults(addon_func=cmd_rm)


    edit_parser = addon_sub.add_parser("edit", help="Edit an installed spec or rule.")
    edit_parser.add_argument("target", help="Spec/rule name or filename.")
    edit_parser.add_argument(
        "--kind",
        choices=["spec", "pruner", "rule", "transform"],
        help="Target kind (default: auto-detect).",
    )
    edit_parser.add_argument(
        "--category",
        help="Spec/rule category hint (e.g. info_spec, metadata_spec).",
    )
    edit_parser.set_defaults(addon_func=cmd_edit)
