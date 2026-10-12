"""Context map v3: dataset-level YAML that defines output values without changing originals."""
from __future__ import annotations

from .logic import (
    CATEGORY,
    MISSING,
    RESERVED,
    UTILS_NAMES,
    ContextMapError,
    ScanPlan,
    apply_context_map,
    evaluate,
    find_context_map,
    load_context_map,
    load_yaml,
    matches_condition,
    matches_when,
    plan_scan,
    resolve_context_map,
    resolve_ref,
    validate_context_map,
)

__all__ = [
    "CATEGORY",
    "ContextMapError",
    "MISSING",
    "RESERVED",
    "ScanPlan",
    "UTILS_NAMES",
    "apply_context_map",
    "evaluate",
    "find_context_map",
    "load_context_map",
    "load_yaml",
    "matches_condition",
    "matches_when",
    "plan_scan",
    "resolve_context_map",
    "resolve_ref",
    "validate_context_map",
]
