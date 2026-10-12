from __future__ import annotations

"""Copy a ParaVision study (or chosen scans) into one zip."""

import argparse
import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Dict, List, Optional

try:
    resources.files  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - fallback for Python 3.8
    import importlib_resources as resources  # type: ignore[assignment,no-redef]

import yaml

from brkraw.cli.utils import add_root_argument, spinner
from brkraw.core import config as config_core
from brkraw.specs.pruner import (
    classify_scans,
    prune_dataset_to_zip,
    resolve_prune_spec,
    select_files,
)

logger = logging.getLogger(__name__)


_UNSAFE_NAME = re.compile(r'[/\\:*?"<>|\s]')


def default_output_name(input_name: str, *, anonymize: bool, subject_id: str, study_id: str) -> str:
    """Default zip name: pruned_<study>.zip, or pruned_anon_<subject>_<study-id>.zip when anonymizing."""
    if anonymize:
        base = "pruned_anon_" + subject_id + "_" + study_id
    else:
        text = input_name
        lower = text.lower()
        if lower.endswith(".zip"):
            text = text[:-4]
        elif lower.endswith(".pvdatasets"):
            text = text[:-11]
        base = "pruned_" + text
    return _UNSAFE_NAME.sub("_", base) + ".zip"


def cmd_prune(args: argparse.Namespace) -> int:
    path = args.path or os.environ.get("BRKRAW_PATH")
    if not path:
        args.parser.print_help()
        return 2
    if not args.path:
        logger.info("Using study: %s", path)
    if not Path(path).exists():
        logger.error("Path not found: %s", path)
        return 2

    template_vars: Dict[str, str] = {"subject_id": args.subject_id, "study_id": args.study_id}
    try:
        template_vars.update(_parse_kv_pairs(args.set_vars))
    except ValueError as exc:
        logger.error("%s", exc)
        return 2

    spec_value = "anonymize" if args.anonymize else args.spec
    if spec_value:
        try:
            spec_path = _resolve_pruner_spec(spec_value)
            spec = resolve_prune_spec(spec_path, validate=not args.no_validate, template_vars=template_vars)
        except ValueError as exc:
            logger.error("%s", exc)
            return 2
        # --anonymize, or a spec that declares it (anonymize: true), or the built-in spec
        anonymize = args.anonymize or spec.get("anonymize") is True or _is_builtin_anonymize(spec_path)
    else:
        spec_path = None
        spec = {}
        anonymize = False

    if args.files:
        files, mode = args.files, "keep"
    elif args.exclude_files:
        files, mode = args.exclude_files, "drop"
    elif spec_path is not None:
        files, mode = spec.get("files", []), spec.get("mode", "keep")
    else:
        files, mode = None, "keep"

    dirs = _build_dir_override(args.scan_id, args.reco_id)
    if dirs is None:
        dirs = spec.get("dirs")

    strip = (
        args.strip_jcamp_comments
        if args.strip_jcamp_comments is not None
        else bool(spec.get("strip_jcamp_comments", False))
    )

    output = args.output or str(
        Path.cwd()
        / default_output_name(
            Path(path).name,
            anonymize=anonymize,
            subject_id=template_vars["subject_id"],
            study_id=template_vars["study_id"],
        )
    )

    try:
        selected = select_files(path, files, mode=mode, dirs=dirs)
    except ValueError as exc:
        logger.error("%s", exc)
        return 2
    if not selected:
        logger.error("No files left to copy.")
        return 2
    _warn_scans(selected, args.scan_id, args.reco_id)

    if args.dry_run:
        print("Dry run: nothing is written.")
        print(f"input: {path}")
        print(f"output: {output}")
        root_name = spec.get("root_name")
        if root_name:
            print(f"top folder: {root_name}")
        else:
            print("top folder: the original study folder name")
        kinds = classify_scans(selected)
        scan_ids = list(kinds.keys())
        print("scans: " + (", ".join(scan_ids) if scan_ids else "-"))
        for sid in scan_ids:
            n = sum(1 for p in selected if p.split("/")[0] == sid)
            print(f"  scan {sid}: {n} files")
        print(f"files: {len(selected)}")
        print("changes:")
        listed = False
        update_params = spec.get("update_params") or {}
        for file_name, keys in update_params.items():
            for key, value in keys.items():
                listed = True
                shown = "removed" if value is None else value
                print(f"  {file_name}: {key} -> {shown}")
        jcamp_headers = spec.get("jcamp_headers") or {}
        for name, value in jcamp_headers.items():
            listed = True
            print(f"  ##{name} -> {value} (every JCAMP file)")
        if args.institution:
            listed = True
            print(
                f"  institution -> {args.institution} "
                "(ACQ_institution, VisuInstitution, SUBJECT_institution where present)"
            )
        if not listed:
            print("  none")
        print("$$ comment lines: removed" if strip else "$$ comment lines: kept")
        print("Fields are changed only where they exist in the source.")
        return 0

    report: dict = {}
    try:
        with spinner("Pruning"):
            prune_dataset_to_zip(
                path,
                output,
                files,
                mode=mode,
                update_params=spec.get("update_params"),
                dirs=dirs,
                add_root=spec.get("add_root", True),
                root_name=spec.get("root_name"),
                strip_jcamp_comments=strip,
                jcamp_headers=spec.get("jcamp_headers"),
                institution=args.institution,
                overwrite=args.overwrite,
                report=report,
            )
    except Exception as exc:
        logger.error("%s", exc)
        return 2

    write_prune_record(
        out_path=Path(output),
        input_path=Path(path),
        spec_path=spec_path,
        settings={
            "strip_jcamp_comments": strip,
            "scan_id": args.scan_id,
            "reco_id": args.reco_id,
            "files": args.files,
            "exclude_files": args.exclude_files,
            "institution": args.institution,
            "template_vars": template_vars,
        },
        anonymize=anonymize,
    )

    print(
        f'Wrote {output}: {report["files"]} files, {report["bytes"]} bytes; '
        f'scans: {", ".join(report["scans"]) or "-"}; fields changed: {report["changed"]}.'
    )
    print(f'Check the copy with "brkraw info {output}" before sharing it.')
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
    prune_parser = subparsers.add_parser(
        "prune",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Copy a ParaVision study (or chosen scans) into one zip.",
        description=(
            "Copy a ParaVision study into one zip, whole or only the scans and recos you\n"
            "choose. The source is never changed.\n"
            "\n"
            "By default every file of the chosen scans is copied as it is, including raw\n"
            "data (fid, rawdata.job0) and study files such as subject. Nothing is\n"
            "anonymized. Without -s, all scans are copied. Without a path, the study set\n"
            "with \"brkraw session\" is used, or on a scanner console the study open in\n"
            "ParaVision."
        ),
        epilog=(
            "examples:\n"
            "  brkraw prune study.zip                     # ./pruned_study.zip: all scans, no changes\n"
            "  brkraw prune                               # scanner console: the open study\n"
            "  brkraw prune study.zip -s 3 5 -r 1 -o scans_3_5.zip\n"
            "  brkraw prune study.zip --exclude-files fid\n"
            "  brkraw prune study.zip --institution \"Example University\"\n"
            "  brkraw prune study.zip --anonymize --subject-id M01 --dry-run\n"
        ),
    )
    prune_parser.add_argument(
        "path",
        nargs="?",
        type=str,
        help="Study folder, .zip or .PvDatasets file.",
    )

    what_group = prune_parser.add_argument_group("what to copy")
    what_group.add_argument(
        "-s",
        "--scan-id",
        dest="scan_id",
        nargs="+",
        metavar="SCAN_ID",
        help="Copy only these scans (space or comma separated).",
    )
    what_group.add_argument(
        "-r",
        "--reco-id",
        dest="reco_id",
        nargs="+",
        metavar="RECO_ID",
        help="Copy only these recos of each chosen scan.",
    )
    files_group = what_group.add_mutually_exclusive_group()
    files_group.add_argument(
        "--files",
        nargs="+",
        metavar="NAME",
        help="Copy only files with these names or relative paths.",
    )
    files_group.add_argument(
        "--exclude-files",
        dest="exclude_files",
        nargs="+",
        metavar="NAME",
        help="Copy everything except files with these names (for example fid).",
    )

    values_group = prune_parser.add_argument_group("values")
    values_group.add_argument(
        "--institution",
        metavar="NAME",
        help=(
            "Write NAME into the institution fields that exist "
            "(ACQ_institution, VisuInstitution, SUBJECT_institution)."
        ),
    )
    anon_group = values_group.add_mutually_exclusive_group()
    anon_group.add_argument(
        "--anonymize",
        action="store_true",
        help=(
            "Apply the example anonymization spec shipped with brkraw. It is a "
            "starting point: check the result before sharing."
        ),
    )
    anon_group.add_argument(
        "--spec",
        metavar="SPEC",
        help="Apply a pruner spec: a YAML path, an installed name, or a built-in name.",
    )
    values_group.add_argument(
        "--subject-id",
        dest="subject_id",
        metavar="ID",
        default="anon",
        help="Value for $subject_id (default: anon).",
    )
    values_group.add_argument(
        "--study-id",
        dest="study_id",
        metavar="ID",
        default="anon",
        help="Value for $study_id (default: anon).",
    )
    values_group.add_argument(
        "--set-var",
        dest="set_vars",
        action="append",
        metavar="KEY=VALUE",
        help="Fill another $KEY placeholder (repeatable). A placeholder left unfilled stops the run.",
    )
    comments_group = values_group.add_mutually_exclusive_group()
    comments_group.add_argument(
        "--strip-jcamp-comments",
        dest="strip_jcamp_comments",
        action="store_const",
        const=True,
        default=None,
        help="Remove $$ comment lines from kept JCAMP files (default: the spec's setting).",
    )
    comments_group.add_argument(
        "--keep-jcamp-comments",
        dest="strip_jcamp_comments",
        action="store_const",
        const=False,
        help="Keep $$ comment lines even if the spec removes them.",
    )

    output_group = prune_parser.add_argument_group("output")
    output_group.add_argument(
        "-o",
        "--output",
        dest="output",
        help=(
            "Output zip (default: ./pruned_<study>.zip, or "
            "./pruned_anon_<subject>_<study-id>.zip with --anonymize or a spec with anonymize: true)."
        ),
    )
    output_group.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing output file.",
    )
    output_group.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Show what would be copied and changed; write nothing.",
    )
    output_group.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip pruner spec validation.",
    )

    add_root_argument(prune_parser)
    prune_parser.set_defaults(func=cmd_prune, parser=prune_parser)


