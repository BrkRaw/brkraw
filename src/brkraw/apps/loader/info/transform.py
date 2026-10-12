from __future__ import annotations

from typing import Union, Optional, Tuple, List, Any, cast
from datetime import datetime, timezone, timedelta
import logging
import re

logger = logging.getLogger("brkraw.info.transform")

def strip_jcamp_string(value: Optional[str]) -> str:
    if value is None:
        return "Unknown"
    text = str(value).strip()
    if text.startswith("<") and text.endswith(">"):
        text = text[1:-1]
    text = re.sub(r"\^+", " ", text)
    return " ".join(text.split())


def strip_method_prefix(value: Optional[str]) -> Optional[str]:
    """Method name without the vendor prefix: ``Bruker:EPI`` -> ``EPI``, ``User:zte`` -> ``zte``.

    Text without a colon is returned unchanged. ``Method`` keeps the original
    value; this gives the separate ``MethodBase`` item (BRK-0034 1).
    """
    if value is None:
        return None
    text = str(value)
    head, sep, tail = text.partition(":")
    return tail.strip() if sep and tail.strip() else text


def unixtime_to_datetime(
    value: Optional[Union[int, float, Tuple[Union[int, float], ...]]]
) -> Optional[datetime]:
    """Convert unix time value to timezone-aware datetime.

    Accepts:
      - int/float: epoch seconds (local timezone)
      - tuple: (sec,), (sec, ms), or (sec, ms, offset_min)
      - None (the field is missing, for example removed by an anonymizing
        pruner spec): returns None, so study info still loads.

    If offset_min is missing, local timezone is used.
    """
    if value is None:
        return None
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

    An empty value or ``"Unknown"`` (what ``strip_jcamp_string`` gives for a
    missing field) returns ``"Unknown"``. A value in any other format logs a
    warning and is returned as text, so one unreadable date (for example a
    removed or replaced birth date) never stops study info.
    """
    _FORMATS = (
        "%Y-%m-%dT%H:%M:%S,%f%z",
        "%H:%M:%S %d %b %Y",
        "%d %b %Y",
        "%Y%m%d",
    )

    stripped = value.strip()
    if not stripped or stripped == "Unknown":
        return "Unknown"
    for fmt in _FORMATS:
        try:
            return datetime.strptime(stripped, fmt)
        except ValueError:
            continue
    logger.warning("Unsupported time format: %r", stripped)
    return stripped


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
