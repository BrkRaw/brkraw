from __future__ import annotations

"""Session command to manage BrkRaw environment defaults."""

import argparse
import os
from pathlib import Path
from typing import Iterable, List, Tuple

from brkraw.apps.loader import BrukerLoader


def _format_export(name: str, value: str) -> str:
    escaped = value.replace("\"", "\\\"")
    return f'export {name}="{escaped}"'


def _format_scan_ids(scan_ids: Iterable[int]) -> str:
    return ",".join(str(sid) for sid in scan_ids)


def _format_param_files(files: Iterable[str]) -> str:
    return ",".join(str(item) for item in files)


def cmd_session(args: argparse.Namespace) -> int:
    handler = getattr(args, "session_func", None)
    if handler is None:
        args.parser.print_help()
        return 2
    return handler(args)


def cmd_set(args: argparse.Namespace) -> int:
    if (
        not args.path
        and not args.scan_id
        and args.reco_id is None
        and not args.param_key
        and not args.param_file
        and not args.convert_option
    ):
        parser = getattr(args, "parser", None)
        if parser is not None:
            print(_format_short_help(parser))
        print("\nTip: run `brkraw init --shell-rc ~/.zshrc` (or ~/.bashrc)")
        print("Then use `brkraw-set ...` and `brkraw-unset` in your shell.")
        print("You can still use `eval \"$(brkraw session set ...)\"` directly.")
        return 2
    lines: List[str] = []
    if args.path:
        path = Path(args.path).expanduser()
        if not path.exists():
            print(f"error: path not found: {path}")
            return 2
        try:
            BrukerLoader(path)
        except Exception as exc:
            print(f"error: failed to load dataset at {path}: {exc}")
            return 2
        lines.append(_format_export("BRKRAW_PATH", str(path.resolve())))
    if args.scan_id:
        lines.append(_format_export("BRKRAW_SCAN_ID", _format_scan_ids(args.scan_id)))
    if args.reco_id is not None:
        lines.append(_format_export("BRKRAW_RECO_ID", str(args.reco_id)))
    if args.param_key:
        lines.append(_format_export("BRKRAW_PARAM_KEY", args.param_key))
    if args.param_file:
        lines.append(_format_export("BRKRAW_PARAM_FILE", _format_param_files(args.param_file)))
    if args.convert_option:
        convert_items: List[str] = []
        for item in args.convert_option:
            if isinstance(item, list):
                convert_items.extend(item)
            else:
                convert_items.append(item)
        for key, value in _parse_convert_options(convert_items):
            lines.append(_format_export(f"BRKRAW_CONVERT_{key}", value))
    if lines:
        print("\n".join(lines))
    return 0


def cmd_unset(args: argparse.Namespace) -> int:
    base_vars = [
        "BRKRAW_PATH",
        "BRKRAW_SCAN_ID",
        "BRKRAW_RECO_ID",
        "BRKRAW_PARAM_KEY",
        "BRKRAW_PARAM_FILE",
    ]
    convert_vars = [
        "BRKRAW_CONVERT_OUTPUT",
        "BRKRAW_CONVERT_PREFIX",
        "BRKRAW_CONVERT_SCAN_ID",
        "BRKRAW_CONVERT_RECO_ID",
        "BRKRAW_CONVERT_SIDECAR",
        "BRKRAW_CONVERT_CONTEXT_MAP",
        "BRKRAW_CONVERT_SPACE",
        "BRKRAW_CONVERT_COMPRESS",
        "BRKRAW_CONVERT_FLATTEN_FG",
        "BRKRAW_CONVERT_OVERRIDE_SUBJECT_TYPE",
        "BRKRAW_CONVERT_OVERRIDE_SUBJECT_POSE",
        "BRKRAW_CONVERT_XYZ_UNITS",
        "BRKRAW_CONVERT_T_UNITS",
        "BRKRAW_CONVERT_HEADER",
    ]
    targets: List[str] = []
    if args.path:
        targets.append("BRKRAW_PATH")
    if args.scan_id:
        targets.append("BRKRAW_SCAN_ID")
    if args.reco_id:
        targets.append("BRKRAW_RECO_ID")
    if args.param_key:
        targets.append("BRKRAW_PARAM_KEY")
    if args.param_file:
        targets.append("BRKRAW_PARAM_FILE")

    if args.convert_option:
        keys: List[str] = []
        for item in args.convert_option:
            if item is None or item == "*":
                keys = ["*"]
                break
            keys.append(item)
        if "*" in keys:
            targets.extend(convert_vars)
        else:
            targets.extend(
                [f"BRKRAW_CONVERT_{key.strip().upper().replace('-', '_')}" for key in keys]
            )

    if not targets:
        targets = base_vars + convert_vars
    print("unset " + " ".join(targets))
    return 0


