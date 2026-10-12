"""Help wording for 0.6.0rc1 (bundle R2): next steps at the end of
`brkraw -h` (X3), one command table (X4), "Commands" (X5), addon and hook
descriptions; plus the BRK-0040 answer: `-r` without `-s` names the scans it
skips."""
from __future__ import annotations

import importlib
import logging
import shutil
from pathlib import Path

import pytest

from brkraw.cli.main import build_parser, main

cli_main = importlib.import_module("brkraw.cli.main")

from tests.helpers import make_synthetic_study


def _top_help(capsys) -> str:
    assert main(["-h"]) == 0
    return capsys.readouterr().out


def _flat(text: str) -> str:
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# X3: next steps at the end of brkraw -h
# ---------------------------------------------------------------------------


def test_top_help_ends_with_next_steps(capsys):
    out = _top_help(capsys)
    tail = out[out.index("Extensions:"):]
    lines = [line.strip() for line in tail.splitlines()]
    for expected in (
        "brkraw init",
        "brkraw info /path/to/study",
        "brkraw convert /path/to/study -s 3",
        "brkraw prune /path/to/study --dry-run",
    ):
        assert any(line.startswith(expected) for line in lines), expected
    assert "brkraw <command> -h" in tail
    assert "https://brkraw.github.io/" in tail


def test_next_steps_keep_their_lines(capsys):
    # argparse must not reflow the example lines into one paragraph
    out = _top_help(capsys)
    init_line = next(line for line in out.splitlines() if line.strip().startswith("brkraw init"))
    assert "brkraw info" not in init_line


# ---------------------------------------------------------------------------
# X4: one command table
# ---------------------------------------------------------------------------


def test_one_command_table_drives_help_and_choices():
    table = cli_main.CORE_COMMANDS
    names = [name for name, _ in table]
    assert names == ["info", "params", "convert", "prune", "init", "config", "cache", "session", "addon", "hook"]
    assert cli_main.HELP_CATEGORY_BY_COMMAND == dict(table)
    assert cli_main.HELP_COMMAND_ORDER == {name: i for i, name in enumerate(names)}
    _, subparsers = build_parser()
    core_choices = [name for name in subparsers.choices if name in dict(table)]
    assert core_choices == names


def test_plugins_come_after_core_commands(monkeypatch):
    real = cli_main._iter_entry_points

    class FakeEP:
        name = "zzplugin"

        def load(self):
            def register(subparsers):
                p = subparsers.add_parser("zzplugin", help="A plugin.")
                p.set_defaults(func=lambda _: 0)

            return register

    def fake(group, name=None):
        eps = list(real(group)) if name is None else list(real(group, name=name))
        return [FakeEP()] + eps

    monkeypatch.setattr(cli_main, "_iter_entry_points", fake)
    _, subparsers = build_parser()
    choices = list(subparsers.choices)
    core = [name for name, _ in cli_main.CORE_COMMANDS]
    # other installed plugins (for example brkraw-cli's example command) may also follow
    assert choices[:len(core)] == core
    assert choices.index("zzplugin") >= len(core)


# ---------------------------------------------------------------------------
# X5: "Commands", not "Sub-commands"
# ---------------------------------------------------------------------------


def test_commands_title():
    parser, _ = build_parser()
    titles = [group.title for group in parser._action_groups]
    assert "Commands" in titles
    assert "Sub-commands" not in titles


# ---------------------------------------------------------------------------
# command descriptions
# ---------------------------------------------------------------------------


def test_top_help_descriptions(capsys):
    out = _flat(_top_help(capsys))
    assert "Manage info specs and rules." not in out
    assert "pruner spec" in out and "context map" in out  # addon
    assert "Convert a scan/reco to NIfTI." not in out
    assert "several" in out  # convert


def test_addon_subcommand_help(capsys):
    with pytest.raises(SystemExit):
        main(["addon", "-h"])
    out = _flat(capsys.readouterr().out)
    assert "Install a spec or rule file." not in out
    assert "List installed specs and rules." not in out
    assert "context map" in out


def test_hook_install_help_says_pip_first(capsys):
    with pytest.raises(SystemExit):
        main(["hook", "-h"])
    out = _flat(capsys.readouterr().out)
    assert "Install hook addons." not in out
    assert "pip" in out


# ---------------------------------------------------------------------------
# BRK-0040: -r without -s skips scans without that reco and says which
# ---------------------------------------------------------------------------


@pytest.fixture
def study(tmp_path):
    path = make_synthetic_study(tmp_path / "study")
    shutil.copytree(path / "3" / "pdata" / "1", path / "3" / "pdata" / "2")
    return path


def _files(folder: Path):
    return sorted(p.name for p in folder.rglob("*") if p.is_file()) if folder.exists() else []


def test_reco_without_scan_names_the_skipped_scans(study, tmp_path, caplog):
    caplog.set_level(logging.INFO)
    out = tmp_path / "out"
    assert main(["convert", str(study), "-r", "2", "-o", str(out)]) == 0
    names = _files(out)
    assert len(names) == 1 and "scan-3" in names[0]
    skipped = [r for r in caplog.records if r.levelno == logging.WARNING and "skipped" in r.getMessage()]
    assert len(skipped) == 1
    message = skipped[0].getMessage()
    assert "reco 2" in message and "scan 1" in message and "scan 3" not in message
    assert "not available for scan 1" not in caplog.text  # skipped before converting


def test_reco_without_scan_no_warning_when_all_have_it(study, tmp_path, caplog):
    out = tmp_path / "out"
    assert main(["convert", str(study), "-r", "1", "-o", str(out)]) == 0
    assert "skipped" not in caplog.text
    assert len(_files(out)) == 2


def test_reco_missing_everywhere_fails(study, tmp_path, caplog):
    out = tmp_path / "out"
    assert main(["convert", str(study), "-r", "7", "-o", str(out)]) == 2
    assert _files(out) == []
    assert "reco 7" in caplog.text