def write_prune_record(
    *,
    out_path: Path,
    input_path: Path,
    spec_path: Optional[Path],
    settings: dict,
    anonymize: bool = False,
) -> Path:
    """Write ``<output>.prune.yaml`` next to the zip (fix 4).

    The record keeps names, never full paths: the input folder or file name
    (left out entirely when anonymizing, because it usually holds the date and
    subject), the output file name, and the spec file name with its SHA-256.
    ``settings`` holds the options actually used.
    """
    record = out_path.with_suffix(".prune.yaml")
    payload: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "command": "brkraw prune",
    }
    if not anonymize:
        payload["input_name"] = input_path.name
    payload["output_name"] = out_path.name
    if spec_path is None:
        payload["spec_name"] = None
        payload["spec_sha256"] = None
    else:
        payload["spec_name"] = spec_path.name
        payload["spec_sha256"] = hashlib.sha256(spec_path.read_bytes()).hexdigest()
        payload["spec"] = _load_prune_spec_summary(spec_path)
    payload.update(settings)
    record.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return record


def _builtin_spec(name: str) -> Optional[Path]:
    if "/" in name or "\\" in name:
        return None
    if name.endswith(".yaml"):
        stem = name[:-5]
    elif name.endswith(".yml"):
        stem = name[:-4]
    else:
        stem = name
    entry = resources.files("brkraw.default").joinpath("pruner_specs", stem + ".yaml")
    return Path(str(entry)) if entry.is_file() else None


