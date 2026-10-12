from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional
from importlib import resources

try:
    resources.files  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - fallback for Python 3.8
    import importlib_resources as resources  # type: ignore[assignment]

import yaml

from ..meta import validate_meta

def validate_prune_spec(spec: Mapping[str, Any], schema_path: Optional[Path] = None) -> List[str]:
    """Validate a prune spec against schema.

    Args:
        spec: Parsed prune spec mapping.
        schema_path: Optional schema path override.

    Returns:
        List of validation error messages (empty when valid).
    """
    errors: List[str] = []
    try:
        import jsonschema
    except Exception:
        errors = _validate_spec_minimal(spec)
    else:
        schema = _load_schema(schema_path)
        validator = jsonschema.Draft202012Validator(schema)
        for err in validator.iter_errors(spec):
            path = ".".join(str(p) for p in err.path)
            prefix = f"spec.{path}" if path else "spec"
            errors.append(f"{prefix}: {err.message}")

    errors.extend(
        validate_meta(
            spec.get("__meta__"),
            raise_on_error=False,
        )
    )
    if errors:
        raise ValueError("Invalid prune spec:\n" + "\n".join(errors))
    return errors


def _load_schema(schema_path: Optional[Path]) -> Dict[str, Any]:
    if schema_path is not None:
        return yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    if __package__ is None:
        raise RuntimeError("Package context required to load pruner schema.")
    with resources.files("brkraw.schema").joinpath("pruner.yaml").open(
        "r", encoding="utf-8"
    ) as handle:
        return yaml.safe_load(handle)


def _validate_spec_minimal(spec: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(spec, Mapping):
        errors.append("spec: must be a mapping.")
        return errors

    if "__meta__" not in spec:
        errors.append("spec.__meta__: is required.")
    else:
        errors.extend(
            validate_meta(
                spec.get("__meta__"),
                raise_on_error=False,
            )
        )

    files = spec.get("files")
    if not isinstance(files, list) or not files:
        errors.append("spec.files: must be a non-empty list.")
    else:
        for idx, item in enumerate(files):
            if not isinstance(item, (str, int)):
                errors.append(f"spec.files[{idx}]: must be string or int.")

    mode = spec.get("mode", "keep")
    if mode not in {"keep", "drop"}:
        errors.append("spec.mode: must be 'keep' or 'drop'.")

    update_params = spec.get("update_params")
    if update_params is not None and not isinstance(update_params, Mapping):
        errors.append("spec.update_params: must be a mapping.")

    dirs = spec.get("dirs")
    if dirs is not None and not isinstance(dirs, list):
        errors.append("spec.dirs: must be a list.")
    if isinstance(dirs, list):
        for idx, rule in enumerate(dirs):
            if not isinstance(rule, Mapping):
                errors.append(f"spec.dirs[{idx}]: must be a mapping.")
                continue
            level = rule.get("level")
            if not isinstance(level, int) or level < 1:
                errors.append(f"spec.dirs[{idx}].level: must be int >= 1.")
            dirs = rule.get("dirs")
            if not isinstance(dirs, list) or not dirs:
                errors.append(f"spec.dirs[{idx}].dirs: must be a non-empty list.")

    add_root = spec.get("add_root")
    if add_root is not None and not isinstance(add_root, bool):
        errors.append("spec.add_root: must be boolean.")

    root_name = spec.get("root_name")
    if root_name is not None and not isinstance(root_name, str):
        errors.append("spec.root_name: must be a string.")

    anonymize = spec.get("anonymize")
    if anonymize is not None and not isinstance(anonymize, bool):
        errors.append("spec.anonymize: must be true or false.")

    headers = spec.get("jcamp_headers")
    if headers is not None:
        if not isinstance(headers, Mapping):
            errors.append("spec.jcamp_headers: must be a mapping of header names to values.")
        else:
            for key, value in headers.items():
                if not isinstance(key, str) or not key or key.startswith("$"):
                    errors.append(f"spec.jcamp_headers: invalid header name {key!r}.")
                if value is None or isinstance(value, (Mapping, list)):
                    errors.append(f"spec.jcamp_headers.{key}: must be a text value.")

    return errors


__all__ = ["validate_prune_spec"]
