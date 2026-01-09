from __future__ import annotations

from collections.abc import Mapping
from typing import Any, List

CONVERTER_KEYS = {"get_dataobj", "get_affine", "convert"}


def validate_hook(hook: Any, *, raise_on_error: bool = True) -> List[str]:
    errors: List[str] = []
    if not isinstance(hook, Mapping):
        errors.append("converter_hook: must be a mapping.")
    else:
        for key, value in hook.items():
            if key not in CONVERTER_KEYS:
                errors.append(f"converter_hook: invalid key {key!r}.")
            if not callable(value):
                errors.append(f"converter_hook[{key!r}]: must be callable.")
    if errors and raise_on_error:
        raise ValueError("Invalid converter hook:\n" + "\n".join(errors))
    return errors

