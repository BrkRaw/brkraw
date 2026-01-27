from __future__ import annotations

import os
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

ENV_CONFIG_HOME = "BRKRAW_CONFIG_HOME"
DEFAULT_PROFILE_DIRNAME = ".brkraw"
CONFIG_VERSION = 0

DEFAULT_CONFIG_YAML = """# brkraw user configuration
# This file is optional. Delete it to fall back to package defaults.
# You can override the config root by setting BRKRAW_CONFIG_HOME.
config_version: 0

# Editor command used by brkraw config/addon edit.
editor: null

logging:
  level: INFO
  print_width: 120

output:
  # output.layout_entries defines how NIfTI filenames are built.
  layout_entries:
    - key: Subject.ID
      entry: sub
      hide: false
    - key: Study.ID
      entry: study
      hide: false
    - key: ScanID
      entry: scan
      hide: false
    - key: Protocol
      hide: true
  layout_template: null
  slicepack_suffix: "_slpack{index}"
  # float_decimals: 6

# Viewer settings for brkraw-viewer (optional GUI extension).
viewer:
  cache:
    # Cache loaded scan data in memory to speed up space/pose changes.
    enabled: true
    # Maximum number of scan/reco entries to keep (LRU). 0 disables caching.
    max_items: 10

# rules_dir: rules
# specs_dir: specs
# pruner_specs_dir: pruner_specs
# transforms_dir: transforms
"""


@dataclass(frozen=True)
class ConfigPaths:
    root: Path
    config_file: Path
    specs_dir: Path
    pruner_specs_dir: Path
    rules_dir: Path
    transforms_dir: Path
    cache_dir: Path


def resolve_root(root: Optional[Union[str, Path]] = None) -> Path:
    if root is not None:
        return Path(root).expanduser()
    env_root = os.environ.get(ENV_CONFIG_HOME)
    if env_root:
        return Path(env_root).expanduser()
    return Path.home() / DEFAULT_PROFILE_DIRNAME


def get_paths(root: Optional[Union[str, Path]] = None) -> ConfigPaths:
    base = resolve_root(root)
    return ConfigPaths(
        root=base,
        config_file=base / "config.yaml",
        specs_dir=base / "specs",
        pruner_specs_dir=base / "pruner_specs",
        rules_dir=base / "rules",
        transforms_dir=base / "transforms",
        cache_dir=base / "cache",
    )


def paths(root: Optional[Union[str, Path]] = None) -> ConfigPaths:
    return get_paths(root=root)


def get_path(name: str, root: Optional[Union[str, Path]] = None) -> Path:
    paths_obj = get_paths(root=root)
    mapping = {
        "root": paths_obj.root,
        "config": paths_obj.config_file,
        "specs": paths_obj.specs_dir,
        "pruner_specs": paths_obj.pruner_specs_dir,
        "rules": paths_obj.rules_dir,
        "transforms": paths_obj.transforms_dir,
        "cache": paths_obj.cache_dir,
    }
    if name not in mapping:
        raise KeyError(f"Unknown config path: {name}")
    return mapping[name]


def is_initialized(root: Optional[Union[str, Path]] = None) -> bool:
    paths = get_paths(root)
    return paths.config_file.exists()


def ensure_initialized(
    root: Optional[Union[str, Path]] = None,
    *,
    create_config: bool = True,
    exist_ok: bool = True,
) -> ConfigPaths:
    paths = get_paths(root)
    if paths.root.exists() and not exist_ok:
        raise FileExistsError(paths.root)
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.specs_dir.mkdir(parents=True, exist_ok=True)
    paths.pruner_specs_dir.mkdir(parents=True, exist_ok=True)
    paths.rules_dir.mkdir(parents=True, exist_ok=True)
    paths.transforms_dir.mkdir(parents=True, exist_ok=True)
    paths.cache_dir.mkdir(parents=True, exist_ok=True)
    if create_config and not paths.config_file.exists():
        paths.config_file.write_text(DEFAULT_CONFIG_YAML, encoding="utf-8")
    return paths


