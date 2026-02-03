from __future__ import annotations

import dataclasses
from pathlib import Path
import sys
import types

import yaml


def test_hook_preset_falls_back_to_build_options_for_kwargs_only() -> None:
    from brkraw.cli.commands import hook as hook_cmd

    mod = types.ModuleType("brkraw_test_fake_hook")

    @dataclasses.dataclass
    class Options:
        alpha: int = 1
        beta: str = "x"

    def _build_options(kwargs):  # type: ignore[no-untyped-def]
        return Options(alpha=int(kwargs.get("alpha", 1)), beta=str(kwargs.get("beta", "x")))

    mod._build_options = _build_options  # type: ignore[attr-defined]
    sys.modules[mod.__name__] = mod

    def get_dataobj(scan, reco_id=None, **kwargs):  # type: ignore[no-untyped-def]
        return None

    get_dataobj.__module__ = mod.__name__
    preset = hook_cmd._infer_hook_preset({"get_dataobj": get_dataobj})
    assert preset == {"alpha": 1, "beta": "x"}


def test_hook_preset_normalizes_paths_for_yaml() -> None:
    from brkraw.cli.commands import hook as hook_cmd

    payload = {"hooks": {"sordino": {"cache_dir": Path("/tmp/sordino")}}}
    normalized = hook_cmd._normalize_yaml_payload(payload)

    assert normalized["hooks"]["sordino"]["cache_dir"] == "/tmp/sordino"
    text = yaml.safe_dump(normalized, sort_keys=False)
    assert "/tmp/sordino" in text
