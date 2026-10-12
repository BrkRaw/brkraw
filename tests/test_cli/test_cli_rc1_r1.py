"""CLI behaviour for 0.6.0rc1 (bundle R1): init --yes and the shell file,
params output, one scan-id rule for session variables, session help,
convert with several scans (BRK-0040 1 and 2)."""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

import pytest

from brkraw.cli.main import build_parser, main

from tests.helpers import make_synthetic_study


def _files(folder: Path):
    if not folder.exists():
        return []
    return sorted(p.name for p in folder.rglob("*") if p.is_file())


@pytest.fixture
def study(tmp_path):
    """Scans 1 (FLASH, reco 1) and 3 (RARE, recos 1 and 2)."""
    path = make_synthetic_study(tmp_path / "study")
    shutil.copytree(path / "3" / "pdata" / "1", path / "3" / "pdata" / "2")
    return path


# ---------------------------------------------------------------------------
# init --yes leaves the shell file alone (BRK-0040 1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("extra", [[], ["--install-default"]])
def test_init_yes_does_not_touch_the_shell_file(extra, monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("SHELL", "/bin/zsh")
    home = Path(os.environ["HOME"])
    rc = home / ".zshrc"
    rc.write_text("# mine\n", encoding="utf-8")
    caplog.set_level(logging.INFO)
    assert main(["init", "--root", str(tmp_path / "r"), "--yes", *extra]) == 0
    assert rc.read_text(encoding="utf-8") == "# mine\n"
    assert not (home / ".bashrc").exists()
    assert "--shell-rc" in caplog.text  # tells how to add the helpers


def test_init_yes_with_shell_rc_adds_the_helpers(tmp_path):
    rc = tmp_path / "my_rc"
    assert main(["init", "--root", str(tmp_path / "r"), "--yes", "--shell-rc", str(rc)]) == 0
    text = rc.read_text(encoding="utf-8")
    assert "brkraw-set()" in text and "brkraw-unset()" in text


def test_init_shell_rc_help_no_longer_promises_a_default(capsys):
    with pytest.raises(SystemExit):
        main(["init", "-h"])
    out = " ".join(capsys.readouterr().out.split())
    assert "defaults to ~/.zshrc" not in out
    assert "--shell-rc" in out


# ---------------------------------------------------------------------------
# params prints its result (stdout), not through the log
# ---------------------------------------------------------------------------


def test_params_result_goes_to_stdout_even_with_warning_logging(study, capsys, caplog):
    caplog.set_level(logging.WARNING)
    assert main(["params", str(study), "-k", "PVM_EchoTime", "-s", "3"]) == 0
    out = capsys.readouterr().out
    assert "PVM_EchoTime" in out
    assert "10" in out


def test_params_no_match_prints_none_to_stdout(study, capsys, caplog):
    caplog.set_level(logging.WARNING)
    assert main(["params", str(study), "-k", "ZZNoSuchKey", "-s", "3"]) == 0
    assert "(none)" in capsys.readouterr().out


def test_params_scan_help_text(capsys):
    with pytest.raises(SystemExit):
        main(["params", "-h"])
    out = " ".join(capsys.readouterr().out.split())
    assert "required for study-level search" not in out


# ---------------------------------------------------------------------------
# one scan-id rule for session variables
# ---------------------------------------------------------------------------


def test_parse_scan_ids_is_shared():
    from brkraw.cli.utils import parse_scan_ids

    assert parse_scan_ids(["3", "4,5"]) == [3, 4, 5]
    with pytest.raises(ValueError):
        parse_scan_ids(["x"])


def test_params_refuses_several_session_scan_ids(study, monkeypatch, caplog):
    monkeypatch.setenv("BRKRAW_SCAN_ID", "1,3")
    assert main(["params", str(study), "-k", "PVM_EchoTime"]) == 2
    assert "one scan id" in caplog.text


def test_params_takes_one_session_scan_id(study, monkeypatch, capsys):
    monkeypatch.setenv("BRKRAW_SCAN_ID", " 3 ")
    assert main(["params", str(study), "-k", "PVM_EchoTime"]) == 0
    assert "PVM_EchoTime" in capsys.readouterr().out


def test_info_reads_the_session_list(study, monkeypatch, capsys):
    monkeypatch.setenv("BRKRAW_SCAN_ID", "3, 1")
    assert main(["info", str(study)]) == 0


def test_info_scan_ids_with_commas(study, capsys):
    assert main(["info", str(study), "--scope", "scan", "-s", "3,1"]) == 0
    out = capsys.readouterr().out
    assert "RARE" in out and "FLASH" in out


def test_info_bad_scan_id_text(study):
    assert main(["info", str(study), "-s", "x"]) == 2


def test_convert_reads_every_session_scan_id(study, monkeypatch, tmp_path):
    monkeypatch.setenv("BRKRAW_SCAN_ID", "1,3")
    out = tmp_path / "out"
    assert main(["convert", str(study), "-r", "1", "-o", str(out)]) == 0
    names = _files(out)
    assert any("scan-1" in n for n in names) and any("scan-3" in n for n in names)


def test_convert_session_scan_id_invalid_is_an_error(study, monkeypatch, tmp_path):
    monkeypatch.setenv("BRKRAW_CONVERT_SCAN_ID", "3;4")
    assert main(["convert", str(study), "-o", str(tmp_path / "out")]) == 2


def test_session_help_lists_only_keys_that_are_read(capsys):
    with pytest.raises(SystemExit):
        main(["session", "set", "-h"])
    out = " ".join(capsys.readouterr().out.split())
    assert "FORMAT" not in out
    assert "SPACE" in out


# ---------------------------------------------------------------------------
# convert with several scans (BRK-0040 2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ids", [["1", "3"], ["1,3"], ["1,", "3"]])
def test_convert_several_scans(ids, study, tmp_path):
    out = tmp_path / "out"
    assert main(["convert", str(study), "-s", *ids, "-o", str(out)]) == 0
    names = _files(out)
    assert len(names) == 3  # scan 1 reco 1, scan 3 recos 1 and 2
    assert sum("scan-1" in n for n in names) == 1
    assert sum("scan-3" in n for n in names) == 2


def test_convert_one_scan_unchanged(study, tmp_path):
    out = tmp_path / "out"
    assert main(["convert", str(study), "-s", "1", "-o", str(out) + os.sep]) == 0
    assert len(_files(out)) == 1


def test_convert_several_scans_need_a_folder_output(study, tmp_path, caplog):
    assert main(["convert", str(study), "-s", "1", "3", "-o", str(tmp_path / "x.nii.gz")]) == 2
    assert not (tmp_path / "x.nii.gz").exists()
    assert "folder" in caplog.text or "directory" in caplog.text


def test_convert_several_scans_with_reco_all_present(study, tmp_path):
    out = tmp_path / "out"
    assert main(["convert", str(study), "-s", "1", "3", "-r", "1", "-o", str(out)]) == 0
    assert len(_files(out)) == 2


def test_convert_reco_missing_in_one_scan_writes_nothing(study, tmp_path, caplog):
    out = tmp_path / "out"
    assert main(["convert", str(study), "-s", "3", "1", "-r", "2", "-o", str(out)]) == 2
    assert _files(out) == []
    assert "scan 1" in caplog.text and "reco 2" in caplog.text


def test_convert_unknown_scan_is_an_error_not_a_crash(study, tmp_path, caplog):
    out = tmp_path / "out"
    assert main(["convert", str(study), "-s", "1", "99", "-o", str(out)]) == 2
    assert _files(out) == []
    assert "99" in caplog.text


@pytest.mark.parametrize("bad", ["x", "3-5", "-3"])
def test_convert_bad_scan_id_text(bad, study, tmp_path):
    assert main(["convert", str(study), "-s", bad, "-o", str(tmp_path / "out")]) == 2


def test_convert_several_scans_with_prefix_get_scan_names(study, tmp_path):
    out = tmp_path / "out"
    assert main(["convert", str(study), "-s", "1", "3", "-r", "1", "-o", str(out), "--prefix", "p"]) == 0
    names = _files(out)
    assert len(names) == 2
    assert any("scan-1" in n for n in names) and any("scan-3" in n for n in names)


def test_convert_all_scans_with_reco_keeps_skipping(study, tmp_path):
    # -s omitted: every scan; a scan without that reco is skipped as before
    out = tmp_path / "out"
    assert main(["convert", str(study), "-r", "2", "-o", str(out)]) == 0
    names = _files(out)
    assert len(names) == 1 and "scan-3" in names[0]


def test_convert_help_says_several_scans(capsys):
    with pytest.raises(SystemExit):
        main(["convert", "-h"])
    out = " ".join(capsys.readouterr().out.split())
    assert "Scan id(s) to convert" in out


def test_batch_still_refuses_scan_ids(tmp_path):
    folder = tmp_path / "studies"
    make_synthetic_study(folder / "a")
    assert main(["convert", str(folder), "--batch", "-s", "1", "3"]) == 2


def test_parser_gives_a_list():
    parser, _ = build_parser()
    args = parser.parse_args(["convert", "/p", "-s", "1", "3,4"])
    assert args.scan_id == ["1", "3,4"]
