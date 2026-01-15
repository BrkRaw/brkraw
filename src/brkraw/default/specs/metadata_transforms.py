from __future__ import annotations

from typing import Optional
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


def to_seconds(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple, np.ndarray)):
        arr = np.asarray(value, dtype=float)
        return (arr / 1000.0).tolist()
    return float(value) / 1000.0


def first_seconds(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple, np.ndarray)):
        arr = np.asarray(value, dtype=float).ravel()
        if arr.size == 0:
            return None
        return float(arr[0]) / 1000.0
    return float(value) / 1000.0


def freq_to_field(value=None, freq=None):
    if freq is None:
        freq = value
    if freq is None:
        return None
    return float(freq) / 42.576


def as_list(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def pixel_spacing_from_extent(extent=None, size=None):
    if extent is None or size is None:
        return None
    arr_extent = np.asarray(extent, dtype=float).ravel()
    arr_size = np.asarray(size, dtype=float).ravel()
    if arr_extent.size == 0 or arr_size.size == 0:
        return None
    if arr_extent.size != arr_size.size:
        count = min(arr_extent.size, arr_size.size)
        if count == 0:
            return None
        arr_extent = arr_extent[:count]
        arr_size = arr_size[:count]
    with np.errstate(divide="ignore", invalid="ignore"):
        spacing = arr_extent / arr_size
    return spacing.tolist()


def normalize_method(value: Optional[str]) -> str:
    return strip_jcamp_string(value).upper()


def pick_value(value=None, **_):
    return value


def volume_timing(tr=None, nr=None):
    if tr is None or nr is None:
        return None
    tr_sec = first_seconds(tr)
    if tr_sec is None:
        return None
    try:
        count = int(np.asarray(nr).ravel()[0])
    except Exception:
        return None
    if count <= 0:
        return None
    return (np.arange(count) * tr_sec).tolist()
