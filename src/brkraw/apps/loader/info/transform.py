from __future__ import annotations

from typing import Union, Optional, Tuple, List, Any, cast
from datetime import datetime, timezone, timedelta
import re

def strip_jcamp_string(value: Optional[str]) -> str:
    if value is None:
        return "Unknown"
    text = str(value).strip()
    if text.startswith("<") and text.endswith(">"):
        text = text[1:-1]
    text = re.sub(r"\^+", " ", text)
    return " ".join(text.split())


def unixtime_to_datetime(value: Union[int, float, Tuple[Union[int, float], ...]]) -> datetime:
    """Convert unix time value to timezone-aware datetime.

    Accepts:
      - int/float: epoch seconds (local timezone)
      - tuple: (sec,), (sec, ms), or (sec, ms, offset_min)

    If offset_min is missing, local timezone is used.
    """
    local_tz = datetime.now().astimezone().tzinfo

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=local_tz)

    if not isinstance(value, tuple) or not value:
        raise TypeError(f"Unsupported value: {value!r}")

    sec = value[0]
    ms = value[1] if len(value) > 1 else 0
    offset_min = value[2] if len(value) > 2 else None

    tz = timezone(timedelta(minutes=offset_min)) if offset_min is not None else local_tz
    return datetime.fromtimestamp(sec, tz=tz).replace(microsecond=int(ms) * 1000)


def stringtime_to_datetime(value: str) -> Union[datetime, str]:
    """Parse PV time strings into datetime.

    Supported formats:
      - 2026-01-01T12:00:00,873-0500
      - 12:00:00 1 Jan 2026
      - 1 Jan 2026
      - 20260101
    """
    _FORMATS = (
        "%Y-%m-%dT%H:%M:%S,%f%z",
        "%H:%M:%S %d %b %Y",
        "%d %b %Y",
        "%Y%m%d",
    )
    
    value = value.strip()
    if len(value) == 0:
        return "Unknown"
    for fmt in _FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported time format: {value!r}")


def merge_entry_and_position(entry: str, position: str):
    entry = entry.split('_')[-1].replace("First", "")
    position = position.split('_')[-1]
    return f'{entry}_{position}'


def convert_to_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return cast(Any, value).tolist()
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]
    

__all__ = [
    'strip_jcamp_string',
    'unixtime_to_datetime',
    'stringtime_to_datetime',
    'merge_entry_and_position',
    'convert_to_list'
]