def cmd_env(_: argparse.Namespace) -> int:
    path = os.environ.get("BRKRAW_PATH")
    scan_id = os.environ.get("BRKRAW_SCAN_ID")
    reco_id = os.environ.get("BRKRAW_RECO_ID")
    param_key = os.environ.get("BRKRAW_PARAM_KEY")
    param_file = os.environ.get("BRKRAW_PARAM_FILE")
    convert_output = os.environ.get("BRKRAW_CONVERT_OUTPUT")
    convert_prefix = os.environ.get("BRKRAW_CONVERT_PREFIX")
    convert_scan_id = os.environ.get("BRKRAW_CONVERT_SCAN_ID")
    convert_reco_id = os.environ.get("BRKRAW_CONVERT_RECO_ID")
    convert_sidecar = os.environ.get("BRKRAW_CONVERT_SIDECAR")
    convert_context_map = os.environ.get("BRKRAW_CONVERT_CONTEXT_MAP")
    convert_compress = os.environ.get("BRKRAW_CONVERT_COMPRESS")
    convert_space = os.environ.get("BRKRAW_CONVERT_SPACE")
    convert_flatten_fg = os.environ.get("BRKRAW_CONVERT_FLATTEN_FG")
    convert_subject_type = os.environ.get("BRKRAW_CONVERT_OVERRIDE_SUBJECT_TYPE")
    convert_subject_pose = os.environ.get("BRKRAW_CONVERT_OVERRIDE_SUBJECT_POSE")
    convert_xyz_units = os.environ.get("BRKRAW_CONVERT_XYZ_UNITS")
    convert_t_units = os.environ.get("BRKRAW_CONVERT_T_UNITS")
    convert_header = os.environ.get("BRKRAW_CONVERT_HEADER")
    if (
        path is None
        and scan_id is None
        and reco_id is None
        and param_key is None
        and param_file is None
        and convert_output is None
        and convert_prefix is None
        and convert_scan_id is None
        and convert_reco_id is None
        and convert_sidecar is None
        and convert_context_map is None
        and convert_compress is None
        and convert_space is None
        and convert_flatten_fg is None
        and convert_subject_type is None
        and convert_subject_pose is None
        and convert_xyz_units is None
        and convert_t_units is None
        and convert_header is None
    ):
        print("(none)")
        return 0
    if path is not None:
        print(f"BRKRAW_PATH={path}")
    if scan_id is not None:
        print(f"BRKRAW_SCAN_ID={scan_id}")
    if reco_id is not None:
        print(f"BRKRAW_RECO_ID={reco_id}")
    if param_key is not None:
        print(f"BRKRAW_PARAM_KEY={param_key}")
    if param_file is not None:
        print(f"BRKRAW_PARAM_FILE={param_file}")
    if convert_output is not None:
        print(f"BRKRAW_CONVERT_OUTPUT={convert_output}")
    if convert_prefix is not None:
        print(f"BRKRAW_CONVERT_PREFIX={convert_prefix}")
    if convert_scan_id is not None:
        print(f"BRKRAW_CONVERT_SCAN_ID={convert_scan_id}")
    if convert_reco_id is not None:
        print(f"BRKRAW_CONVERT_RECO_ID={convert_reco_id}")
    if convert_sidecar is not None:
        print(f"BRKRAW_CONVERT_SIDECAR={convert_sidecar}")
    if convert_context_map is not None:
        print(f"BRKRAW_CONVERT_CONTEXT_MAP={convert_context_map}")
    if convert_space is not None:
        print(f"BRKRAW_CONVERT_SPACE={convert_space}")
    if convert_compress is not None:
        print(f"BRKRAW_CONVERT_COMPRESS={convert_compress}")
    if convert_flatten_fg is not None:
        print(f"BRKRAW_CONVERT_FLATTEN_FG={convert_flatten_fg}")
    if convert_subject_type is not None:
        print(f"BRKRAW_CONVERT_OVERRIDE_SUBJECT_TYPE={convert_subject_type}")
    if convert_subject_pose is not None:
        print(f"BRKRAW_CONVERT_OVERRIDE_SUBJECT_POSE={convert_subject_pose}")
    if convert_xyz_units is not None:
        print(f"BRKRAW_CONVERT_XYZ_UNITS={convert_xyz_units}")
    if convert_t_units is not None:
        print(f"BRKRAW_CONVERT_T_UNITS={convert_t_units}")
    if convert_header is not None:
        print(f"BRKRAW_CONVERT_HEADER={convert_header}")
    return 0


