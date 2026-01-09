from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable, Dict, Union

from ...core.entrypoints import list_entry_points
from .validator import validate_hook

DEFAULT_GROUP = "brkraw.converter_hook"


def resolve_hook(
    hook: Union[Mapping[str, Callable[..., Any]], str],
    *,
    group: str = DEFAULT_GROUP,
) -> Dict[str, Callable[..., Any]]:
    if isinstance(hook, str):
        matches = list_entry_points(group, hook)
        if not matches:
            raise LookupError(
                f"Converter hook not found: {hook!r} (group={group!r})"
            )
        entry = matches[0].load()
        validate_hook(entry)
        return dict(entry)
    validate_hook(hook)
    return dict(hook)


__all__ = ["DEFAULT_GROUP", "resolve_hook"]

