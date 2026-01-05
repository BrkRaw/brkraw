from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Set, Union, Literal, Mapping, Dict, Any, List
import re
import shutil
import zipfile

import yaml

from ...core.fs import DatasetFS
from ...core.parameters import Parameters
from .validator import validate_prune_spec


def prune_dataset_to_zip(
    source: Union[str, Path],
    dest: Union[str, Path],
    files: Iterable[str],
    *,
    mode: Literal["keep", "drop"] = "keep",
    update_params: Optional[Mapping[str, Mapping[str, Optional[str]]]] = None,
    dirs: Optional[Iterable[Mapping[str, Any]]] = None,
    add_root: bool = True,
    root_name: Optional[str] = None,
    strip_jcamp_comments: bool = False,
) -> Path:
    """Create a pruned dataset ZIP with optional JCAMP parameter edits.

    Args:
        source: Dataset root (directory or zip file).
        dest: Destination zip path.
        files: Filenames or relative paths used by the selection mode.
        mode: "keep" to include only matching files, "drop" to exclude them.
        update_params: Mapping of {filename: {key: value}} JCAMP edits.
        dirs: Directory rules as a list of {level, dirs} mappings.
        add_root: Whether to include a top-level root directory in the zip.
        root_name: Override the root directory name when add_root is True.
        strip_jcamp_comments: When True, remove $$ comment lines from JCAMP files.

    Returns:
        Path to the created zip file.

    Raises:
        ValueError: When the selector list is empty or no files remain after filtering.
    """
    fs = DatasetFS.from_path(source)
    selectors = _normalize_selectors(files)
    if not selectors:
        raise ValueError("files must contain at least one filename or path.")

    if mode not in {"keep", "drop"}:
        raise ValueError("mode must be 'keep' or 'drop'.")

    rule_specs = _normalize_dir_rules(dirs, mode)
    selected_files = _select_files(fs, selectors, mode=mode, dir_rules=rule_specs)
    if not selected_files:
        raise ValueError(f"No files remain after applying {mode} list.")

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    root = root_name or fs.anchor or fs.root.name

    arcnames = [_to_arcname(relpath, root, add_root=add_root) for relpath in selected_files]
    param_updates = _load_parameter_updates(update_params)
    _write_zip(
        fs,
        dest,
        selected_files,
        arcnames,
        param_updates=param_updates,
        strip_jcamp_comments=strip_jcamp_comments,
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

    Returns:
        Path to the created zip file.
    """
    if isinstance(spec, (str, Path)):
        spec_data = load_prune_spec(spec, validate=validate)
    else:
        spec_data = dict(spec)
        if validate:
            validate_prune_spec(spec_data)

    if template_vars:
        spec_data = _substitute_vars(spec_data, template_vars)

    if source is None or dest is None:
        raise ValueError("source and dest are required for prune spec.")

    mode_value = mode if mode is not None else spec_data.get("mode", "keep")
    if mode_value not in {"keep", "drop"}:
        raise ValueError("mode must be 'keep' or 'drop'.")

    return prune_dataset_to_zip(
        source,
        dest,
        files=spec_data.get("files", []),
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
    )


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
) -> None:
    """Write selected files into a zip, applying JCAMP edits when requested."""
    entries = sorted(zip(files, arcnames), key=lambda item: item[1])
    parent_dirs = _collect_parent_dirs([arc for _, arc in entries])
    param_updates = param_updates or {}

    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for d in parent_dirs:
            zf.writestr(f"{d}/", b"")
        for relpath, arcname in entries:
            name = relpath.strip("/").split("/")[-1]
            updates = param_updates.get(name)
            if updates:
                content = fs.open_binary(relpath).read()
                updated_text = _apply_jcamp_updates(content, updates, path_hint=relpath)
                if strip_jcamp_comments:
                    updated_text = _strip_jcamp_comments(updated_text)
                zf.writestr(arcname, updated_text.encode("utf-8"))
                continue
            if strip_jcamp_comments:
                content = fs.open_binary(relpath).read()
                if Parameters._looks_like_jcamp(content):
                    stripped = _strip_jcamp_comments(
                        content.decode("utf-8", errors="ignore")
                    )
                    zf.writestr(arcname, stripped.encode("utf-8"))
                    continue
            with fs.open_binary(relpath) as src, zf.open(arcname, "w") as dst:
                shutil.copyfileobj(src, dst)


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
        if level > len(parts):
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
    "prune_dataset_to_zip",
    "prune_dataset_to_zip_from_spec",
    "load_prune_spec",
]
