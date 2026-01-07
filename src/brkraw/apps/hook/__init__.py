"""Hook package utilities for converter hooks."""

from __future__ import annotations

from typing import List

from .core import (
    install_hook,
    install_all,
    list_hooks,
    read_hook_docs,
    uninstall_hook,
)

__all__ = [
    "install_all",
    "install_hook",
    "list_hooks",
    "read_hook_docs",
    "uninstall_hook",
]


def __dir__() -> List[str]:
    return sorted(__all__)
