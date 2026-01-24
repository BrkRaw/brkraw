"""
Utilities to resolve NumPy dtype and scaling parameters for Paravision scans/recos.

Given a `Scan` or `Reco` object, `resolve()` inspects the relevant parameter
objects (`acqp` for Scan, `visu_pars` for Reco) and returns a dict containing:
    - dtype: NumPy dtype built from byte order and word type
    - slope: VisuCoreDataSlope
    - offset: VisuCoreDataOffs
"""
from __future__ import annotations
from typing import Union, Optional, TypedDict, cast
import numpy as np
from .helpers import get_file
from ..dataclasses import Scan, Reco, LazyScan


WORDTYPE = {
    "_32BIT_SGN_INT": "i",
    "_16BIT_SGN_INT": "h",
    "_8BIT_UNSGN_INT": "B",
    "_32BIT_FLOAT": "f",
}

BYTEORDER = {
    "littleEndian": "<",
    "bigEndian": ">",
}


class ResolvedDatatype(TypedDict):
    dtype: np.dtype
    slope: Optional[float]
    offset: Optional[float]



def _get_dtype(byte_order: str, word_type: str) -> np.dtype:
    if byte_order not in BYTEORDER:
        raise ValueError(f"Unsupported byte order: {byte_order!r}")
    if word_type not in WORDTYPE:
        raise ValueError(f"Unsupported word type: {word_type!r}")
    return np.dtype(f"{BYTEORDER[byte_order]}{WORDTYPE[word_type]}")


def resolve(obj: Union["LazyScan", "Scan", "Reco"]) -> Optional[ResolvedDatatype]:
    """Return dtype/slope/offset metadata for a Scan or Reco."""
    # Accept LazyScan-like proxies by materializing them.
    if not isinstance(obj, (Scan, Reco)) and hasattr(obj, "materialize"):
        try:
            obj = obj.materialize()
        except Exception as e:
            raise TypeError(
                f"resolve() failed to materialize proxy object {type(obj)!r}: {e}"
            ) from e
    if isinstance(obj, Scan):
        try:
            p = get_file(obj, 'acqp')
        except FileNotFoundError:
            return None
        byte_order = f'{p.get("BYTORDA")}Endian'
        word_type = f'_{"".join(p["ACQ_word_size"].split("_"))}_SGN_INT'
    elif isinstance(obj, Reco):
        try:
            p = get_file(obj, 'visu_pars')
        except FileNotFoundError:
            return None
        byte_order = p.get('VisuCoreByteOrder')
        word_type = p.get('VisuCoreWordType')
    else:
        raise TypeError(f"resolve() expects Scan or Reco, got {type(obj)!r}")
    result: ResolvedDatatype = {
        "dtype": _get_dtype(byte_order, word_type),
        "slope": cast(Optional[float], p.get('VisuCoreDataSlope')),
        "offset": cast(Optional[float], p.get('VisuCoreDataOffs')),
    }

    return result
