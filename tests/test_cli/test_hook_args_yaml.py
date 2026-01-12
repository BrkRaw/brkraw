from __future__ import annotations

from pathlib import Path

import pytest


def test_load_hook_args_yaml_accepts_hooks_key(tmp_path: Path) -> None:
    from brkraw.cli.hook_args import load_hook_args_yaml

    path = tmp_path / "hook_args.yaml"
    path.write_text(
        "\n".join(
            [
                "hooks:",
                "  mrs:",
                "    reference: water",
                "    peak_ppm: 3.02",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    loaded = load_hook_args_yaml([str(path)])
    assert loaded == {"mrs": {"reference": "water", "peak_ppm": 3.02}}


def test_load_hook_args_yaml_accepts_flat_mapping(tmp_path: Path) -> None:
    from brkraw.cli.hook_args import load_hook_args_yaml

    path = tmp_path / "hook_args.yaml"
    path.write_text("mrs:\n  reference: water\n", encoding="utf-8")
    loaded = load_hook_args_yaml([str(path)])
    assert loaded == {"mrs": {"reference": "water"}}


def test_load_hook_args_yaml_merges_multiple_sources(tmp_path: Path) -> None:
    from brkraw.cli.hook_args import load_hook_args_yaml

    p1 = tmp_path / "a.yaml"
    p2 = tmp_path / "b.yaml"
    p1.write_text("hooks:\n  mrs:\n    reference: water\n", encoding="utf-8")
    p2.write_text("hooks:\n  mrs:\n    peak_ppm: 3.02\n", encoding="utf-8")
    loaded = load_hook_args_yaml([str(p1), str(p2)])
    assert loaded == {"mrs": {"reference": "water", "peak_ppm": 3.02}}


def test_load_hook_args_yaml_rejects_non_mapping(tmp_path: Path) -> None:
    from brkraw.cli.hook_args import load_hook_args_yaml

    path = tmp_path / "hook_args.yaml"
    path.write_text("- not-a-mapping\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_hook_args_yaml([str(path)])


def test_filter_hook_kwargs_drops_unknown() -> None:
    from brkraw.apps.loader import helper as helper_mod

    def hook(*, reference: str = "water") -> None:
        return None

    filtered = helper_mod._filter_hook_kwargs(hook, {"reference": "met", "unknown": 1})
    assert filtered == {"reference": "met"}


def test_filter_hook_kwargs_allows_varkw() -> None:
    from brkraw.apps.loader import helper as helper_mod

    def hook(**kwargs):  # type: ignore[no-untyped-def]
        return kwargs

    filtered = helper_mod._filter_hook_kwargs(hook, {"a": 1, "b": 2})
    assert filtered == {"a": 1, "b": 2}
