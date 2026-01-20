"""Hook installer utilities for converter hook packages."""

from __future__ import annotations

import importlib
import importlib.metadata
import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union, cast

try:
    from importlib import resources
except ImportError:  # pragma: no cover - fallback for Python 3.8
    import importlib_resources as resources  # type: ignore[assignment]
import yaml

from ...core import config as config_core
from ...core.entrypoints import list_entry_points
from ...specs.hook.logic import DEFAULT_GROUP
from ..addon import installation as addon_install
from ..addon import dependencies as addon_deps
from ..addon.io import write_file as _write_file

logger = logging.getLogger("brkraw")

REGISTRY_FILENAME = "hooks.yaml"
MANIFEST_NAMES = ("brkraw_hook.yaml", "brkraw_hook.yml")


def _metadata_get(
    dist: Optional[importlib.metadata.Distribution],
    key: str,
    default: Optional[str] = None,
) -> Optional[str]:
    """Typed helper to read distribution metadata."""
    if dist is None:
        return default
    meta = cast(Mapping[str, str], dist.metadata)
    return meta.get(key, default)


def _packages_distributions() -> Mapping[str, List[str]]:
    packages_distributions = getattr(importlib.metadata, "packages_distributions", None)
    if packages_distributions is not None:
        return cast(Callable[[], Mapping[str, List[str]]], packages_distributions)()

    mapping: Dict[str, List[str]] = {}
    for dist in importlib.metadata.distributions():
        read_text = getattr(dist, "read_text", None)
        top_level_text = ""
        if callable(read_text):
            top_level = read_text("top_level.txt")
            if isinstance(top_level, str):
                top_level_text = top_level
        dist_name = _metadata_get(dist, "Name")
        if not dist_name:
            continue
        for package in top_level_text.splitlines():
            package = package.strip()
            if package:
                mapping.setdefault(package, []).append(dist_name)
    return mapping


