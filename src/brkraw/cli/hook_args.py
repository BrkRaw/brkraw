from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping

import yaml


def merge_hook_args(
    base: Mapping[str, Mapping[str, Any]],
    override: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for hook_name, values in base.items():
        if not isinstance(hook_name, str) or not hook_name:
            continue
        if not isinstance(values, Mapping):
            continue
        merged[hook_name] = dict(values)
    for hook_name, values in override.items():
        if not isinstance(hook_name, str) or not hook_name:
            continue
        if not isinstance(values, Mapping):
            continue
        merged.setdefault(hook_name, {}).update(dict(values))
    return merged


def load_hook_args_yaml(paths: List[str]) -> Dict[str, Dict[str, Any]]:
    """Load hook args mapping from YAML files.

    Supported YAML formats:
      - `{hooks: {hook_name: {key: value}}}`
      - `{hook_name: {key: value}}`
    """

    merged: Dict[str, Dict[str, Any]] = {}

    def normalize_doc(doc: Any, *, source: str) -> Dict[str, Dict[str, Any]]:
        if doc is None:
            return {}
        hooks_obj = doc.get("hooks") if isinstance(doc, Mapping) else None
        if hooks_obj is None and isinstance(doc, Mapping):
            hooks_obj = doc
        if not isinstance(hooks_obj, Mapping):
            raise ValueError(f"Invalid hook args YAML in {source!r}: expected mapping.")

        out: Dict[str, Dict[str, Any]] = {}
        for hook_name, values in hooks_obj.items():
            if not isinstance(hook_name, str) or not hook_name.strip():
                continue
            if values is None:
                continue
            if not isinstance(values, Mapping):
                raise ValueError(
                    f"Invalid hook args YAML in {source!r}: hook {hook_name!r} must map to a dict."
                )
            out[hook_name.strip()] = dict(values)
        return out

    for raw in paths:
        source = raw.strip()
        if not source:
            continue
        if source == "-":
            doc = yaml.safe_load(sys.stdin.read())
        else:
            path = Path(source).expanduser()
            if not path.exists():
                raise ValueError(f"Hook args YAML not found: {source}")
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        parsed = normalize_doc(doc, source=source)
        merged = merge_hook_args(merged, parsed)

    return merged


__all__ = ["load_hook_args_yaml", "merge_hook_args"]

