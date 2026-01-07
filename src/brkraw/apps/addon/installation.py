"""Installation and listing helpers for addon specs and rules."""

from __future__ import annotations

from importlib import resources

try:
    resources.files  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - fallback for Python 3.8
    import importlib_resources as resources  # type: ignore[assignment]
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import yaml

from ...core import config as config_core
from ...specs import remapper
from ...specs.pruner import validator as pruner_validator
from ...specs.rules import validator as rules_validator
from .dependencies import (
    RULE_KEYS,
    collect_transforms_sources as _collect_transforms_sources,
    extract_transforms_source as _extract_transforms_source,
    load_pruner_spec_records as _load_pruner_spec_records,
    load_spec_records as _load_spec_records,
    normalize_transform_ref as _normalize_transform_ref,
    warn_dependencies as _warn_dependencies,
    resolve_spec_reference,
)
from .io import write_file as _write_file

logger = logging.getLogger("brkraw")


def add(path: Union[str, Path], root: Optional[Union[str, Path]] = None) -> List[Path]:
    """Install a spec or rule YAML file."""
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(src)
    if src.suffix.lower() in {".yaml", ".yml"}:
        return add_from_yaml(src, root=root)
    raise ValueError(f"Unsupported file type: {src}")


def add_spec_data(
    spec_data: Dict[str, Any],
    *,
    filename: Optional[str] = None,
    source_path: Optional[Path] = None,
    root: Optional[Union[str, Path]] = None,
    transforms_dir: Optional[Path] = None,
) -> List[Path]:
    """Install a spec from parsed data."""
    if not isinstance(spec_data, dict):
        raise ValueError("Spec data must be a mapping.")
    if filename is None:
        if source_path is None:
            raise ValueError("filename is required when source_path is not provided.")
        filename = source_path.name
    if not filename.endswith((".yaml", ".yml")):
        raise ValueError(f"Spec filename must be .yaml/.yml: {filename}")
    paths = config_core.paths(root=root)
    target = paths.specs_dir / filename
    installed = [target]
    installed_transforms, updated = install_transforms_from_spec(
        spec_data,
        base_dir=source_path.parent if source_path else None,
        target_spec=target,
        root=root,
        target_transforms_dir=transforms_dir,
    )
    installed += installed_transforms
    content = yaml.safe_dump(spec_data, sort_keys=False)
    _write_file(target, content)
    logger.info("Installed spec: %s", target)
    return installed


def add_pruner_spec_data(
    spec_data: Dict[str, Any],
    *,
    filename: Optional[str] = None,
    source_path: Optional[Path] = None,
    root: Optional[Union[str, Path]] = None,
) -> List[Path]:
    """Install a pruner spec from parsed data."""
    if not isinstance(spec_data, dict):
        raise ValueError("Pruner spec data must be a mapping.")
    if filename is None:
        if source_path is None:
            raise ValueError("filename is required when source_path is not provided.")
        filename = source_path.name
    if not filename.endswith((".yaml", ".yml")):
        raise ValueError(f"Pruner spec filename must be .yaml/.yml: {filename}")
    pruner_validator.validate_prune_spec(spec_data)
    paths = config_core.paths(root=root)
    target = paths.pruner_specs_dir / filename
    content = yaml.safe_dump(spec_data, sort_keys=False)
    _write_file(target, content)
    logger.info("Installed pruner spec: %s", target)
    return [target]


def add_rule_data(
    rule_data: Dict[str, Any],
    *,
    filename: Optional[str] = None,
    source_path: Optional[Path] = None,
    root: Optional[Union[str, Path]] = None,
) -> List[Path]:
    """Install a rule file from parsed data."""
    if not isinstance(rule_data, dict):
        raise ValueError("Rule data must be a mapping.")
    if filename is None:
        if source_path is None:
            raise ValueError("filename is required when source_path is not provided.")
        filename = source_path.name
    if not filename.endswith((".yaml", ".yml")):
        raise ValueError(f"Rule filename must be .yaml/.yml: {filename}")
    rules_validator.validate_rules(rule_data)
    ensure_rule_specs_present(rule_data, root=root)
    paths = config_core.paths(root=root)
    target = paths.rules_dir / filename
    content = yaml.safe_dump(rule_data, sort_keys=False)
    _write_file(target, content)
    logger.info("Installed rule: %s", target)
    return [target]


