from __future__ import annotations

from pathlib import Path
from typing import Any, IO, List, Dict, Union, Optional
from importlib import resources

try:
    resources.files  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - fallback for Python 3.8
    import importlib_resources as resources  # type: ignore[assignment]

import yaml

from ..meta import validate_meta

_ALLOWED_FILES = {"method", "acqp", "visu_pars", "reco", "subject"}
_RULE_KEYS = {"sources", "inputs", "const", "ref", "transform", "default"}
_INPUT_KEYS = {"sources", "const", "ref", "transform", "default", "required"}
_INLINE_SOURCE_KEYS = {"inputs", "transform"}
_META_KEY = "__meta__"


def _validate_transforms_source(
    transforms_source: Optional[Union[str, Path, List[str], List[Path], IO[str], IO[bytes]]],
    errors: List[str],
) -> None:
    if transforms_source is None:
        return
    if isinstance(transforms_source, (str, Path)):
        src_path = Path(transforms_source)
        if not src_path.exists():
            errors.append(f"transforms_source: not found: {src_path}")
        return
    if isinstance(transforms_source, list):
        for item in transforms_source:
            if not isinstance(item, (str, Path)):
                errors.append("transforms_source: list entries must be paths.")
                continue
            src_path = Path(item)
            if not src_path.exists():
                errors.append(f"transforms_source: not found: {src_path}")


def _load_schema() -> Dict[str, Any]:
    if __package__ is None:
        raise RuntimeError("Package context required to load remapper schema.")
    with resources.files("brkraw.schema").joinpath("remapper.yaml").open(
        "r", encoding="utf-8"
    ) as handle:
        return yaml.safe_load(handle)


def _validate_sources(sources: Any, path: str, errors: List[str]) -> None:
    if not isinstance(sources, list):
        errors.append(f"{path}: sources must be a list.")
        return
    for idx, src in enumerate(sources):
        item_path = f"{path}.sources[{idx}]"
        if not isinstance(src, dict):
            errors.append(f"{item_path}: source must be an object.")
            continue
        if "inputs" in src:
            extra = set(src.keys()) - _INLINE_SOURCE_KEYS
            if extra:
                errors.append(f"{item_path}: unexpected keys {sorted(extra)}.")
            _validate_inputs(src["inputs"], item_path, errors)
            if "transform" in src:
                t = src["transform"]
                if isinstance(t, list):
                    if not all(isinstance(name, str) for name in t):
                        errors.append(f"{item_path}: transform list must be strings.")
                elif not isinstance(t, str):
                    errors.append(f"{item_path}: transform must be a string or list.")
            continue
        extra = set(src.keys()) - {"file", "key", "reco_id"}
        if extra:
            errors.append(f"{item_path}: unexpected keys {sorted(extra)}.")
        if "file" not in src or "key" not in src:
            errors.append(f"{item_path}: requires file and key.")
            continue
        if src["file"] not in _ALLOWED_FILES:
            errors.append(f"{item_path}: invalid file {src['file']!r}.")
        if not isinstance(src["key"], str):
            errors.append(f"{item_path}: key must be a string.")
        reco_id = src.get("reco_id")
        if reco_id is not None and (not isinstance(reco_id, int) or reco_id < 1):
            errors.append(f"{item_path}: reco_id must be int >= 1.")


def _validate_inputs(inputs: Any, path: str, errors: List[str]) -> None:
    if not isinstance(inputs, dict):
        errors.append(f"{path}: inputs must be a mapping.")
        return
    for name, spec in inputs.items():
        item_path = f"{path}.inputs[{name!r}]"
        if isinstance(spec, str):
            if not spec.startswith("$"):
                errors.append(f"{item_path}: input shorthand must start with '$'.")
            continue
        if not isinstance(spec, dict):
            errors.append(f"{item_path}: input spec must be an object.")
            continue
        extra = set(spec.keys()) - _INPUT_KEYS
        if extra:
            errors.append(f"{item_path}: unexpected keys {sorted(extra)}.")
        if not any(k in spec for k in ("sources", "const", "ref")):
            errors.append(f"{item_path}: requires sources, const, or ref.")
        if "sources" in spec:
            _validate_sources(spec["sources"], item_path, errors)
        if "ref" in spec and not isinstance(spec["ref"], str):
            errors.append(f"{item_path}: ref must be a string.")
        if "transform" in spec:
            t = spec["transform"]
            if isinstance(t, list):
                if not all(isinstance(name, str) for name in t):
                    errors.append(f"{item_path}: transform list must be strings.")
            elif not isinstance(t, str):
                errors.append(f"{item_path}: transform must be a string or list.")
        if "required" in spec and not isinstance(spec["required"], bool):
            errors.append(f"{item_path}: required must be a boolean.")


def _validate_spec_minimal(spec: Any) -> List[str]:
    errors: List[str] = []
    if not isinstance(spec, dict):
        errors.append("spec: must be a mapping.")
        return errors
    if _META_KEY not in spec:
        errors.append("spec.__meta__: is required.")
    else:
        errors.extend(
            validate_meta(
                spec.get(_META_KEY),
                allow_extra_keys={"include", "include_mode", "transforms_source", "__spec_path__"},
                raise_on_error=False,
            )
        )
    for key, rule in spec.items():
        if key == _META_KEY:
            continue
        path = f"spec[{key!r}]"
        if not isinstance(rule, dict):
            errors.append(f"{path}: rule must be an object.")
            continue
        extra = set(rule.keys()) - _RULE_KEYS
        if extra:
            errors.append(f"{path}: unexpected keys {sorted(extra)}.")
        if not any(k in rule for k in ("sources", "inputs", "const", "ref")):
            errors.append(f"{path}: requires sources, inputs, const, or ref.")
        if "sources" in rule:
            _validate_sources(rule["sources"], path, errors)
        if "inputs" in rule:
            _validate_inputs(rule["inputs"], path, errors)
        if "ref" in rule and not isinstance(rule["ref"], str):
            errors.append(f"{path}: ref must be a string.")
        if "transform" in rule:
            t = rule["transform"]
            if isinstance(t, list):
                if not all(isinstance(name, str) for name in t):
                    errors.append(f"{path}: transform list must be strings.")
            elif not isinstance(t, str):
                errors.append(f"{path}: transform must be a string or list.")
    return errors


def validate_spec(
    spec: Any,
    *,
    transforms_source: Optional[Union[str, Path, List[str], List[Path], IO[str], IO[bytes]]] = None,
    raise_on_error: bool = True,
) -> List[str]:
    """Validate a remapper spec against the schema.

    Args:
        spec: Parsed spec mapping to validate.
        raise_on_error: If True, raise ValueError on validation errors.

    Returns:
        List of validation error messages (empty when valid).
    """
    errors: List[str] = []
    try:
        import jsonschema
    except Exception:
        errors = _validate_spec_minimal(spec)
    else:
        schema = _load_schema()
        validator = jsonschema.Draft202012Validator(schema)
        for err in validator.iter_errors(spec):
            path = ".".join(str(p) for p in err.path)
            prefix = f"spec.{path}" if path else "spec"
            errors.append(f"{prefix}: {err.message}")

    meta = spec.get(_META_KEY) if isinstance(spec, dict) else None
    errors.extend(
        validate_meta(
            meta,
            allow_extra_keys={"include", "include_mode", "transforms_source", "__spec_path__"},
            raise_on_error=False,
        )
    )
    _validate_transforms_source(transforms_source, errors)
    if errors and raise_on_error:
        raise ValueError("Invalid remapper spec:\n" + "\n".join(errors))
    return errors