def list_hooks(*, root: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    hooks = _collect_hooks()
    registry = _load_registry(root=root)
    installed = registry.get("hooks", {})
    root_path = config_core.resolve_root(root)
    for hook in hooks:
        entry = installed.get(hook["name"])
        hook["installed"] = bool(entry)
        hook["installed_version"] = entry.get("version") if isinstance(entry, dict) else None
        hook["install_status"] = _install_status(entry, root=root_path)
    return hooks


def install_all(
    *,
    root: Optional[Union[str, Path]] = None,
    upgrade: bool = False,
    force: bool = False,
) -> Dict[str, List[str]]:
    hooks = _collect_hooks()
    installed: List[str] = []
    skipped: List[str] = []
    for hook in hooks:
        status = _install_hook(hook, root=root, upgrade=upgrade, force=force)
        if status == "installed":
            installed.append(hook["name"])
        else:
            skipped.append(hook["name"])
    return {"installed": installed, "skipped": skipped}


def install_hook(
    target: str,
    *,
    root: Optional[Union[str, Path]] = None,
    upgrade: bool = False,
    force: bool = False,
) -> str:
    hook = _resolve_hook_target(target)
    return _install_hook(hook, root=root, upgrade=upgrade, force=force)


def read_hook_docs(
    target: str,
    *,
    root: Optional[Union[str, Path]] = None,
) -> Tuple[str, str]:
    hook = _resolve_hook_target(target)
    manifest_path, manifest = _load_manifest(hook["dist"], hook.get("packages"))
    docs_path = _resolve_docs_path(manifest, manifest_path)
    if docs_path is None:
        raise FileNotFoundError(f"Hook docs not found for {hook['name']}")
    return hook["name"], docs_path.read_text(encoding="utf-8")


def uninstall_hook(
    target: str,
    *,
    root: Optional[Union[str, Path]] = None,
    force: bool = False,
) -> Tuple[str, Dict[str, List[str]], bool]:
    registry = _load_registry(root=root)
    hooks = registry.get("hooks", {})
    hook_name = _resolve_hook_name(target)
    entry = hooks.get(hook_name)
    if entry is None:
        entry_matches = [
            name
            for name, data in hooks.items()
            if target in (data.get("entrypoints") or [])
        ]
        if len(entry_matches) == 1:
            hook_name = entry_matches[0]
            entry = hooks.get(hook_name)
        elif entry_matches:
            names = ", ".join(sorted(entry_matches))
            raise ValueError(f"Multiple hooks match {target}: {names}")
    if entry is None:
        raise LookupError(f"Hook not installed: {hook_name}")
    module_missing = not list_entry_points(DEFAULT_GROUP, name=hook_name)
    removed: Dict[str, List[str]] = {
        "specs": [],
        "pruner_specs": [],
        "rules": [],
        "transforms": [],
    }
    root_path = config_core.resolve_root(root)
    for kind in ("specs", "pruner_specs", "rules", "transforms"):
        for relpath in entry.get(kind, []) if isinstance(entry, dict) else []:
            target_path = root_path / relpath
            if not target_path.exists():
                continue
            if _has_dependencies(target_path, kind, root=root_path) and not force:
                raise RuntimeError("Dependencies found; use --force to remove.")
            target_path.unlink()
            removed[kind].append(relpath)
    hooks.pop(hook_name, None)
    _save_registry(registry, root=root)
    return hook_name, removed, module_missing


def _install_hook(
    hook: Dict[str, Any],
    *,
    root: Optional[Union[str, Path]],
    upgrade: bool,
    force: bool,
) -> str:
    registry = _load_registry(root=root)
    hooks = registry.setdefault("hooks", {})
    existing = hooks.get(hook["name"])
    if isinstance(existing, dict):
        if not upgrade and not force:
            return "skipped"
        if not force:
            installed_version = existing.get("version")
            if installed_version and not _is_version_newer(hook["version"], installed_version):
                return "skipped"
    manifest_path, manifest = _load_manifest(hook["dist"], hook.get("packages"))
    namespace = _namespace_for_hook(hook["name"])
    installed = _install_manifest(
        manifest,
        manifest_path,
        root=root,
        namespace=namespace,
    )
    hooks[hook["name"]] = {
        "version": hook["version"],
        "entrypoints": hook["entrypoints"],
        "namespace": namespace,
        **installed,
    }
    _save_registry(registry, root=root)
    return "installed"


def _kind_to_remove(kind: str) -> str:
    if kind == "specs":
        return "spec"
    if kind == "pruner_specs":
        return "pruner"
    if kind == "rules":
        return "rule"
    if kind == "transforms":
        return "transform"
    raise ValueError(f"Unknown hook kind: {kind}")


def _install_manifest(
    manifest: Mapping[str, Any],
    manifest_path: Path,
    *,
    root: Optional[Union[str, Path]],
    namespace: str,
) -> Dict[str, List[str]]:
    installed: Dict[str, List[str]] = {
        "specs": [],
        "pruner_specs": [],
        "rules": [],
        "transforms": [],
    }
    base_dir = manifest_path.parent
    paths = config_core.paths(root=root)
    spec_basenames = {
        Path(item).name
        for item in _normalize_manifest_list(manifest.get("specs"))
    }
    for spec in _normalize_manifest_list(manifest.get("specs")):
        src = _resolve_manifest_path(base_dir, spec)
        spec_data = _read_yaml(src)
        paths_installed = addon_install.add_spec_data(
            spec_data,
            filename=str(Path(namespace) / src.name),
            source_path=src,
            root=root,
            transforms_dir=paths.transforms_dir / namespace,
        )
        _record_installed_paths(paths_installed, installed, root=root)
    for pruner_spec in _normalize_manifest_list(manifest.get("pruner_specs")):
        src = _resolve_manifest_path(base_dir, pruner_spec)
        spec_data = _read_yaml(src)
        paths_installed = addon_install.add_pruner_spec_data(
            spec_data,
            filename=str(Path(namespace) / src.name),
            source_path=src,
            root=root,
        )
        _record_installed_paths(paths_installed, installed, root=root)
    for rule in _normalize_manifest_list(manifest.get("rules")):
        src = _resolve_manifest_path(base_dir, rule)
        rule_data = _read_yaml(src)
        _rewrite_rule_uses(rule_data, namespace, spec_basenames)
        paths_installed = addon_install.add_rule_data(
            rule_data,
            filename=str(Path(namespace) / src.name),
            source_path=src,
            root=root,
        )
        _record_installed_paths(paths_installed, installed, root=root)
    for transform in _normalize_manifest_list(manifest.get("transforms")):
        src = _resolve_manifest_path(base_dir, transform)
        target = paths.transforms_dir / namespace / src.name
        _write_file(target, src.read_text(encoding="utf-8"))
        installed["transforms"].append(_relative_to_root(target, root=root))
        logger.info("Installed transforms: %s", target)
    return installed


def _record_installed_paths(
    paths: Sequence[Path],
    installed: Dict[str, List[str]],
    *,
    root: Optional[Union[str, Path]],
) -> None:
    config_paths = config_core.paths(root=root)
    for path in paths:
        relpath = _relative_to_root(path, root=root)
        try:
            path.relative_to(config_paths.specs_dir)
        except ValueError:
            pass
        else:
            installed["specs"].append(relpath)
            continue
        try:
            path.relative_to(config_paths.pruner_specs_dir)
        except ValueError:
            pass
        else:
            installed["pruner_specs"].append(relpath)
            continue
        try:
            path.relative_to(config_paths.rules_dir)
        except ValueError:
            pass
        else:
            installed["rules"].append(relpath)
            continue
        try:
            path.relative_to(config_paths.transforms_dir)
        except ValueError:
            continue
        installed["transforms"].append(relpath)


def _normalize_manifest_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        items = [item for item in value if isinstance(item, str) and item.strip()]
        return items
    raise ValueError("Manifest entries must be a list of strings.")


def _resolve_manifest_path(base_dir: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def _read_yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        raise ValueError(f"Empty YAML file: {path}")
    if not isinstance(data, dict):
        raise ValueError(f"YAML file must be a mapping: {path}")
    return data


def _collect_hooks() -> List[Dict[str, Any]]:
    hooks: Dict[str, Dict[str, Any]] = {}
    for ep in list_entry_points(DEFAULT_GROUP):
        dist = _resolve_distribution(ep)
        dist_name = _dist_name(dist) or ep.name
        entry = hooks.setdefault(
            dist_name,
            {
                "name": dist_name,
                "entrypoints": [],
                "packages": set(),
                "dist": dist,
                "version": _dist_version(dist),
                "author": _dist_author(dist),
                "description": _dist_description(dist),
            },
        )
        entry["entrypoints"].append(ep.name)
        pkg = _entrypoint_package(ep)
        if pkg:
            entry["packages"].add(pkg)
    for hook in hooks.values():
        packages = hook.get("packages")
        if isinstance(packages, set):
            hook["packages"] = sorted(packages)
    return sorted(hooks.values(), key=lambda item: item["name"])


def _resolve_hook_target(target: str) -> Dict[str, Any]:
    hooks = _collect_hooks()
    name_matches = [hook for hook in hooks if hook["name"] == target]
    if len(name_matches) == 1:
        return name_matches[0]
    entry_matches = [
        hook for hook in hooks if target in hook.get("entrypoints", [])
    ]
    if len(entry_matches) == 1:
        return entry_matches[0]
    if not name_matches and not entry_matches:
        raise LookupError(f"Unknown hook: {target}")
    names = sorted({hook["name"] for hook in name_matches + entry_matches})
    raise ValueError(f"Multiple hooks match {target}: {', '.join(names)}")


def _resolve_hook_name(target: str) -> str:
    try:
        return _resolve_hook_target(target)["name"]
    except LookupError:
        return target


def _resolve_distribution(ep: importlib.metadata.EntryPoint) -> Optional[importlib.metadata.Distribution]:
    dist = getattr(ep, "dist", None)
    if dist is not None:
        return dist
    pkg = getattr(ep, "module", "").split(".")[0]
    if not pkg:
        return None
    mapping = _packages_distributions()
    dist_names = mapping.get(pkg, [])
    if not dist_names:
        return None
    try:
        return importlib.metadata.distribution(dist_names[0])
    except importlib.metadata.PackageNotFoundError:
        return None


def _dist_name(dist: Optional[importlib.metadata.Distribution]) -> Optional[str]:
    if dist is None:
        return None
    return _metadata_get(dist, "Name")


def _dist_version(dist: Optional[importlib.metadata.Distribution]) -> str:
    if dist is None:
        return "<Unknown>"
    return _metadata_get(dist, "Version", "<Unknown>") or "<Unknown>"


def _dist_description(dist: Optional[importlib.metadata.Distribution]) -> str:
    if dist is None:
        return "<Unknown>"
    return _metadata_get(dist, "Summary", "<Unknown>") or "<Unknown>"


def _dist_author(dist: Optional[importlib.metadata.Distribution]) -> str:
    if dist is None:
        return "<Unknown>"
    for key in ("Author", "Author-email", "Maintainer", "Maintainer-email"):
        value = _metadata_get(dist, key)
        if value:
            return value
    return "<Unknown>"


def _load_manifest(
    dist: Optional[importlib.metadata.Distribution],
    packages: Optional[Sequence[str]] = None,
) -> Tuple[Path, Dict[str, Any]]:
    if dist is None:
        raise FileNotFoundError("Hook distribution not available.")
    manifest = _find_manifest(dist, packages=packages)
    if manifest is None:
        raise FileNotFoundError(
            f"No hook manifest found in {_metadata_get(dist, 'Name', '<Unknown>')}"
        )
    data = _read_yaml(manifest)
    return manifest, data


def _find_manifest(
    dist: importlib.metadata.Distribution,
    *,
    packages: Optional[Sequence[str]] = None,
) -> Optional[Path]:
    files = dist.files or []
    for name in MANIFEST_NAMES:
        for entry in files:
            if entry.name == name:
                return Path(str(dist.locate_file(entry)))
    search_packages = list(packages or []) or _dist_top_level(dist)
    for package in search_packages:
        for name in MANIFEST_NAMES:
            try:
                candidate = resources.files(package).joinpath(name)
            except Exception:
                candidate = None
            if candidate is not None and candidate.is_file():
                return Path(str(candidate))
        fallback = _find_manifest_in_module(package)
        if fallback is not None:
            return fallback
    return None


def _entrypoint_package(ep: importlib.metadata.EntryPoint) -> Optional[str]:
    module = getattr(ep, "module", None)
    if not module:
        value = getattr(ep, "value", "")
        module = value.split(":", 1)[0] if value else ""
    if not module:
        return None
    return module.split(".", 1)[0]


def _find_manifest_in_module(package: str) -> Optional[Path]:
    try:
        module = importlib.import_module(package)
    except Exception:
        return None
    module_file = getattr(module, "__file__", None)
    if not module_file:
        return None
    base = Path(module_file).resolve().parent
    for name in MANIFEST_NAMES:
        candidate = base / name
        if candidate.is_file():
            return candidate
    return None


def _dist_top_level(dist: importlib.metadata.Distribution) -> List[str]:
    raw = dist.read_text("top_level.txt")
    if not raw:
        return []
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _registry_path(root: Optional[Union[str, Path]]) -> Path:
    base = config_core.resolve_root(root)
    return base / REGISTRY_FILENAME


def _load_registry(*, root: Optional[Union[str, Path]]) -> Dict[str, Any]:
    path = _registry_path(root)
    if not path.exists():
        return {"hooks": {}}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"hooks": {}}
    if "hooks" not in data:
        data["hooks"] = {}
    return data


def _save_registry(data: Mapping[str, Any], *, root: Optional[Union[str, Path]]) -> None:
    config_core.ensure_initialized(root=root, create_config=True, exist_ok=True)
    path = _registry_path(root)
    content = yaml.safe_dump(dict(data), sort_keys=False)
    path.write_text(content, encoding="utf-8")


def _is_version_newer(version: str, installed: str) -> bool:
    if version == "<Unknown>" or installed == "<Unknown>":
        return True
    try:
        from packaging.version import Version  # type: ignore
    except Exception:
        return _compare_fallback(version, installed) > 0
    return Version(version) > Version(installed)


def _compare_fallback(a: str, b: str) -> int:
    def _split(value: str) -> Tuple[Tuple[int, ...], str]:
        nums = tuple(int(item) for item in re.findall(r"\d+", value))
        return nums, value

    a_nums, a_raw = _split(a)
    b_nums, b_raw = _split(b)
    if a_nums != b_nums:
        return (a_nums > b_nums) - (a_nums < b_nums)
    return (a_raw > b_raw) - (a_raw < b_raw)


def _namespace_for_hook(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "hook"


def _rewrite_rule_uses(rule_data: Dict[str, Any], namespace: str, spec_basenames: set[str]) -> None:
    for key in addon_deps.RULE_KEYS:
        if key == "converter_hook":
            continue
        entries = rule_data.get(key) or []
        if not isinstance(entries, list):
            continue
        for item in entries:
            if not isinstance(item, dict):
                continue
            use = item.get("use")
            if not isinstance(use, str):
                continue
            base = Path(use).name
            if base in spec_basenames:
                item["use"] = str(Path("specs") / namespace / base)


def _relative_to_root(path: Path, *, root: Optional[Union[str, Path]]) -> str:
    base = config_core.resolve_root(root)
    try:
        return str(path.resolve().relative_to(base))
    except ValueError:
        return str(path.name)


def _has_dependencies(
    target: Path,
    kind: str,
    *,
    root: Optional[Union[str, Path]],
) -> bool:
    try:
        return addon_deps.warn_dependencies(target, kind=_kind_to_remove(kind), root=root)
    except Exception:
        return False


def _resolve_docs_path(manifest: Mapping[str, Any], manifest_path: Path) -> Optional[Path]:
    value = manifest.get("docs")
    if not value:
        value = manifest.get("readme")
    if not isinstance(value, str):
        return None
    return _resolve_manifest_path(manifest_path.parent, value)


def _install_status(entry: Any, *, root: Path) -> str:
    if not isinstance(entry, dict):
        return "No"
    paths: List[str] = []
    for kind in ("specs", "pruner_specs", "rules", "transforms"):
        items = entry.get(kind, [])
        if isinstance(items, list):
            paths.extend([item for item in items if isinstance(item, str) and item.strip()])
    if not paths:
        return "Yes"
    missing = 0
    for relpath in paths:
        if not (root / relpath).exists():
            missing += 1
    if missing == 0:
        return "Yes"
    return "Partially"

    a_nums, a_raw = _split(a)
    b_nums, b_raw = _split(b)
    if a_nums != b_nums:
        return (a_nums > b_nums) - (a_nums < b_nums)
    return (a_raw > b_raw) - (a_raw < b_raw)


__all__ = [
    "install_all",
    "install_hook",
    "list_hooks",
    "uninstall_hook",
]