def install_defaults(root: Optional[Union[str, Path]] = None) -> List[Path]:
    """Install bundled default specs and rules."""
    installed: List[Path] = []

    base = resources.files("brkraw.default")
    for rel_dir in ("specs", "rules", "pruner_specs"):
        src_dir = base / rel_dir
        if not src_dir.is_dir():
            continue
        for entry in src_dir.iterdir():
            name = entry.name
            if not (name.endswith(".yaml") or name.endswith(".yml")):
                continue
            content = entry.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
            if not isinstance(data, dict):
                continue
            entry_path = Path(str(entry))
            if rel_dir == "specs":
                installed += add_spec_data(
                    data,
                    filename=name,
                    source_path=entry_path,
                    root=root,
                )
            elif rel_dir == "pruner_specs":
                installed += add_pruner_spec_data(
                    data,
                    filename=name,
                    source_path=entry_path,
                    root=root,
                )
            else:
                installed += add_rule_data(
                    data,
                    filename=name,
                    source_path=entry_path,
                    root=root,
                )
    return installed


def list_installed(root: Optional[Union[str, Path]] = None) -> Dict[str, List[Dict[str, str]]]:
    """List installed specs and rules with metadata."""
    paths = config_core.paths(root=root)
    result: Dict[str, List[Dict[str, str]]] = {
        "specs": [],
        "pruner_specs": [],
        "rules": [],
        "transforms": [],
    }

    rule_entries = load_rule_entries(paths.rules_dir)
    spec_categories = spec_categories_from_rules(rule_entries)

    transforms_map: Dict[str, Set[str]] = {}
    for record in _load_spec_records(paths.specs_dir):
        name = record.get("name")
        desc = record.get("description")
        version = record.get("version")
        category = (
            record.get("category")
            or spec_categories.get(record["file"])
            or spec_categories.get(name or "")
        )
        result["specs"].append(
            {
                "file": record["file"],
                "name": name if name else "<Unknown>",
                "version": version if version else "<Unknown>",
                "description": desc if desc else "<Unknown>",
                "category": category if category else "<Unknown>",
                "name_unknown": "1" if not name else "0",
                "version_unknown": "1" if not version else "0",
                "description_unknown": "1" if not desc else "0",
                "category_unknown": "1" if not category else "0",
            }
        )
        spec_path = record["path"]
        spec_label = record["file"]
        for src in _collect_transforms_sources(spec_path):
            normalized = _normalize_transform_ref(
                src,
                spec_path=spec_path,
                transforms_dir=paths.transforms_dir,
            )
            transforms_map.setdefault(normalized, set()).add(spec_label)

    for entry in rule_entries:
        result["rules"].append(entry)

    for record in _load_pruner_spec_records(paths.pruner_specs_dir):
        result["pruner_specs"].append(
            {
                "file": record["file"],
                "name": record.get("name") or "<Unknown>",
                "version": record.get("version") or "<Unknown>",
                "description": record.get("description") or "<Unknown>",
                "name_unknown": "1" if not record.get("name") else "0",
                "version_unknown": "1" if not record.get("version") else "0",
                "description_unknown": "1" if not record.get("description") else "0",
            }
        )

    for path in sorted(paths.transforms_dir.rglob("*.py")):
        relpath = str(path.relative_to(paths.transforms_dir))
        mapped = transforms_map.get(relpath)
        result["transforms"].append(
            {
                "file": relpath,
                "spec": ", ".join(sorted(mapped)) if mapped else "<Unknown>",
                "spec_unknown": "1" if not mapped else "0",
            }
        )

    return result


