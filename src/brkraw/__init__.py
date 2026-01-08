from __future__ import annotations

__version__ = '0.5.0rc1'
from .apps.loader import BrukerLoader


def load(path):
    return BrukerLoader(path)

__all__ = [
    'load',
    'BrukerLoader',
    '__version__',
]