def init(
    root: Optional[Union[str, Path]] = None,
    *,
    create_config: bool = True,
    exist_ok: bool = True,
) -> ConfigPaths:
    return ensure_initialized(root=root, create_config=create_config, exist_ok=exist_ok)


def cache_dir(root: Optional[Union[str, Path]] = None) -> Path:
    return get_paths(root=root).cache_dir


def load_config(root: Optional[Union[str, Path]] = None) -> Optional[Dict[str, Any]]:
    paths = get_paths(root)
    if not paths.config_file.exists():
        return None
    with paths.config_file.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("config.yaml must contain a YAML mapping at the top level.")
    return data


def load(root: Optional[Union[str, Path]] = None) -> Optional[Dict[str, Any]]:
    return load_config(root=root)


def write_config(data: Dict[str, Any], root: Optional[Union[str, Path]] = None) -> None:
    data = _normalize_config(dict(data))
    data["config_version"] = CONFIG_VERSION
    paths = ensure_initialized(root=root, create_config=False, exist_ok=True)
    paths.config_file.write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )


def reset_config(root: Optional[Union[str, Path]] = None) -> None:
    paths = ensure_initialized(root=root, create_config=False, exist_ok=True)
    paths.config_file.write_text(DEFAULT_CONFIG_YAML, encoding="utf-8")


def default_config() -> Dict[str, Any]:
    data = yaml.safe_load(DEFAULT_CONFIG_YAML)
    if not isinstance(data, dict):
        return {}
    return _normalize_config(data)


