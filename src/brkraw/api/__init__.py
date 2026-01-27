"""Public API surface for BrkRaw.

This module intentionally re-exports a curated set of symbols for external use.
To keep import-time fast and reduce side effects, most symbols are lazily
imported on first access (PEP 562: module `__getattr__`).
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any, Dict, Tuple

# Public API -----------------------------------------------------------------

__all__ = [
    "formatter",
    "BrukerLoader",
    "loader",
    "hook",
    "hook_manager",
    "hook_resolver",
    "pruner",
    "rules",
    "addon",
    "addon_manager",
    "validate_meta",
    "transform",
    "info_resolver",
    "affine_resolver",
    "shape_resolver",
    "image_resolver",
    "fid_resolver",
    "nifti_resolver",
    "types",
    "config",
]

# Lazy import map: name -> (module_path, attribute_name or None)
# If attribute_name is None, the module itself is returned.
_LAZY: Dict[str, Tuple[str, str | None]] = {
    # core
    "formatter": ("brkraw.core", "formatter"),

    # apps
    "BrukerLoader": ("brkraw.apps.loader", "BrukerLoader"),
    "loader": ("brkraw.apps", "loader"),
    "hook_manager": ("brkraw.apps", "hook"),
    "addon_manager": ("brkraw.apps", "addon"),
    "hook_resolver": ("brkraw.apps.loader.helper", "resolve_converter_hook"),
    "config": ("brkraw.core", "config"),

    # apps.loader.info resolvers
    "info_resolver": ("brkraw.apps.loader", "info"),
    "transform": ("brkraw.apps.loader.info", "transform"),

    # resolvers
    "affine_resolver": ("brkraw.resolver", "affine"),
    "shape_resolver": ("brkraw.resolver", "shape"),
    "image_resolver": ("brkraw.resolver", "image"),
    "fid_resolver": ("brkraw.resolver", "fid"),
    "nifti_resolver": ("brkraw.resolver", "nifti"),

    # specs
    "hook": ("brkraw.specs", "hook"),
    "pruner": ("brkraw.specs", "pruner"),
    "rules": ("brkraw.specs", "rules"),
    "addon": ("brkraw.specs", "remapper"),

    # meta
    "validate_meta": ("brkraw.specs.meta", "validate_meta"),

    # local
    "types": ("brkraw.api", "types"),
}


def __getattr__(name: str) -> Any:
    """Lazily import and return public symbols.

    This keeps import-time minimal while preserving the convenient
    `brkraw.api.<symbol>` access pattern.
    """

    try:
        mod_path, attr = _LAZY[name]
    except KeyError as e:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from e

    mod = import_module(mod_path)
    obj = mod if attr is None else getattr(mod, attr)

    # Cache the resolved object on the module for fast subsequent access.
    globals()[name] = obj
    return obj


def __dir__() -> list[str]:
    # Expose the curated public surface in interactive environments.
    return sorted(set(__all__))


# Type-checking / IDE support -------------------------------------------------
# Importing these only for type-checking keeps runtime imports lazy.
if TYPE_CHECKING:
    from brkraw.core import formatter as formatter
    from brkraw.core import config as config
    from brkraw.apps.loader import BrukerLoader as BrukerLoader
    from brkraw.apps.loader import info as info_resolver
    from brkraw.apps.loader.info import transform as transform
    from brkraw.apps.loader.helper import resolve_converter_hook as hook_resolver
    from brkraw.apps import addon as addon_manager, hook as hook_manager, loader as loader
    from brkraw.resolver import (
        affine as affine_resolver,
        fid as fid_resolver,
        image as image_resolver,
        nifti as nifti_resolver,
        shape as shape_resolver,
    )
    from brkraw.specs import hook as hook, pruner as pruner, rules as rules
    from brkraw.specs import remapper as addon
    from brkraw.specs.meta import validate_meta as validate_meta
    from brkraw.api import types as types