def _resolve_pruner_spec(value: str) -> Path:
    raw = Path(value).expanduser()
    candidates = []
    if raw.suffix:
        candidates.append(raw)
    else:
        candidates.append(raw)
        candidates.append(raw.with_suffix(".yaml"))
        candidates.append(raw.with_suffix(".yml"))

    if raw.is_absolute():
        for cand in candidates:
            if cand.exists():
                return cand
    else:
        search_roots = [Path.cwd(), config_core.paths().pruner_specs_dir]
        for base in search_roots:
            for cand in candidates:
                path = (base / cand).resolve()
                if path.exists():
                    return path

    builtin = _builtin_spec(value)
    if builtin is not None:
        return builtin
    raise ValueError(f"Pruner spec not found: {value}")


def _is_builtin_anonymize(spec_path: Path) -> bool:
    builtin = _builtin_spec("anonymize")
    if builtin is None:
        return False
    return spec_path.resolve() == builtin.resolve()


def _load_prune_spec_summary(spec_path: Path) -> dict:
    try:
        data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        "__meta__": data.get("__meta__", {}),
        "mode": data.get("mode"),
        "files": data.get("files"),
        "dirs": data.get("dirs"),
        "update_params_keys": list((data.get("update_params") or {}).keys()),
        "add_root": data.get("add_root"),
        "root_name": data.get("root_name"),
        "strip_jcamp_comments": data.get("strip_jcamp_comments"),
    }