def resolve_config(root: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    defaults = default_config()
    overrides = _normalize_config(load(root=root) or {})
    overrides.pop("nifti_filename_template", None)
    overrides.pop("output_format", None)
    overrides["config_version"] = CONFIG_VERSION
    defaults.pop("nifti_filename_template", None)
    defaults.pop("output_format", None)
    return _deep_merge(defaults, overrides)


def resolve_editor_binary(root: Optional[Union[str, Path]] = None) -> Optional[str]:
    config = resolve_config(root=root)
    editor = config.get("editor")
    if not isinstance(editor, str) or not editor.strip():
        editor = config.get("editor_binary")
    if isinstance(editor, str) and editor.strip():
        return editor.strip()
    env_editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if isinstance(env_editor, str) and env_editor.strip():
        return env_editor.strip()
    return None


def clear_config(
    root: Optional[Union[str, Path]] = None,
    *,
    keep_config: bool = False,
    keep_rules: bool = False,
    keep_specs: bool = False,
    keep_pruner_specs: bool = False,
    keep_transforms: bool = False,
    keep_cache: bool = False,
) -> None:
    paths = get_paths(root=root)
    if not paths.root.exists():
        return
    if paths.config_file.exists() and not keep_config:
        paths.config_file.unlink()
    if paths.rules_dir.exists() and not keep_rules:
        _remove_tree(paths.rules_dir)
    if paths.specs_dir.exists() and not keep_specs:
        _remove_tree(paths.specs_dir)
    if paths.pruner_specs_dir.exists() and not keep_pruner_specs:
        _remove_tree(paths.pruner_specs_dir)
    if paths.transforms_dir.exists() and not keep_transforms:
        _remove_tree(paths.transforms_dir)
    if paths.cache_dir.exists() and not keep_cache:
        _remove_tree(paths.cache_dir)
    try:
        paths.root.rmdir()
    except OSError:
        pass


def clear(
    root: Optional[Union[str, Path]] = None,
    *,
    keep_config: bool = False,
    keep_rules: bool = False,
    keep_specs: bool = False,
    keep_pruner_specs: bool = False,
    keep_transforms: bool = False,
    keep_cache: bool = False,
) -> None:
    clear_config(
        root=root,
        keep_config=keep_config,
        keep_rules=keep_rules,
        keep_specs=keep_specs,
        keep_pruner_specs=keep_pruner_specs,
        keep_transforms=keep_transforms,
        keep_cache=keep_cache,
    )


def configure_logging(
    *,
    name: Optional[str] = None,
    root: Optional[Union[str, Path]] = None,
    level: Optional[Union[str, int]] = None,
    stream=None,
) -> logging.Logger:
    if name is None:
        name = "brkraw"
    config = resolve_config(root=root)
    if level is None:
        level = config.get("logging", {}).get("level", "INFO")
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    if not logging.getLogger().handlers:
        if level == logging.INFO:
            fmt = "%(message)s"
        else:
            fmt = "%(asctime)s(%(levelname).1s): %(name)s:%(funcName)s - %(message)s"
        logging.basicConfig(level=level, format=fmt, stream=stream)
    return logging.getLogger(name)


def output_width(root: Optional[Union[str, Path]] = None, default: int = 120) -> int:
    config = resolve_config(root=root)
    width = config.get("logging", {}).get("print_width", default)
    try:
        return int(width)
    except (TypeError, ValueError):
        return default


def float_decimals(root: Optional[Union[str, Path]] = None, default: int = 6) -> int:
    config = resolve_config(root=root)
    output_cfg = config.get("output", {})
    decimals = output_cfg.get("float_decimals", config.get("float_decimals", default))
    try:
        return int(decimals)
    except (TypeError, ValueError):
        return default


def affine_decimals(root: Optional[Union[str, Path]] = None, default: int = 6) -> int:
    return float_decimals(root=root, default=default)


def layout_template(
    root: Optional[Union[str, Path]] = None,
) -> Optional[str]:
    config = resolve_config(root=root)
    output_cfg = config.get("output", {})
    value = output_cfg.get("layout_template")
    if isinstance(value, str) and value.strip():
        return value
    return None


def layout_entries(
    root: Optional[Union[str, Path]] = None,
    default: Optional[list] = None,
) -> list:
    config = resolve_config(root=root)
    output_cfg = config.get("output", {})
    fields = output_cfg.get("layout_entries")
    if fields is None:
        fields = output_cfg.get("layout_fields")
    if fields is None:
        fields = output_cfg.get("format_fields")
    if isinstance(fields, list):
        return fields
    if default is None:
        default = default_config().get("output", {}).get("layout_entries", [])
    return list(default) if isinstance(default, list) else []


def output_slicepack_suffix(
    root: Optional[Union[str, Path]] = None,
    default: str = "_slpack{index}",
) -> str:
    config = resolve_config(root=root)
    value = config.get("output", {}).get("slicepack_suffix", default)
    return str(value) if isinstance(value, str) and value else default


def _normalize_config(data: Dict[str, Any]) -> Dict[str, Any]:
    config = dict(data)
    logging_cfg = dict(config.get("logging") or {})
    output_cfg = dict(config.get("output") or {})

    config.pop("output_format", None)
    if "log_level" in config and "level" not in logging_cfg:
        logging_cfg["level"] = config.pop("log_level")
    if "output_width" in config and "print_width" not in logging_cfg:
        logging_cfg["print_width"] = config.pop("output_width")
    config.pop("output_format_fields", None)
    config.pop("output_format_spec", None)
    if "layout_fields" in output_cfg and "layout_entries" not in output_cfg:
        output_cfg["layout_entries"] = output_cfg["layout_fields"]
    if "float_decimals" in config and "float_decimals" not in output_cfg:
        output_cfg["float_decimals"] = config.pop("float_decimals")
    if "editor_binary" in config and "editor" not in config:
        config["editor"] = config.pop("editor_binary")

    if logging_cfg:
        config["logging"] = logging_cfg
    if output_cfg:
        config["output"] = output_cfg
    return config


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _remove_tree(path: Path) -> None:
    for child in path.iterdir():
        if child.is_dir():
            _remove_tree(child)
        else:
            child.unlink()
    path.rmdir()
