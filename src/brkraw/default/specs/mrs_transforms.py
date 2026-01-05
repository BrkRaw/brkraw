from __future__ import annotations

from typing import Optional, Any, cast
import re

import numpy as np


def strip_jcamp_string(value: Optional[str]) -> str:
    if value is None:
        return "Unknown"
    text = str(value).strip()
    if text.startswith("<") and text.endswith(">"):
        text = text[1:-1]
    text = re.sub(r"\^+", " ", text)
    return " ".join(text.split())


def convert_to_list(value: Any):
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return cast(Any, value).tolist()
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]
