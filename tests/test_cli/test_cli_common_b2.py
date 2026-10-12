"""CLI common changes (b1 bundle B2): ParaVision chooser, common --root,
convert --batch, init only, prune option names, old names removed."""
from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest
import yaml

from brkraw.cli import main as cli_main_module
from brkraw.cli import pvcmd
from brkraw.cli.main import HELP_CATEGORY_BY_COMMAND, HELP_COMMAND_ORDER, build_parser, main
from brkraw.cli.utils import add_root_argument

from tests.helpers import SYNTH_MARKERS, make_synthetic_study

CORE_COMMANDS = ["info", "params", "convert", "prune", "init", "config", "cache", "session", "addon", "hook"]


def _ps_line(study: Path, scan: int, reco: int) -> str:
    return f"ps;REQUEST_ATTR;{study}/{scan}/pdata/{reco}"


@pytest.fixture
def no_pvcmd_query(monkeypatch):
    def fail():
        raise AssertionError("pvcmd must not be queried here")

    monkeypatch.setattr(pvcmd, "query_ps_text", fail)


def _fake_ps(monkeypatch, text, *, interactive=False, answers=()):
    monkeypatch.setattr(pvcmd, "query_ps_text", lambda: text)
    monkeypatch.setattr(pvcmd, "is_interactive", lambda: interactive)
    queue = list(answers)
    monkeypatch.setattr(pvcmd, "_ask", lambda prompt: queue.pop(0) if queue else "")


# ---------------------------------------------------------------------------
# ParaVision chooser (BRK-0030 ①, BRK-0031 ③)
# ---------------------------------------------------------------------------


def test_help_never_queries_paravision(no_pvcmd_query):
    assert main(["-h"]) == 0
    with pytest.raises(SystemExit):
        main(["info", "-h"])
    with pytest.raises(SystemExit):
        main(["--version"])


def test_commands_without_a_path_never_query(no_pvcmd_query, capsys):
    assert main(["config", "path", "root"]) == 0


def test_given_path_or_session_path_is_not_replaced(no_pvcmd_query, monkeypatch, tmp_path):
    study = make_synthetic_study(tmp_path / "study")
    assert main(["info", str(study), "--scope", "study"]) == 0
    monkeypatch.setenv("BRKRAW_PATH", str(study))
    assert main(["info", "--scope", "study"]) == 0
    assert os.environ["BRKRAW_PATH"] == str(study)


def test_no_paravision_or_no_entry_continues(monkeypatch):
    _fake_ps(monkeypatch, None)
    assert main(["info"]) == 2  # path needed; no SystemExit from pvcmd
    _fake_ps(monkeypatch, "")
    assert main(["info"]) == 2
    assert "BRKRAW_PATH" not in os.environ


def test_one_entry_is_used(monkeypatch, tmp_path, capsys):
    study = make_synthetic_study(tmp_path / "study")
    _fake_ps(monkeypatch, _ps_line(study, 3, 1))
    assert main(["info", "--scope", "study"]) == 0
    assert os.environ["BRKRAW_PATH"] == str(study)
    assert os.environ["BRKRAW_SCAN_ID"] == "3"
    assert "Using the study open in ParaVision" in capsys.readouterr().err


def test_many_entries_without_terminal_warn_and_pick_nothing(monkeypatch, tmp_path, capsys):
    a = make_synthetic_study(tmp_path / "a")
    b = make_synthetic_study(tmp_path / "b")
    _fake_ps(monkeypatch, _ps_line(a, 1, 1) + "\n" + _ps_line(b, 3, 1), interactive=False)
    assert main(["info"]) == 2
    assert "BRKRAW_PATH" not in os.environ
    assert '2 ParaVision datasets are open; pass a path or use "brkraw session".' in capsys.readouterr().err