def remove(
    filename: Union[str, Path],
    *,
    root: Optional[Union[str, Path]] = None,
    kind: Optional[str] = None,
    force: bool = False,
) -> List[Path]:
    """Remove an installed spec/rule/transform file by filename.

    Notes:
        The `filename` argument matches the installed file name (not the
        spec/rule `__meta__.name`).
    """
    name = Path(filename).name
    paths = config_core.paths(root=root)
    removed: List[Path] = []
    kinds = [kind] if kind else ["spec", "pruner", "rule", "transform"]
    targets = resolve_targets(name, kinds, paths)
    if not targets:
        raise FileNotFoundError(name)
    has_deps = False
    for target, item in targets:
        has_deps = _warn_dependencies(target, kind=item, root=root) or has_deps
    if has_deps and not force:
        raise RuntimeError("Dependencies found; use --force to remove.")
    for target, item in targets:
        target.unlink()
        removed.append(target)
    if not removed:
        raise FileNotFoundError(name)
    return removed


def resolve_targets(
    name: str,
    kinds: List[str],
    paths: config_core.ConfigPaths,
) -> List[Tuple[Path, str]]:
    targets: List[Tuple[Path, str]] = []
    for item in kinds:
        if item == "spec":
            base = paths.specs_dir
        elif item == "pruner":
            base = paths.pruner_specs_dir
        elif item == "rule":
            base = paths.rules_dir
        elif item == "transform":
            base = paths.transforms_dir
        else:
            raise ValueError("kind must be 'spec' or 'pruner' or 'rule' or 'transform'.")
        if not base.exists():
            continue
        candidate = (base / name).resolve()
        if candidate.exists():
            matches = [candidate]
        else:
            matches = [path for path in base.rglob(name) if path.is_file()]
        for path in matches:
            targets.append((path, item))
    return targets


