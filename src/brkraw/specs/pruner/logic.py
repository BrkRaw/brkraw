from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Set, Union, Literal, Mapping, Dict, Any, List
import os
import re
import shutil
import tempfile
import zipfile

import yaml

from ...core.fs import DatasetFS
from ...core.parameters import Parameters
from .validator import validate_prune_spec


INSTITUTION_FIELDS: Dict[str, List[str]] = {
    "acqp": ["ACQ_institution"],
    "visu_pars": ["VisuInstitution"],
    "subject": ["SUBJECT_institution"],
}


def select_files(
    source: Union[str, Path],
    files: Optional[Iterable[str]] = None,
    *,
    mode: Literal["keep", "drop"] = "keep",
    dirs: Optional[Iterable[Mapping[str, Any]]] = None,
) -> List[str]:
    """Dataset-relative paths a prune would copy, sorted.

    ``files=None`` selects every file (the default prune). Otherwise ``mode``
    "keep" keeps only matching names or relative paths and "drop" removes them.
    ``dirs`` are folder rules ``{level, dirs}`` (level 1 = scan folders,
    level 3 = reco folders under ``pdata``); files above a rule's level, such
    as the study file ``subject``, are never removed by it.
    """
    fs = DatasetFS.from_path(source)
    return sorted(_selected(fs, files, mode=mode, dirs=dirs))


def _selected(
    fs: DatasetFS,
    files: Optional[Iterable[str]],
    *,
    mode: Literal["keep", "drop"],
    dirs: Optional[Iterable[Mapping[str, Any]]],
) -> Set[str]:
    if mode not in {"keep", "drop"}:
        raise ValueError("mode must be 'keep' or 'drop'.")
    if files is None:
        mode, selectors = "drop", set()
    else:
        selectors = _normalize_selectors(files)
        if not selectors and mode == "keep":
            raise ValueError("files must contain at least one filename or path.")
    rule_specs = _normalize_dir_rules(dirs, "keep" if files is None else mode)
    return _select_files(fs, selectors, mode=mode, dir_rules=rule_specs)