def test_many_entries_in_terminal_let_the_user_choose(monkeypatch, tmp_path):
    a = make_synthetic_study(tmp_path / "a")
    b = make_synthetic_study(tmp_path / "b")
    _fake_ps(monkeypatch, _ps_line(a, 1, 1) + "\n" + _ps_line(b, 3, 1), interactive=True, answers=["2"])
    assert main(["info", "--scope", "study"]) == 0
    assert os.environ["BRKRAW_PATH"] == str(b)


def test_existing_scan_and_reco_defaults_are_kept(monkeypatch, tmp_path):
    study = make_synthetic_study(tmp_path / "study")
    monkeypatch.setenv("BRKRAW_SCAN_ID", "1")
    _fake_ps(monkeypatch, _ps_line(study, 3, 2))
    assert main(["info", "--scope", "study"]) == 0
    assert os.environ["BRKRAW_SCAN_ID"] == "1"
    assert os.environ["BRKRAW_RECO_ID"] == "2"


def test_convert_batch_never_queries(no_pvcmd_query):
    assert main(["convert", "--batch"]) == 2


def test_query_failure_is_silent(monkeypatch):
    monkeypatch.setattr(pvcmd.shutil, "which", lambda name: None)
    assert pvcmd.query_ps_text() is None


# ---------------------------------------------------------------------------
# Common --root (BRK-0031, BRK-0032)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", CORE_COMMANDS)
def test_every_core_command_accepts_root(command, tmp_path):
    parser, _ = build_parser()
    extra = {"config": ["show"], "cache": ["info"], "session": ["env"], "addon": ["list"], "hook": ["list"],
             "prune": ["study", "--spec", "s.yaml"]}
    args = parser.parse_args([command, "--root", str(tmp_path)] + extra.get(command, []))
    assert args.root == str(tmp_path)


def test_root_wins_over_environment_for_the_whole_run(monkeypatch, tmp_path):
    from brkraw.cli.commands import info as info_cmd

    seen = {}

    def spy(args):
        seen["home"] = os.environ.get("BRKRAW_CONFIG_HOME")
        return 0

    monkeypatch.setattr(info_cmd, "cmd_info", spy)
    monkeypatch.setenv("BRKRAW_CONFIG_HOME", str(tmp_path / "from-env"))
    assert main(["info", "somewhere", "--root", str(tmp_path / "from-root")]) == 0
    assert seen["home"] == str(tmp_path / "from-root")


def test_config_path_follows_root(tmp_path, capsys):
    assert main(["config", "--root", str(tmp_path / "r"), "path", "root"]) == 0
    assert capsys.readouterr().out.strip() == str(tmp_path / "r")


def test_prune_finds_installed_spec_under_root(tmp_path):
    root = tmp_path / "r"
    (root / "pruner_specs").mkdir(parents=True)
    spec = {"__meta__": {"name": "mine", "version": "1.0.0", "description": "t", "category": "pruner_spec"},
            "files": ["subject", "acqp", "method", "visu_pars", "reco", "2dseq"]}
    (root / "pruner_specs" / "mine.yaml").write_text(yaml.safe_dump(spec), encoding="utf-8")
    study = make_synthetic_study(tmp_path / "study")
    out = tmp_path / "o.zip"
    assert main(["prune", str(study), "--root", str(root), "--spec", "mine", "-o", str(out)]) == 0
    assert zipfile.is_zipfile(out)


def test_session_set_with_root_exports_config_home(tmp_path, capsys):
    study = make_synthetic_study(tmp_path / "study")
    assert main(["session", "--root", str(tmp_path / "r"), "set", "-p", str(study)]) == 0
    out = capsys.readouterr().out
    assert f'export BRKRAW_CONFIG_HOME="{tmp_path / "r"}"' in out


def test_add_root_argument_helper_for_plugins():
    import argparse

    parser = argparse.ArgumentParser()
    add_root_argument(parser)
    assert parser.parse_args(["--root", "x"]).root == "x"
    assert parser.parse_args([]).root is None


# ---------------------------------------------------------------------------
# convert --batch (BRK-0026), old command removed
# ---------------------------------------------------------------------------


