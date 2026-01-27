"""BrkRaw loader package entrypoint.

Last updated: 2025-12-30
"""
from __future__ import annotations


from .core import BrukerLoader
from .info import (
    study as study_resolver, 
    scan as scan_resolver,
)
__all__ = [
    "BrukerLoader",
    "study_resolver",
    "scan_resolver",
]
