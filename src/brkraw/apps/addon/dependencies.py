"""Dependency and reference helpers for addon specs and rules."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import yaml

from ...core import config as config_core

logger = logging.getLogger("brkraw")

RULE_KEYS = {"info_spec", "metadata_spec", "converter_hook"}
_SPEC_EXTS = (".yaml", ".yml")


def warn_dependencies(target: Path, *, kind: str, root: Optional[Union[str, Path]]) -> bool:
    paths = config_core.paths(root=root)
    warned = False
    if kind == "spec":
        used_by_rules = rules_using_spec(target.name, paths.rules_dir)
        if used_by_rules:
            logger.warning(
                "Spec %s is referenced by rules: %s",
                target.name,
                ", ".join(sorted(used_by_rules)),
            )
            warned = True
        included_by = specs_including_spec(target.name, paths.specs_dir)
        if included_by:
            logger.warning(
                "Spec %s is included by: %s",
                target.name,
                ", ".join(sorted(included_by)),
            )
            warned = True
    elif kind == "transform":
        transform_ref = normalize_transform_ref(
            str(target),
            spec_path=target,
            transforms_dir=paths.transforms_dir,
        )
        used_by_specs = specs_using_transform(transform_ref, paths.specs_dir)
        if used_by_specs:
            logger.warning(
                "Transform %s is referenced by specs: %s",
                target.name,
                ", ".join(sorted(used_by_specs)),
            )
            warned = True
    return warned


def rules_using_spec(spec_name: str, rules_dir: Path) -> Set[str]:
    used_by: Set[str] = set()
    if not rules_dir.exists():
        return used_by
    files = list(rules_dir.rglob("*.yaml")) + list(rules_dir.rglob("*.yml"))
    for path in files:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        for key in RULE_KEYS:
            if key == "converter_hook":
                continue
            for item in data.get(key, []) or []:
                if not isinstance(item, dict):
                    continue
                use = item.get("use")
                if isinstance(use, str) and Path(use).name == spec_name:
                    used_by.add(path.name)
    return used_by


def specs_including_spec(spec_name: str, specs_dir: Path) -> Set[str]:
    included_by: Set[str] = set()
    if not specs_dir.exists():
        return included_by
    files = list(specs_dir.rglob("*.yaml")) + list(specs_dir.rglob("*.yml"))
    for path in files:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        meta = data.get("__meta__")
        include_list: List[str] = []
        if isinstance(meta, dict) and "include" in meta:
            include = meta.get("include")
            if isinstance(include, str):
                include_list = [include]
            elif isinstance(include, list) and all(isinstance(item, str) for item in include):
                include_list = include
        if any(Path(item).name == spec_name for item in include_list):
            included_by.add(path.name)
    return included_by


def extract_transforms_source(spec_data: Dict[str, Any]) -> List[str]:
    """Collect transforms_source entries from a spec mapping."""
    sources: List[str] = []
    meta = spec_data.get("__meta__")
    if isinstance(meta, dict) and meta.get("transforms_source"):
        src = meta["transforms_source"]
        if isinstance(src, str):
            sources.append(src)
        elif isinstance(src, list) and all(isinstance(item, str) for item in src):
            sources.extend(src)
        else:
            raise ValueError("transforms_source must be a string or list of strings.")
    for value in spec_data.values():
        if not isinstance(value, dict):
            continue
        child_meta = value.get("__meta__")
        if isinstance(child_meta, dict) and child_meta.get("transforms_source"):
            src = child_meta["transforms_source"]
            if isinstance(src, str):
                sources.append(src)
            elif isinstance(src, list) and all(isinstance(item, str) for item in src):
                sources.extend(src)
            else:
                raise ValueError("transforms_source must be a string or list of strings.")
    return sources


def collect_transforms_sources(spec_path: Path, stack: Optional[Set[Path]] = None) -> Set[str]:
    """Collect transforms_source entries from a spec file, including includes."""
    if stack is None:
        stack = set()
    spec_path = spec_path.resolve()
    if spec_path in stack:
        return set()
    stack.add(spec_path)
    try:
        spec_data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        if not isinstance(spec_data, dict):
            return set()
        sources = set(extract_transforms_source(spec_data))
        meta = spec_data.get("__meta__")
        include_list: List[str] = []
        if isinstance(meta, dict) and "include" in meta:
            include = meta.get("include")
            if isinstance(include, str):
                include_list = [include]
            elif isinstance(include, list) and all(isinstance(item, str) for item in include):
                include_list = include
        for item in include_list:
            inc_path = Path(item)
            if not inc_path.is_absolute():
                inc_path = (spec_path.parent / inc_path).resolve()
            if not inc_path.exists():
                logger.warning("Spec include not found while listing: %s", inc_path)
                continue
            sources.update(collect_transforms_sources(inc_path, stack))
        return sources
    finally:
        stack.remove(spec_path)


def normalize_transform_ref(
    src: str,
    *,
    spec_path: Path,
    transforms_dir: Path,
) -> str:
    candidate = Path(src)
    if not candidate.is_absolute():
        candidate = (spec_path.parent / candidate).resolve()
    try:
        return str(candidate.relative_to(transforms_dir))
    except ValueError:
        return candidate.name


def specs_using_transform(transform_ref: str, specs_dir: Path) -> Set[str]:
    used_by: Set[str] = set()
    if not specs_dir.exists():
        return used_by
    files = list(specs_dir.rglob("*.yaml")) + list(specs_dir.rglob("*.yml"))
    for path in files:
        for src in collect_transforms_sources(path):
            normalized = normalize_transform_ref(
                src,
                spec_path=path,
                transforms_dir=specs_dir.parent / "transforms",
            )
            if normalized == transform_ref:
                used_by.add(str(path.relative_to(specs_dir)))
                break
    return used_by


def resolve_spec_path(use: str, base: Path) -> Path:
    """Resolve rule `use` values into absolute spec paths."""
    candidate = Path(use)
    if candidate.is_absolute():
        return candidate
    if candidate.parts and candidate.parts[0] == "specs":
        return base / candidate
    return base / "specs" / candidate


def looks_like_spec_path(use: str) -> bool:
    return (
        "/" in use
        or "\\" in use
        or use.endswith(_SPEC_EXTS)
        or use.startswith(".")
    )


def version_key(value: str) -> Tuple[Tuple[int, Union[int, str]], ...]:
    parts = [p for p in re.split(r"[.\-_+]", value) if p]
    key: List[Tuple[int, Union[int, str]]] = []
    for part in parts:
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part))
    return tuple(key)


def select_latest(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    def _key(item: Dict[str, Any]) -> Tuple[Tuple[int, Union[int, str]], ...]:
        version = item.get("version")
        return version_key(version) if isinstance(version, str) else tuple()

    best = max(records, key=_key)
    best_key = _key(best)
    tied = [item for item in records if _key(item) == best_key]
    if len(tied) > 1:
        files = ", ".join(sorted(item["file"] for item in tied))
        raise ValueError(f"Multiple specs share the latest version: {files}")
    return best


def load_spec_meta(path: Path) -> Dict[str, str]:
    """Load __meta__ name/description from a spec file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    meta = data.get("__meta__")
    if not isinstance(meta, dict):
        return {}
    name = meta.get("name")
    desc = meta.get("description")
    version = meta.get("version")
    category = meta.get("category")
    out: Dict[str, str] = {}
    if isinstance(name, str):
        out["name"] = name
    if isinstance(desc, str):
        out["description"] = desc
    if isinstance(version, str):
        out["version"] = version
    if isinstance(category, str):
        out["category"] = category
    return out