def add_from_yaml(path: Path, root: Optional[Union[str, Path]]) -> List[Path]:
    """Install a spec or rule YAML after classifying the content."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        raise ValueError(f"Empty YAML file: {path}")
    if not isinstance(data, dict):
        raise ValueError(f"Rule/spec YAML must be a mapping: {path}")

    kind = classify_yaml(data)
    if kind == "rule":
        return add_rule_data(data, filename=path.name, source_path=path, root=root)
    if kind == "spec":
        return add_spec_data(data, filename=path.name, source_path=path, root=root)
    if kind == "pruner_spec":
        return add_pruner_spec_data(data, filename=path.name, source_path=path, root=root)
    raise ValueError(f"Unrecognized YAML file: {path}")


def classify_yaml(data: Dict[str, Any]) -> str:
    """Classify YAML content as a spec or rule mapping."""
    if RULE_KEYS.intersection(data.keys()):
        rules_validator.validate_rules(data)
        return "rule"
    errors = remapper.validate_spec(data, raise_on_error=False)
    if not errors:
        return "spec"
    try:
        pruner_validator.validate_prune_spec(data)
    except Exception:
        pass
    else:
        return "pruner_spec"
    rules_validator.validate_rules(data)
    return "rule"


def update_transforms_source(spec_data: Dict[str, Any], value: List[str]) -> None:
    """Rewrite transforms_source fields inside a spec mapping."""
    meta = spec_data.get("__meta__")
    if isinstance(meta, dict) and meta.get("transforms_source"):
        meta["transforms_source"] = value[0] if len(value) == 1 else value
    for section in spec_data.values():
        if not isinstance(section, dict):
            continue
        section_meta = section.get("__meta__")
        if isinstance(section_meta, dict) and section_meta.get("transforms_source"):
            section_meta["transforms_source"] = value[0] if len(value) == 1 else value


def install_transforms_from_spec(
    spec_data: Dict[str, Any],
    *,
    base_dir: Optional[Path],
    target_spec: Path,
    root: Optional[Union[str, Path]],
    target_transforms_dir: Optional[Path] = None,
) -> Tuple[List[Path], bool]:
    """Install transforms referenced by a spec and rewrite paths."""
    sources = _extract_transforms_source(spec_data)
    if not sources:
        return [], False
    paths = config_core.paths(root=root)
    transforms_dir = target_transforms_dir or paths.transforms_dir
    installed: List[Path] = []
    rel_paths: List[str] = []
    for src in sources:
        src_path = Path(src)
        target = transforms_dir / src_path.name
        if base_dir is not None:
            candidate = (base_dir / src_path).resolve()
            if not candidate.exists():
                raise FileNotFoundError(candidate)
            _write_file(target, candidate.read_text(encoding="utf-8"))
        elif src_path.is_absolute():
            if not src_path.exists():
                raise FileNotFoundError(src_path)
            _write_file(target, src_path.read_text(encoding="utf-8"))
        else:
            raise FileNotFoundError(src_path)
        rel_paths.append(os.path.relpath(target, start=target_spec.parent))
        installed.append(target)
        logger.info("Installed transforms: %s", target)
    update_transforms_source(spec_data, rel_paths)
    return installed, True


def ensure_rule_specs_present(rule_data: Dict[str, Any], *, root: Optional[Union[str, Path]]) -> None:
    """Ensure rule references point to installed specs."""
    base = config_core.resolve_root(root)
    for key in RULE_KEYS:
        if key == "converter_hook":
            continue
        for item in rule_data.get(key, []) or []:
            if not isinstance(item, dict):
                continue
            use = item.get("use")
            if not isinstance(use, str):
                continue
            version = item.get("version") if isinstance(item.get("version"), str) else None
            spec_path = resolve_spec_reference(
                use,
                category=key,
                version=version,
                root=base,
            )
            ensure_spec_category(spec_path, key)


def ensure_spec_category(spec_path: Path, category: str) -> None:
    if category not in {"info_spec", "metadata_spec"}:
        return
    data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Spec file must be a mapping: {spec_path}")
    meta = data.get("__meta__")
    if not isinstance(meta, dict):
        raise ValueError(f"{spec_path}: __meta__ must be an object.")
    current = meta.get("category")
    if current is None:
        raise ValueError(f"{spec_path}: __meta__.category is required.")
    if current != category:
        raise ValueError(
            f"{spec_path}: __meta__.category={current!r} conflicts with rule category {category!r}."
        )


def load_rule_entries(rules_dir: Path) -> List[Dict[str, str]]:
    """Load rule metadata for listing."""
    entries: List[Dict[str, str]] = []
    if not rules_dir.exists():
        return entries
    files = list(rules_dir.rglob("*.yaml")) + list(rules_dir.rglob("*.yml"))
    for path in sorted(files):
        relpath = str(path.relative_to(rules_dir))
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        for key in RULE_KEYS:
            for item in data.get(key, []) or []:
                if not isinstance(item, dict):
                    continue
                entries.append(
                    {
                        "file": relpath,
                        "category": key,
                        "name": str(item.get("name", "")),
                        "description": str(item.get("description", "")),
                        "version": str(item.get("version", "")),
                        "use": str(item.get("use", "")),
                    }
                )
    return entries


def spec_categories_from_rules(rule_entries: List[Dict[str, str]]) -> Dict[str, str]:
    """Derive spec category labels from rule entries."""
    mapping: Dict[str, Set[str]] = {}
    for entry in rule_entries:
        category = entry.get("category", "")
        if category not in {"info_spec", "metadata_spec"}:
            continue
        use = entry.get("use", "")
        if not use:
            continue
        spec_name = Path(use).name if use else ""
        if not spec_name:
            continue
        mapping.setdefault(spec_name, set()).add(category)
    return {name: ", ".join(sorted(cats)) for name, cats in mapping.items()}


__all__ = [
    "add",
    "add_spec_data",
    "add_pruner_spec_data",
    "add_rule_data",
    "install_defaults",
    "list_installed",
    "remove",
    "resolve_targets",
    "add_from_yaml",
    "classify_yaml",
    "update_transforms_source",
    "install_transforms_from_spec",
    "ensure_rule_specs_present",
    "ensure_spec_category",
    "load_rule_entries",
    "spec_categories_from_rules",
]