def _format_short_help(parser: argparse.ArgumentParser) -> str:
    formatter = parser._get_formatter()
    formatter.add_usage(parser.usage, parser._actions, parser._mutually_exclusive_groups)
    for action_group in parser._action_groups:
        formatter.start_section(action_group.title)
        actions = [
            action
            for action in action_group._group_actions
            if "-h" not in action.option_strings and "--help" not in action.option_strings
        ]
        formatter.add_arguments(actions)
        formatter.end_section()
    return formatter.format_help()


def _parse_convert_options(items: List[str]) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid convert option (expected KEY=VALUE): {item}")
        key, value = item.split("=", 1)
        key = key.strip().upper().replace("-", "_")
        if not key:
            raise ValueError(f"Invalid convert option key in: {item}")
        pairs.append((key, value.strip()))
    return pairs


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
    session_parser = subparsers.add_parser(
        "session",
        help="Manage BrkRaw environment defaults.",
    )
    session_parser.add_argument(
        "--root",
        help="Override config root directory (default: BRKRAW_CONFIG_HOME or ~/.brkraw).",
    )
    session_parser.set_defaults(func=cmd_session, parser=session_parser)
    session_sub = session_parser.add_subparsers(dest="session_command")

    set_parser = session_sub.add_parser(
        "set",
        help="Emit shell exports for BrkRaw environment defaults.",
    )
    set_parser.add_argument(
        "-p",
        "--path",
        help="Default Bruker study path.",
    )
    set_parser.add_argument(
        "-s",
        "--scan-id",
        nargs="*",
        type=int,
        help="Default scan id(s).",
    )
    set_parser.add_argument(
        "-r",
        "--reco-id",
        type=int,
        help="Default reco id.",
    )
    set_parser.add_argument(
        "-k",
        "--param-key",
        help="Default parameter key for brkraw params.",
    )
    set_parser.add_argument(
        "-f",
        "--param-file",
        nargs="*",
        help="Default parameter file(s) for brkraw params.",
    )
    set_parser.add_argument(
        "--convert-option",
        action="append",
        metavar="KEY=VALUE",
        help=(
            "Set BRKRAW_CONVERT_<OPTION> as KEY=VALUE (repeatable). "
            "Keys: OUTPUT, PREFIX, SCAN_ID, RECO_ID, SIDECAR, CONTEXT_MAP, "
            "COMPRESS, SPACE, FLATTEN_FG, OVERRIDE_SUBJECT_TYPE, "
            "OVERRIDE_SUBJECT_POSE, XYZ_UNITS, T_UNITS, HEADER, FORMAT."
        ),
    )
    set_parser.set_defaults(session_func=cmd_set, parser=set_parser)

    unset_parser = session_sub.add_parser(
        "unset",
        help="Emit shell unset commands for BrkRaw environment defaults.",
    )
    unset_parser.add_argument(
        "-p",
        "--path",
        action="store_true",
        help="Unset BRKRAW_PATH.",
    )
    unset_parser.add_argument(
        "-s",
        "--scan-id",
        action="store_true",
        help="Unset BRKRAW_SCAN_ID.",
    )
    unset_parser.add_argument(
        "-r",
        "--reco-id",
        action="store_true",
        help="Unset BRKRAW_RECO_ID.",
    )
    unset_parser.add_argument(
        "-k",
        "--param-key",
        action="store_true",
        help="Unset BRKRAW_PARAM_KEY.",
    )
    unset_parser.add_argument(
        "-f",
        "--param-file",
        action="store_true",
        help="Unset BRKRAW_PARAM_FILE.",
    )
    unset_parser.add_argument(
        "--convert-option",
        nargs="?",
        action="append",
        const="*",
        metavar="KEY",
        help=(
            "Unset BRKRAW_CONVERT_<OPTION> by KEY (repeatable). "
            "Use without KEY to unset all convert variables."
        ),
    )
    unset_parser.set_defaults(session_func=cmd_unset)

    env_parser = session_sub.add_parser(
        "env",
        help="Show current BrkRaw environment defaults.",
    )
    env_parser.set_defaults(session_func=cmd_env)