def load_spec_records(specs_dir: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if not specs_dir.exists():
        return records
    spec_files = list(specs_dir.rglob("*.yml")) + list(specs_dir.rglob("*.yaml"))
    for spec_path in sorted(spec_files):
        relpath = str(spec_path.relative_to(specs_dir))
        meta = load_spec_meta(spec_path)
        records.append(
            {
                "file": relpath,
                "path": spec_path,
                "name": meta.get("name"),
                "version": meta.get("version"),
                "description": meta.get("description"),
                "category": meta.get("category"),
            }
        )
    return records


def load_pruner_spec_records(specs_dir: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if not specs_dir.exists():
        return records
    spec_files = list(specs_dir.rglob("*.yml")) + list(specs_dir.rglob("*.yaml"))
    for spec_path in sorted(spec_files):
        relpath = str(spec_path.relative_to(specs_dir))
        meta = load_spec_meta(spec_path)
        records.append(
            {
                "file": relpath,
                "path": spec_path,
                "name": meta.get("name"),
                "version": meta.get("version"),
                "description": meta.get("description"),
                "category": meta.get("category"),
            }
        )
    return records


def resolve_spec_by_name(
    name: str,
    *,
    category: Optional[str],
    version: Optional[str],
    base: Path,
) -> Path:
    paths = config_core.paths(root=base)
    records = [r for r in load_spec_records(paths.specs_dir) if r.get("name") == name]
    label = f"{category}:{name}" if category else name
    if not records:
        raise FileNotFoundError(f"Spec name not found: {label}")
    if category:
        records = [r for r in records if r.get("category") == category]
        if not records:
            raise FileNotFoundError(f"Spec category/name not found: {label}")
    if version:
        matches = [r for r in records if r.get("version") == version]
        if not matches:
            raise FileNotFoundError(f"Spec name/version not found: {label}@{version}")
        if len(matches) > 1:
            files = ", ".join(sorted(item["file"] for item in matches))
            raise ValueError(f"Multiple specs share the same version for {name}: {files}")
        return matches[0]["path"]
    selected = select_latest(records)
    return selected["path"]


def resolve_spec_reference(
    use: str,
    *,
    category: Optional[str] = None,
    version: Optional[str] = None,
    root: Optional[Union[str, Path]] = None,
) -> Path:
    base = config_core.resolve_root(root)
    if looks_like_spec_path(use):
        spec_path = resolve_spec_path(use, base)
        if not spec_path.exists():
            raise FileNotFoundError(
                f"{spec_path} not found. Install the spec before adding rules."
            )
        return spec_path
    return resolve_spec_by_name(use, category=category, version=version, base=base)


def resolve_pruner_spec_reference(
    use: str,
    *,
    version: Optional[str] = None,
    root: Optional[Union[str, Path]] = None,
) -> Path:
    base = config_core.resolve_root(root)
    candidate = Path(use)
    if candidate.is_absolute():
        return candidate
    if candidate.parts and candidate.parts[0] == "pruner_specs":
        spec_path = base / candidate
        if spec_path.exists():
            return spec_path
    if candidate.suffix.lower() in _SPEC_EXTS:
        spec_path = base / "pruner_specs" / candidate
        if spec_path.exists():
            return spec_path
    paths = config_core.paths(root=base)
    records = [r for r in load_pruner_spec_records(paths.pruner_specs_dir) if r.get("name") == use]
    if not records:
        raise FileNotFoundError(f"Pruner spec name not found: {use}")
    if version:
        matches = [r for r in records if r.get("version") == version]
        if not matches:
            raise FileNotFoundError(f"Pruner spec name/version not found: {use}@{version}")
        if len(matches) > 1:
            files = ", ".join(sorted(item["file"] for item in matches))
            raise ValueError(f"Multiple pruner specs share the same version for {use}: {files}")
        return matches[0]["path"]
    selected = select_latest(records)
    return selected["path"]


__all__ = [
    "RULE_KEYS",
    "warn_dependencies",
    "rules_using_spec",
    "specs_including_spec",
    "extract_transforms_source",
    "collect_transforms_sources",
    "specs_using_transform",
    "resolve_spec_path",
    "looks_like_spec_path",
    "version_key",
    "select_latest",
    "load_spec_meta",
    "load_spec_records",
    "load_pruner_spec_records",
    "resolve_spec_by_name",
    "resolve_spec_reference",
    "resolve_pruner_spec_reference",
]
