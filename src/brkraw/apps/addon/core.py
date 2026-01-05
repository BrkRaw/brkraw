"""Addon installer utilities for specs and rules.

Last updated: 2025-12-30
"""

from __future__ import annotations

from typing import List

from .dependencies import resolve_pruner_spec_reference, resolve_spec_reference
from .installation import (
    add,
    add_pruner_spec_data,
    add_rule_data,
    add_spec_data,
    install_defaults,
    list_installed,
    remove,
)

__all__ = [
    "add",
    "add_rule_data",
    "add_spec_data",
    "add_pruner_spec_data",
    "install_defaults",
    "resolve_spec_reference",
    "resolve_pruner_spec_reference",
    "list_installed",
    "remove",
]


def __dir__() -> List[str]:
    return sorted(__all__)