def _build_dir_override(
    scan_ids: Optional[List[str]],
    reco_ids: Optional[List[str]],
) -> Optional[List[Dict[str, object]]]:
    scan_list = _parse_id_list(scan_ids)
    reco_list = _parse_id_list(reco_ids)
    rules: List[Dict[str, object]] = []
    if scan_list:
        rules.append({"level": 1, "dirs": scan_list})
    if reco_list:
        rules.append({"level": 3, "dirs": reco_list})
    return rules or None


def _parse_id_list(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    result: List[str] = []
    for value in values:
        for part in str(value).split(","):
            part = part.strip()
            if part:
                result.append(part)
    return result


def _parse_kv_pairs(items: Optional[List[str]]) -> Dict[str, str]:
    if not items:
        return {}
    pairs: Dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"--set-var needs KEY=VALUE: {item!r}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"--set-var needs KEY=VALUE: {item!r}")
        pairs[key] = value
    return pairs


def _warn_scans(
    selected: List[str],
    scan_ids: Optional[List[str]],
    reco_ids: Optional[List[str]],
) -> None:
    kinds = classify_scans(selected)
    for sid, kind in kinds.items():
        if kind == "raw":
            logger.warning(
                "scan %s has raw data only (no 2dseq and visu_pars): brkraw cannot convert it.",
                sid,
            )
        elif kind == "none":
            logger.warning(
                "scan %s has no image or raw data files (2dseq, fid, rawdata.job*): it may be incomplete.",
                sid,
            )
    for sid in _parse_id_list(scan_ids):
        if sid not in kinds:
            logger.warning("scan %s not found in the dataset.", sid)
    for rid in _parse_id_list(reco_ids):
        found = False
        for p in selected:
            parts = p.split("/")
            if len(parts) >= 3 and parts[1] == "pdata" and parts[2] == rid:
                found = True
                break
        if not found:
            logger.warning("reco %s not found in the chosen scans.", rid)
