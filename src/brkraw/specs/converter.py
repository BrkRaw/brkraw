from __future__ import annotations

"""Backward-compatible alias for converter hooks.

Prefer `brkraw.specs.hook`.
"""

import warnings

from .hook.logic import DEFAULT_GROUP, resolve_hook
from .hook.validator import CONVERTER_KEYS, validate_hook

warnings.warn(
    "brkraw.specs.converter is deprecated; use brkraw.specs.hook instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "CONVERTER_KEYS",
    "DEFAULT_GROUP",
    "resolve_hook",
    "validate_hook",
]