def prune_dataset_to_zip(
    source: Union[str, Path],
    dest: Union[str, Path],
    files: Optional[Iterable[str]] = None,
    *,
    mode: Literal["keep", "drop"] = "keep",
    update_params: Optional[Mapping[str, Mapping[str, Optional[str]]]] = None,
    dirs: Optional[Iterable[Mapping[str, Any]]] = None,
    add_root: bool = True,
    root_name: Optional[str] = None,
    strip_jcamp_comments: bool = False,
    jcamp_headers: Optional[Mapping[str, Any]] = None,
    institution: Optional[str] = None,
    overwrite: bool = False,
    report: Optional[Dict[str, Any]] = None,
) -> Path:
    """Create a pruned dataset ZIP with optional JCAMP parameter edits.

    Args:
        source: Dataset root (directory or zip file).
        dest: Destination zip path.
        files: Filenames or relative paths used by the selection mode; None
            (the default) copies every file.
        mode: "keep" to include only matching files, "drop" to exclude them.
        update_params: Mapping of {filename: {key: value}} JCAMP edits.
        dirs: Directory rules as a list of {level, dirs} mappings.
        add_root: Whether to include a top-level root directory in the zip.
        root_name: Override the root directory name when add_root is True
            (default: the original study folder name).
        strip_jcamp_comments: When True, remove $$ comment lines from JCAMP files.
        jcamp_headers: Mapping of {HEADER: value} applied to the ``##HEADER=``
            lines of every kept JCAMP file (for example ``{"OWNER": "anon"}``).
        institution: Institution name written into the institution fields that
            exist in the source (``INSTITUTION_FIELDS``); after, and over, the
            spec's edits. No field is created.
        overwrite: When False (default), an existing ``dest`` is never replaced.
        report: Optional dict filled with ``files``, ``bytes``, ``scans`` and
            ``changed`` (parameter fields that existed and were changed or
            removed) after writing.

    Returns:
        Path to the created zip file.

    Raises:
        ValueError: When the selector list is empty or no files remain after filtering.
        FileExistsError: When ``dest`` exists and ``overwrite`` is False.
    """
    fs = DatasetFS.from_path(source)
    selected_files = _selected(fs, files, mode=mode, dirs=dirs)
    if not selected_files:
        raise ValueError(f"No files remain after applying {mode} list.")

    dest = Path(dest)
    if dest.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {dest} (use overwrite=True to replace it)")
    dest.parent.mkdir(parents=True, exist_ok=True)
    root = root_name or fs.anchor or fs.root.name

    arcnames = [_to_arcname(relpath, root, add_root=add_root) for relpath in selected_files]
    param_updates = _load_parameter_updates(update_params)
    headers = _load_jcamp_headers(jcamp_headers)

    # Write to a temporary file beside dest and move it into place only when
    # the whole zip is written, so a failure never leaves a half-written zip.
    fd, tmp_name = tempfile.mkstemp(
        prefix="." + dest.name + ".", suffix=".tmp", dir=str(dest.parent)
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    stats: Dict[str, Any] = {"files": 0, "bytes": 0, "changed": 0}
    try:
        _write_zip(
            fs,
            tmp_path,
            selected_files,
            arcnames,
            param_updates=param_updates,
            strip_jcamp_comments=strip_jcamp_comments,
            jcamp_headers=headers,
            institution=institution,
            stats=stats,
        )
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
    os.replace(tmp_path, dest)
    if report is not None:
        report.update(stats)
        report["scans"] = sorted(
            {rel.split("/", 1)[0] for rel in selected_files if "/" in rel and rel.split("/", 1)[0].isdecimal()},
            key=int,
        )
    return dest


def prune_dataset_to_zip_from_spec(
    spec: Union[Mapping[str, Any], str, Path],
    *,
    source: Optional[Union[str, Path]] = None,
    dest: Optional[Union[str, Path]] = None,
    validate: bool = True,
    strip_jcamp_comments: Optional[bool] = None,
    root_name: Optional[str] = None,
    dirs: Optional[Iterable[Mapping[str, Any]]] = None,
    mode: Optional[Literal["keep", "drop"]] = None,
    template_vars: Optional[Mapping[str, str]] = None,
    overwrite: bool = False,
    files: Optional[Iterable[str]] = None,
    institution: Optional[str] = None,
    report: Optional[Dict[str, Any]] = None,
) -> Path:
    """Create a pruned dataset ZIP from a prune spec mapping or YAML path.

    Args:
        spec: Prune spec mapping or YAML file path.
        source: Optional override for spec["source"].
        dest: Optional override for spec["dest"].
        validate: When True, validate the spec against the schema.
        strip_jcamp_comments: Optional override to strip $$ comment lines.
        root_name: Optional override for the root directory name in the zip.
        dirs: Optional override for directory filter rules.
        mode: Optional override for keep/drop mode.
        template_vars: Optional mapping used to substitute `$key` placeholders.
        overwrite: When False (default), an existing ``dest`` is never replaced.
        files: Optional override for the spec's file list (used with ``mode``).
        institution: See ``prune_dataset_to_zip``.
        report: See ``prune_dataset_to_zip``.

    Returns:
        Path to the created zip file.

    Raises:
        ValueError: Also when a ``$name`` placeholder is left after substitution.
    """
    spec_data = resolve_prune_spec(spec, validate=validate, template_vars=template_vars)

    if source is None or dest is None:
        raise ValueError("source and dest are required for prune spec.")

    mode_value = mode if mode is not None else spec_data.get("mode", "keep")
    if mode_value not in {"keep", "drop"}:
        raise ValueError("mode must be 'keep' or 'drop'.")

    return prune_dataset_to_zip(
        source,
        dest,
        files=files if files is not None else spec_data.get("files", []),
        mode=mode_value,
        update_params=spec_data.get("update_params"),
        dirs=dirs if dirs is not None else spec_data.get("dirs"),
        add_root=spec_data.get("add_root", True),
        root_name=root_name if root_name is not None else spec_data.get("root_name"),
        strip_jcamp_comments=(
            strip_jcamp_comments
            if strip_jcamp_comments is not None
            else bool(spec_data.get("strip_jcamp_comments", False))
        ),
        jcamp_headers=spec_data.get("jcamp_headers"),
        institution=institution,
        overwrite=overwrite,
        report=report,
    )


def resolve_prune_spec(
    spec: Union[Mapping[str, Any], str, Path],
    *,
    validate: bool = True,
    template_vars: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Load (or copy) a spec, validate it, fill ``$name`` placeholders and check none is left.

    Placeholders in ``__meta__`` (for example a description that names them)
    are not required to be filled.
    """
    if isinstance(spec, (str, Path)):
        spec_data = load_prune_spec(spec, validate=validate)
    else:
        spec_data = dict(spec)
        if validate:
            validate_prune_spec(spec_data)
    if template_vars:
        spec_data = _substitute_vars(spec_data, template_vars)
    left = find_unfilled_vars(spec_data)
    if left:
        names = ", ".join("$" + name for name in left)
        raise ValueError(f"Unfilled placeholders in the pruner spec: {names} (give them with --set-var KEY=VALUE).")
    return spec_data


def load_prune_spec(path: Union[str, Path], *, validate: bool = True) -> Dict[str, Any]:
    """Load a prune spec from YAML and optionally validate it."""
    spec_path = Path(path)
    data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if data is None:
        raise ValueError("Prune spec is empty.")
    if not isinstance(data, Mapping):
        raise ValueError("Prune spec must be a mapping.")
    spec = dict(data)
    if validate:
        validate_prune_spec(spec)
    return spec


def _normalize_selectors(items: Iterable[str]) -> Set[str]:
    """Normalize selector strings by trimming and dropping empty entries."""
    return {str(item).strip().strip("/") for item in items if str(item).strip()}


def _select_files(
    fs: DatasetFS,
    selectors: Set[str],
    *,
    mode: Literal["keep", "drop"],
    dir_rules: List[Dict[str, Any]],
) -> Set[str]:
    """Return dataset-relative file paths selected by keep/drop rules."""
    selected: Set[str] = set()
    for dirpath, _, filenames in fs.walk():
        for name in filenames:
            rel = f"{dirpath}/{name}".strip("/")
            rel = fs.strip_anchor(rel)
            if _is_excluded_by_dir_rules(rel, dir_rules):
                continue
            matches = _matches_selector(rel, name, selectors)
            if mode == "keep" and matches:
                selected.add(rel)
            elif mode == "drop" and not matches:
                selected.add(rel)
    return selected


def _matches_selector(relpath: str, name: str, selectors: Set[str]) -> bool:
    """Match either a full relative path or a basename against selectors."""
    return relpath in selectors or name in selectors


def _to_arcname(relpath: str, root: str, *, add_root: bool) -> str:
    """Build a zip archive name with optional root folder prefix."""
    relpath = relpath.strip("/")
    if not add_root:
        return relpath
    if not root:
        return relpath
    return f"{root}/{relpath}" if relpath else root


def _write_zip(
    fs: DatasetFS,
    dest: Path,
    files: Iterable[str],
    arcnames: Iterable[str],
    *,
    param_updates: Optional[Mapping[str, Mapping[str, Optional[str]]]] = None,
    strip_jcamp_comments: bool = False,
    jcamp_headers: Optional[Mapping[str, str]] = None,
    institution: Optional[str] = None,
    stats: Optional[Dict[str, Any]] = None,
) -> None:
    """Write selected files into a zip, applying JCAMP edits when requested."""
    entries = sorted(zip(files, arcnames), key=lambda item: item[1])
    parent_dirs = _collect_parent_dirs([arc for _, arc in entries])
    param_updates = param_updates or {}
    headers = jcamp_headers or {}
    stats = stats if stats is not None else {}
    stats.setdefault("files", 0)
    stats.setdefault("bytes", 0)
    stats.setdefault("changed", 0)

    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for d in parent_dirs:
            zf.writestr(f"{d}/", b"")
        for relpath, arcname in entries:
            name = relpath.strip("/").split("/")[-1]
            stats["files"] += 1
            updates = dict(param_updates.get(name) or {})
            inst_keys = INSTITUTION_FIELDS.get(name, []) if institution else []
            if updates or inst_keys:
                content = fs.open_binary(relpath).read()
                original = content.decode("utf-8", errors="ignore")
                # --institution goes over the spec for fields the source has,
                # even when the spec removes them; it never creates a field.
                for key in inst_keys:
                    value = _institution_value(original, key, str(institution))
                    if value is not None:
                        updates[key] = value
                stats["changed"] += sum(1 for key in updates if _has_param(original, key))
                text = _apply_jcamp_updates(content, updates, path_hint=relpath) if updates else original
                text = _apply_jcamp_headers(text, headers)
                if strip_jcamp_comments:
                    text = _strip_jcamp_comments(text)
                data = text.encode("utf-8")
                stats["bytes"] += len(data)
                zf.writestr(arcname, data)
                continue
            if headers or strip_jcamp_comments:
                # Decide from the head only; binary files (fid, rawdata, 2dseq)
                # are streamed and never read whole.
                with fs.open_binary(relpath) as src:
                    head = src.read(4096)
                    if _looks_like_jcamp_head(head):
                        rest = src.read()
                        text = (head + rest).decode("utf-8", errors="ignore")
                        text = _apply_jcamp_headers(text, headers)
                        if strip_jcamp_comments:
                            text = _strip_jcamp_comments(text)
                        data = text.encode("utf-8")
                        stats["bytes"] += len(data)
                        zf.writestr(arcname, data)
                    else:
                        with zf.open(arcname, "w", force_zip64=True) as dst:
                            dst.write(head)
                            stats["bytes"] += len(head) + _copy_stream(src, dst)
                continue
            with fs.open_binary(relpath) as src, zf.open(arcname, "w", force_zip64=True) as dst:
                stats["bytes"] += _copy_stream(src, dst)


def _copy_stream(src, dst, chunk: int = 1 << 20) -> int:
    """Copy in chunks (never the whole file in memory) and return the byte count."""
    total = 0
    while True:
        block = src.read(chunk)
        if not block:
            return total
        dst.write(block)
        total += len(block)


def _has_param(text: str, key: str) -> bool:
    return re.search(r"^##\$" + re.escape(key) + r"=", text, flags=re.M) is not None


def _institution_value(text: str, key: str, name: str) -> Optional[str]:
    """New JCAMP value for an institution field that exists in ``text``; None if absent.

    Keeps a declared string size valid: ``( N )`` becomes max(N, len(name) + 1).
    """
    match = re.search(r"^##\$" + re.escape(key) + r"=\s*(\(\s*(\d+)\s*\))?", text, flags=re.M)
    if match is None:
        return None
    if match.group(2):
        size = max(int(match.group(2)), len(name) + 1)
        return f"( {size} )\n<{name}>"
    return f"<{name}>"


def classify_scans(relpaths: Iterable[str]) -> Dict[str, str]:
    """Per scan id (numeric order): "image" (some pdata folder has 2dseq and visu_pars),
    "raw" (fid or rawdata.job* directly in the scan folder, no image) or "none"."""
    scan_pdata: Dict[str, Dict[str, Set[str]]] = {}
    scan_raw: Set[str] = set()
    for path in list(relpaths):
        parts = [p for p in path.split("/") if p]
        if len(parts) < 2 or not parts[0].isdecimal():
            continue
        scan_id = parts[0]
        pdata = scan_pdata.setdefault(scan_id, {})
        if len(parts) == 4 and parts[1] == "pdata":
            pdata.setdefault(parts[2], set()).add(parts[3])
        if len(parts) == 2 and (parts[1] == "fid" or parts[1].startswith("rawdata.job")):
            scan_raw.add(scan_id)
    result: Dict[str, str] = {}
    for scan_id in sorted(scan_pdata, key=int):
        if any("2dseq" in names and "visu_pars" in names for names in scan_pdata[scan_id].values()):
            result[scan_id] = "image"
        elif scan_id in scan_raw:
            result[scan_id] = "raw"
        else:
            result[scan_id] = "none"
    return result


_UNFILLED = re.compile(r"(?<!\$)\$([A-Za-z_]\w*)")


def find_unfilled_vars(obj: Any) -> List[str]:
    """Names of ``$name`` placeholders left in spec values (not keys; top-level ``__meta__`` skipped)."""
    found: Set[str] = set()

    def walk(current: Any, top: bool) -> None:
        if isinstance(current, Mapping):
            for key, value in current.items():
                if top and key == "__meta__":
                    continue
                walk(value, False)
        elif isinstance(current, (list, tuple)):
            for item in current:
                walk(item, False)
        elif isinstance(current, str):
            found.update(_UNFILLED.findall(current))

    walk(obj, True)
    return sorted(found)


def _collect_parent_dirs(arcnames: Iterable[str]) -> Set[str]:
    """Return all parent directory entries for the given archive paths."""
    dirs: Set[str] = set()
    for arcname in arcnames:
        parts = arcname.split("/")[:-1]
        acc = []
        for part in parts:
            acc.append(part)
            dirs.add("/".join(acc))
    return {d for d in dirs if d}


def _load_parameter_updates(
    update_params: Optional[Mapping[str, Mapping[str, Optional[str]]]]
) -> Dict[str, Dict[str, Optional[str]]]:
    """Validate JCAMP update mappings."""
    if update_params is None:
        return {}
    if not isinstance(update_params, Mapping):
        raise ValueError("update_params must be a mapping.")

    result: Dict[str, Dict[str, Optional[str]]] = {}
    for filename, updates in update_params.items():
        if not isinstance(filename, str) or not filename.strip():
            raise ValueError("update_params keys must be non-empty strings.")
        if not isinstance(updates, Mapping):
            raise ValueError(f"update_params[{filename!r}] must be a mapping.")
        inner: Dict[str, Optional[str]] = {}
        for key, value in updates.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"update_params[{filename!r}] keys must be strings.")
            inner[key] = None if value is None else str(value)
        result[filename.strip()] = inner
    return result


def _apply_jcamp_updates(
    content: bytes,
    updates: Mapping[str, Optional[str]],
    *,
    path_hint: str,
) -> str:
    """Apply JCAMP updates using Parameters and return updated source text."""
    try:
        params = Parameters(content)
    except Exception as exc:
        raise ValueError(f"Parameter file is not parseable: {path_hint}") from exc
    params.replace_values(updates, reparse=True)
    return params.source_text()


def _strip_jcamp_comments(text: str) -> str:
    """Remove $$ comment lines from JCAMP text."""
    lines = text.splitlines(keepends=True)
    kept = [line for line in lines if not line.lstrip().startswith("$$")]
    return "".join(kept)


def _load_jcamp_headers(headers: Optional[Mapping[str, Any]]) -> Dict[str, str]:
    """Validate a {HEADER: value} mapping for JCAMP ``##HEADER=`` lines (for example OWNER)."""
    if headers is None:
        return {}
    if not isinstance(headers, Mapping):
        raise ValueError("jcamp_headers must be a mapping of header names to values.")
    result: Dict[str, str] = {}
    for key, value in headers.items():
        name = str(key).strip()
        if not name or name.startswith("$") or not re.fullmatch(r"[A-Za-z0-9_.]+", name):
            raise ValueError(f"jcamp_headers: invalid header name {key!r}.")
        if value is None or isinstance(value, (dict, list)):
            raise ValueError(f"jcamp_headers[{name!r}] must be a text value.")
        result[name] = str(value)
    return result


def _apply_jcamp_headers(text: str, headers: Mapping[str, str]) -> str:
    """Replace the value of ``##NAME=`` header lines (not ``##$`` parameters)."""
    if not headers:
        return text
    lines = text.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        if not line.startswith("##") or line.startswith("##$"):
            continue
        name, sep, _ = line[2:].partition("=")
        if sep and name in headers:
            ending = line[len(line.rstrip("\r\n")):]
            lines[idx] = f"##{name}={headers[name]}{ending}"
    return "".join(lines)


def _looks_like_jcamp_head(head: bytes) -> bool:
    """Decide from the first bytes of a file whether it is a JCAMP-DX parameter file.

    Strict on purpose: the first non-blank line must be a ``##NAME=`` header
    and there must be no NUL byte, so binary data (fid, 2dseq, rawdata) is
    never treated as text.
    """
    if b"\x00" in head:
        return False
    if head.startswith(b"\xef\xbb\xbf"):
        head = head[3:]
    head = head.lstrip(b" \t\r\n")
    if not head.startswith(b"##"):
        return False
    first_newline = head.find(b"\n")
    first_cr = head.find(b"\r")
    ends = [i for i in (first_newline, first_cr) if i != -1]
    first_line = head[: min(ends)] if ends else head
    return b"=" in first_line


def _normalize_dir_rules(
    rules: Optional[Iterable[Mapping[str, Any]]],
    mode: Literal["keep", "drop"],
) -> List[Dict[str, Any]]:
    if not rules:
        return []
    normalized: List[Dict[str, Any]] = []
    for idx, rule in enumerate(rules):
        if not isinstance(rule, Mapping):
            raise ValueError(f"dirs[{idx}] must be a mapping.")
        level = rule.get("level")
        if not isinstance(level, int) or level < 1:
            raise ValueError(f"dirs[{idx}].level must be int >= 1.")
        dirs = rule.get("dirs")
        if not isinstance(dirs, Iterable):
            raise ValueError(f"dirs[{idx}].dirs must be a list of names.")
        names = [str(d).strip() for d in dirs if str(d).strip()]
        if not names:
            raise ValueError(f"dirs[{idx}].dirs must contain at least one name.")
        normalized.append({"mode": mode, "level": level, "dirs": set(names)})
    normalized.sort(key=lambda item: item["level"])
    return normalized


def _is_excluded_by_dir_rules(relpath: str, rules: List[Dict[str, Any]]) -> bool:
    if not rules:
        return False
    parts = [p for p in relpath.split("/") if p]
    for rule in rules:
        level = rule["level"]
        # A rule for folder level L applies only to paths that have a folder at
        # level L. Files above it (for example the study file `subject` when
        # choosing scans at level 1) are decided by the file list alone.
        if level >= len(parts):
            continue
        name = parts[level - 1]
        if rule["mode"] == "drop":
            if name in rule["dirs"]:
                return True
        else:
            if name not in rule["dirs"]:
                return True
    return False


def _substitute_vars(obj: Any, variables: Mapping[str, str]) -> Any:
    """Recursively substitute $key placeholders in strings using variables mapping."""
    if isinstance(obj, str):
        return _substitute_string(obj, variables)
    if isinstance(obj, Mapping):
        return {k: _substitute_vars(v, variables) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute_vars(item, variables) for item in obj]
    return obj


_VAR_PATTERN = re.compile(r"\$(\w+)")


def _substitute_string(text: str, variables: Mapping[str, str]) -> str:
    def replacer(match: re.Match[str]) -> str:
        key = match.group(1)
        return variables.get(key, match.group(0))

    return _VAR_PATTERN.sub(replacer, text)


__all__ = [
    "INSTITUTION_FIELDS",
    "classify_scans",
    "find_unfilled_vars",
    "prune_dataset_to_zip",
    "prune_dataset_to_zip_from_spec",
    "load_prune_spec",
    "resolve_prune_spec",
    "select_files",
]
