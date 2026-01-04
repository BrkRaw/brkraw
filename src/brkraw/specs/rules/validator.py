from __future__ import annotations

from pathlib import Path
from typing import Any, List, Dict, Optional
from importlib import resources

try:
    resources.files  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - fallback for Python 3.8
    import importlib_resources as resources  # type: ignore[assignment]

import yaml

from ...core.entrypoints import list_entry_points

CONVERTER_GROUP = "brkraw.converter_hook"

def _load_schema() -> Dict[str, Any]:
    if __package__ is None:
        raise RuntimeError("Package context required to load rules schema.")
    with resources.files("brkraw.schema").joinpath("rules.yaml").open(
        "r", encoding="utf-8"
    ) as handle:
        return yaml.safe_load(handle)


def validate_rules(
    rule_data: Dict[str, Any],
    schema_path: Optional[Path] = None,
) -> None:
    """Validate rule mappings against schema and hook availability.

    Args:
        rule_data: Parsed rule mapping to validate.
        schema_path: Optional rules schema path override.
    """
    try:
        import jsonschema
    except ImportError as exc:
        raise RuntimeError("jsonschema is required to validate rule files.") from exc
    schema = (
        _load_schema()
        if schema_path is None
        else yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    )
    jsonschema.Draft202012Validator(schema).validate(rule_data)
    _validate_default_rules(rule_data)
    _validate_converter_hooks(rule_data)


def _validate_default_rules(rule_data: Dict[str, Any]) -> None:
    """Ensure default rules (no 'when') appear first and avoid 'if'."""
    for category, items in rule_data.items():
        if not isinstance(items, list):
            continue
        default_indexes = []
        for idx, rule in enumerate(items):
            if not isinstance(rule, dict):
                continue
            has_when = "when" in rule
            has_if = "if" in rule
            if has_when and not has_if:
                name = rule.get("name", "<unnamed>")
                raise ValueError(
                    f"Rule {name!r} in {category!r} must define 'if' when 'when' is present."
                )
            if not has_when:
                if has_if:
                    name = rule.get("name", "<unnamed>")
                    raise ValueError(
                        f"Rule {name!r} in {category!r} cannot use 'if' without 'when'."
                    )
                default_indexes.append(idx)
        if not default_indexes:
            continue
        if len(default_indexes) > 1 or default_indexes[0] != 0:
            raise ValueError(
                f"Default rule (no 'when') must be the first entry in {category!r}."
            )


def _validate_converter_hooks(rule_data: Dict[str, Any]) -> None:
    """Ensure converter_hook references resolve to installed hooks."""
    missing: List[str] = []
    items = rule_data.get("converter_hook", [])
    if not items:
        return
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        use = item.get("use")
        if not isinstance(use, str):
            continue
        if not list_entry_points(CONVERTER_GROUP, use):
            missing.append(use)
    if missing:
        missing_text = ", ".join(sorted(set(missing)))
        raise ValueError(
            "converter_hook references missing hooks: "
            f"{missing_text} (group={CONVERTER_GROUP})"
        )