def test_convert_batch_command_is_gone():
    with pytest.raises(SystemExit):
        main(["convert-batch", "x"])
    assert "convert-batch" not in HELP_COMMAND_ORDER
    assert "convert-batch" not in HELP_CATEGORY_BY_COMMAND


def test_help_lists_no_old_command(capsys):
    assert main(["-h"]) == 0
    assert "convert-batch" not in capsys.readouterr().out


def test_convert_batch_converts_each_dataset(monkeypatch, tmp_path):
    from brkraw.cli.commands import convert as convert_cmd

    folder = tmp_path / "studies"
    make_synthetic_study(folder / "a")
    make_synthetic_study(folder / "b")
    calls = []
    monkeypatch.setattr(convert_cmd, "_convert_one", lambda args: calls.append(Path(args.path).name) or 0)
    assert main(["convert", str(folder), "--batch", "-o", str(tmp_path / "out")]) == 0
    assert sorted(calls) == ["a", "b"]


@pytest.mark.parametrize("extra", [["-s", "3"], ["-r", "1"], ["-M", "map.yaml"]])
def test_convert_batch_refuses_single_dataset_options(extra, monkeypatch, tmp_path):
    from brkraw.cli.commands import convert as convert_cmd

    folder = tmp_path / "studies"
    make_synthetic_study(folder / "a")
    monkeypatch.setattr(convert_cmd, "_convert_one", lambda args: pytest.fail("must not convert"))
    assert main(["convert", str(folder), "--batch"] + extra) == 2


def test_convert_single_dataset_still_goes_through_convert_one(monkeypatch, tmp_path):
    from brkraw.cli.commands import convert as convert_cmd

    study = make_synthetic_study(tmp_path / "study")
    seen = []
    monkeypatch.setattr(convert_cmd, "_convert_one", lambda args: seen.append(args.path) or 0)
    assert main(["convert", str(study), "-s", "3"]) == 0
    assert seen == [str(study)]


# ---------------------------------------------------------------------------
# init only (BRK-0028)
# ---------------------------------------------------------------------------


def test_config_init_is_gone(tmp_path):
    with pytest.raises(SystemExit):
        main(["config", "--root", str(tmp_path), "init"])


def test_brkraw_init_creates_the_config(tmp_path):
    root = tmp_path / "r"
    assert main(["init", "--root", str(root), "--yes"]) == 0
    assert (root / "config.yaml").is_file()


# ---------------------------------------------------------------------------
# prune option names (BRK-0028)
# ---------------------------------------------------------------------------


def _prune_spec(tmp_path: Path) -> Path:
    spec = {"__meta__": {"name": "t", "version": "1.0.0", "description": "t", "category": "pruner_spec"},
            "files": ["subject", "acqp", "method", "visu_pars", "reco", "2dseq"]}
    path = tmp_path / "spec.yaml"
    path.write_text(yaml.safe_dump(spec), encoding="utf-8")
    return path


def test_prune_scan_and_reco_short_options(tmp_path):
    study = make_synthetic_study(tmp_path / SYNTH_MARKERS["folder"], scans={1: "FLASH", 3: "RARE"})
    out = tmp_path / "o.zip"
    assert main(["prune", str(study), "--spec", str(_prune_spec(tmp_path)), "-o", str(out), "-s", "3", "-r", "1"]) == 0
    with zipfile.ZipFile(out) as zf:
        names = {n.split("/", 1)[1] for n in zf.namelist() if not n.endswith("/")}
    assert "subject" in names and "3/pdata/1/2dseq" in names
    assert not any(n.startswith("1/") for n in names)


@pytest.mark.parametrize("old", [["--scan-ids", "3"], ["--reco-ids", "1"], ["--spec-name", "t"]])
def test_prune_old_option_names_are_gone(old, tmp_path):
    study = make_synthetic_study(tmp_path / "study")
    with pytest.raises(SystemExit):
        main(["prune", str(study), "--spec", str(_prune_spec(tmp_path)), "-o", str(tmp_path / "o.zip")] + old)
