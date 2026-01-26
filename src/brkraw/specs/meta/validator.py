from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional
from importlib import resources

try:
    resources.files  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - fallback for Python 3.8
    import importlib_resources as resources  # type: ignore[assignment]
import re

import yaml


_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+){0,3}$")


def validate_meta(
    meta: Any,
    *,
    allow_extra_keys: Optional[Iterable[str]] = None,
    raise_on_error: bool = True,
) -> List[str]:
    """Validate a __meta__ mapping.

    Args:
        meta: __meta__ mapping to validate.
        allow_extra_keys: Additional keys allowed in __meta__ beyond the base schema.
        raise_on_error: If True, raise ValueError on validation errors.

    Returns:
        List of validation error messages (empty when valid).
    """
    errors: List[str] = []
    if not isinstance(meta, Mapping):
        errors.append("__meta__: must be an object.")
        if errors and raise_on_error:
            raise ValueError("Invalid __meta__:\n" + "\n".join(errors))
        return errors

    try:
        import jsonschema
    except Exception:
        errors.extend(_validate_meta_minimal(meta, allow_extra_keys=allow_extra_keys))
    else:
        schema = _load_schema()
        if allow_extra_keys:
            schema = _extend_schema(schema, allow_extra_keys)
        validator = jsonschema.Draft202012Validator(schema)
        for err in validator.iter_errors(meta):
            path = ".".join(str(p) for p in err.path)
            prefix = f"__meta__.{path}" if path else "__meta__"
            errors.append(f"{prefix}: {err.message}")

    if errors and raise_on_error:
        raise ValueError("Invalid __meta__:\n" + "\n".join(errors))
    return errors


def _extend_schema(schema: Dict[str, Any], extra_keys: Iterable[str]) -> Dict[str, Any]:
    schema = dict(schema)
    props = dict(schema.get("properties") or {})
    for key in extra_keys:
        if key not in props:
            props[key] = {}
    schema["properties"] = props
    return schema


def _load_schema() -> Dict[str, Any]:
    if __package__ is None:
        raise RuntimeError("Package context required to load meta schema.")
    with resources.files("brkraw.schema").joinpath("meta.yaml").open(
        "r", encoding="utf-8"
    ) as handle:
        return yaml.safe_load(handle)


def _validate_meta_minimal(
    meta: Mapping[str, Any],
    *,
    allow_extra_keys: Optional[Iterable[str]] = None,
) -> List[str]:
    errors: List[str] = []
    name = meta.get("name")
    if not isinstance(name, str) or not name:
        errors.append("__meta__.name: must be a non-empty string.")
    elif not _NAME_PATTERN.match(name):
        errors.append("__meta__.name: must be python-friendly with max 4 tokens.")
    version = meta.get("version")
    if not isinstance(version, str) or not version:
        errors.append("__meta__.version: must be a non-empty string.")
    description = meta.get("description")
    if not isinstance(description, str) or not description:
        errors.append("__meta__.description: must be a non-empty string.")
    category = meta.get("category")
    if not isinstance(category, str) or not category:
        errors.append("__meta__.category: must be a non-empty string.")

    for key in ("authors", "developers"):
        if key not in meta:
            continue
        value = meta.get(key)
        if not isinstance(value, list) or not value:
            errors.append(f"__meta__.{key}: must be a non-empty list.")
            continue
        for idx, item in enumerate(value):
            if not isinstance(item, Mapping):
                errors.append(f"__meta__.{key}[{idx}]: must be an object.")
                continue
            person_name = item.get("name")
            if not isinstance(person_name, str) or not person_name:
                errors.append(f"__meta__.{key}[{idx}].name: must be a non-empty string.")
            email = item.get("email")
            if email is not None and not isinstance(email, str):
                errors.append(f"__meta__.{key}[{idx}].email: must be a string.")
            affiliations = item.get("affiliations")
            if affiliations is not None:
                if not isinstance(affiliations, list) or not affiliations:
                    errors.append(
                        f"__meta__.{key}[{idx}].affiliations: must be a non-empty list."
                    )
                elif not all(isinstance(a, str) and a for a in affiliations):
                    errors.append(
                        f"__meta__.{key}[{idx}].affiliations: must be non-empty strings."
                    )
            extra = set(item.keys()) - {"name", "email", "affiliations"}
            if extra:
                errors.append(
                    f"__meta__.{key}[{idx}]: unexpected keys {sorted(extra)}."
                )

    for key in ("doi", "citation"):
        if key in meta and not isinstance(meta.get(key), str):
            errors.append(f"__meta__.{key}: must be a string.")

    allowed = {
        "name",
        "version",
        "description",
        "category",
        "authors",
        "developers",
        "doi",
        "citation",
    }
    if allow_extra_keys:
        allowed.update(allow_extra_keys)
    extra = set(meta.keys()) - allowed
    if extra:
        errors.append(f"__meta__: unexpected keys {sorted(extra)}.")
    return errors


__all__ = ["validate_meta"]
