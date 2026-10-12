from __future__ import annotations

import argparse
import importlib


def test_render_help_groups_commands_by_category() -> None:
    cli_main = importlib.import_module("brkraw.cli.main")

    parser = argparse.ArgumentParser(
        prog="brkraw",
        description="BrkRaw command-line interface.",
    )
    parser.add_argument("-v", "--version", action="version", version="brkraw v0")
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    info_parser = subparsers.add_parser("info", help="Show scan/study info.")
    info_parser.set_defaults(func=lambda _: 0)

    config_parser = subparsers.add_parser("config", help="Manage config.")
    config_parser.set_defaults(func=lambda _: 0)

    custom_parser = subparsers.add_parser("viewer", help="Open the viewer.")
    custom_parser._brkraw_help_category = "Tools"  # type: ignore[attr-defined]
    custom_parser.set_defaults(func=lambda _: 0)

    text = cli_main._render_help(parser, subparsers)

    assert "Data" in text
    assert "Workspace" in text
    assert "Tools" in text
    assert text.index("Data") < text.index("Workspace") < text.index("Tools")
    assert "info" in text
    assert "config" in text
    assert "viewer" in text


def test_main_help_uses_category_sections(monkeypatch, capsys) -> None:
    cli_main = importlib.import_module("brkraw.cli.main")

    def fake_register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
        info = subparsers.add_parser("info", help="Show scan/study info.")
        info.set_defaults(func=lambda _: 0)

        config = subparsers.add_parser("config", help="Manage config.")
        config.set_defaults(func=lambda _: 0)

        viewer = subparsers.add_parser("viewer", help="Open the viewer.")
        viewer.set_defaults(func=lambda _: 0)

    monkeypatch.setattr(cli_main, "_register_entry_point_commands", fake_register)
    monkeypatch.setattr(cli_main.pvcmd, "query_ps_text", lambda: None)

    rc = cli_main.main(["-h"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "Data" in out
    assert "Workspace" in out
    assert "Extensions" in out
    assert "Sub-commands" not in out
    assert out.index("Data") < out.index("Workspace") < out.index("Extensions")
    assert "info" in out
    assert "config" in out
    assert "viewer" in out
