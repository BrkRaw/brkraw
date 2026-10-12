"""Cache size warning and per-entry clean-up before a command; retry after a hook's
memory stop (WI-0074, AP-0015).

Deleting is the risk here, so the tests pin down: only ``y``/``yes`` deletes,
every other answer and end of input keep everything, nothing is asked or
deleted without a terminal, and each subfolder (``sordino/``) is its own choice.
"""
import io

import pytest

from brkraw.cli import cache_check
from brkraw.cli.commands import convert as convert_cmd
from brkraw.cli.main import main
from brkraw.core import cache as cache_core
from brkraw.core import config as config_core

KB = 1024


class _Tty(io.StringIO):
    def isatty(self):
        return True


class _NoRead(io.StringIO):
    """Not a terminal; reading from it is a test failure."""

    def isatty(self):
        return False

    def readline(self, *a):
        raise AssertionError("asked a question without a terminal")


def _config(warn_gb):
    root = config_core.resolve_root(None)
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.yaml").write_text(f"config_version: 0\ncache:\n  warn_size_gb: {warn_gb}\n", encoding="utf-8")


def _cache(sordino_kb=8, viewer_kb=2, loose_kb=1):
    base = config_core.cache_dir(None)
    (base / "sordino").mkdir(parents=True, exist_ok=True)
    (base / "sordino" / "recon_1.bin").write_bytes(b"s" * sordino_kb * KB)
    (base / "viewer").mkdir(exist_ok=True)
    (base / "viewer" / "v.npy").write_bytes(b"v" * viewer_kb * KB)
    (base / "loose.txt").write_bytes(b"l" * loose_kb * KB)
    return base


def _names(base):
    return sorted(p.name for p in base.iterdir())


ALL = ["loose.txt", "sordino", "viewer"]
TINY_GB = 1 / (1024 * 1024)      # 1 KB: the 11 KB test cache is above it


def _run(answers, **kw):
    err = io.StringIO()
    res = cache_check.check_cache("info", stdin=_Tty(answers), stderr=err, interactive=True, **kw)
    return res, err.getvalue()


# --- answers ---------------------------------------------------------------

@pytest.mark.parametrize("answer", ["", "n", "N", "no", "x", "yess", "ye", "1", "nope", " ", "y y", "oui"])
def test_any_answer_but_yes_deletes_nothing(answer):
    _config(TINY_GB)
    base = _cache()
    res, text = _run(f"{answer}\n{answer}\n{answer}\n")
    assert res["warned"] and res["asked"] == ["sordino", "viewer", cache_core.FILES_ENTRY]
    assert res["cleared"] == [] and _names(base) == ALL
    assert "Nothing was deleted." in text


def test_end_of_input_deletes_nothing_and_stops_asking():
    _config(TINY_GB)
    base = _cache()
    res, _ = _run("")
    assert res["asked"] == ["sordino"] and res["cleared"] == [] and _names(base) == ALL


@pytest.mark.parametrize("answer", ["y", "Y", "yes", "YES", " yes "])
def test_yes_deletes_only_the_entry_it_answers(answer):
    _config(TINY_GB)
    base = _cache()
    res, text = _run(f"{answer}\nn\n\n")
    assert res["cleared"] == ["sordino"]
    assert _names(base) == ["loose.txt", "viewer"]
    assert "Cleared" in text


def test_sordino_is_asked_separately_from_the_rest():
    _config(TINY_GB)
    base = _cache()
    res, text = _run("n\ny\ny\n")
    assert "Clear sordino/ (8.00 KB, 1 files)? [y/N]: " in text
    assert res["cleared"] == ["viewer", cache_core.FILES_ENTRY]
    assert _names(base) == ["sordino"]


def test_largest_entry_is_asked_first():
    _config(TINY_GB)
    _cache(sordino_kb=1, viewer_kb=9)
    res, _ = _run("n\nn\nn\n")
    assert res["asked"][0] == "viewer"


# --- no terminal -----------------------------------------------------------

def test_without_a_terminal_it_warns_but_never_asks_or_deletes():
    _config(TINY_GB)
    base = _cache()
    err = _NoRead()
    res = cache_check.check_cache("convert", stdin=_NoRead(), stderr=err)
    assert res["warned"] and res["asked"] == [] and res["cleared"] == []
    assert _names(base) == ALL
    text = err.getvalue()
    assert "warning: the brkraw cache holds" in text and "sordino/" in text
    assert "Nothing was deleted" in text and "brkraw cache clear --only" in text


@pytest.mark.parametrize("stdin_tty,stderr_tty,want", [(True, True, True), (True, False, False),
                                                       (False, True, False), (False, False, False)])
def test_terminal_means_stdin_and_stderr(stdin_tty, stderr_tty, want):
    a = _Tty() if stdin_tty else io.StringIO()
    b = _Tty() if stderr_tty else io.StringIO()
    assert cache_check.is_interactive(a, b) is want


# --- when the check runs ---------------------------------------------------

def test_below_the_size_nothing_is_said():
    _config(1)
    _cache()
    err = _NoRead()
    res = cache_check.check_cache("info", stdin=_NoRead(), stderr=err)
    assert res["checked"] and not res["warned"] and err.getvalue() == ""


def test_default_size_is_10_gb():
    _cache()
    assert cache_check.warn_size_bytes() == 10 * 1024 ** 3
    assert config_core.resolve_config()["cache"]["warn_size_gb"] == 10


def test_size_zero_turns_the_check_off(monkeypatch):
    _config(0)
    _cache()
    monkeypatch.setattr(cache_core, "get_info", lambda *a, **k: pytest.fail("measured with the check off"))
    assert cache_check.check_cache("info", stdin=_NoRead(), stderr=_NoRead())["checked"] is False


def test_environment_variable_turns_the_check_off(monkeypatch):
    _config(TINY_GB)
    _cache()
    monkeypatch.setenv("BRKRAW_NO_CACHE_CHECK", "1")
    monkeypatch.setattr(cache_core, "get_info", lambda *a, **k: pytest.fail("measured with the check off"))
    assert cache_check.check_cache("info", stdin=_NoRead(), stderr=_NoRead())["checked"] is False


@pytest.mark.parametrize("command", ["cache", "config", "init"])
def test_cache_config_and_init_are_not_checked(monkeypatch, command):
    _config(TINY_GB)
    _cache()
    monkeypatch.setattr(cache_core, "get_info", lambda *a, **k: pytest.fail("checked before " + command))
    assert cache_check.check_cache(command, stdin=_NoRead(), stderr=_NoRead())["checked"] is False


@pytest.mark.parametrize("value", ["lots", -1, "[1, 2]"])
def test_a_bad_size_value_warns_and_uses_the_default(value):
    _config(value)
    err = io.StringIO()
    import sys
    old, sys.stderr = sys.stderr, err
    try:
        assert cache_check.warn_size_bytes() == 10 * 1024 ** 3
    finally:
        sys.stderr = old
    assert "cache.warn_size_gb must be a number" in err.getvalue()


def test_a_failing_clear_is_reported_and_the_rest_goes_on(monkeypatch):
    _config(TINY_GB)
    base = _cache()
    real = cache_core.clear

    def clear(root=None, path=None, *, only=None):
        if only == ["sordino"]:
            raise OSError("busy")
        return real(root=root, path=path, only=only)

    monkeypatch.setattr(cache_core, "clear", clear)
    res, text = _run("y\ny\nn\n")
    assert "could not clear sordino/" in text
    assert res["cleared"] == ["viewer"] and _names(base) == ["loose.txt", "sordino"]


# --- the check never stops a command (wi-0074-choi-1 F1) -------------------

@pytest.mark.parametrize("value", [".inf", "inf"])
def test_an_infinite_size_turns_the_check_off(value):
    root = config_core.resolve_root(None)
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.yaml").write_text(f"config_version: 0\ncache:\n  warn_size_gb: {value}\n", encoding="utf-8")
    _cache()
    assert cache_check.warn_size_bytes() is None
    assert cache_check.check_cache("info", stdin=_NoRead(), stderr=_NoRead())["checked"] is False


def test_an_infinite_size_does_not_stop_main(tmp_path, capsys):
    root = config_core.resolve_root(None)
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.yaml").write_text("config_version: 0\ncache:\n  warn_size_gb: .inf\n", encoding="utf-8")
    _cache()
    assert main(["info", str(tmp_path / "no-such-study")]) == 2      # info's own "path not found"


def test_any_error_in_the_check_leaves_the_command_alone(monkeypatch, tmp_path, capsys):
    _config(TINY_GB)
    base = _cache()
    missing = str(tmp_path / "no-such-study")
    want = main(["info", missing])

    def broken(*a, **k):
        raise OSError("stderr is gone")

    monkeypatch.setattr(cache_check, "check_cache", broken)
    assert main(["info", missing]) == want
    assert _names(base) == ALL


def test_a_broken_answer_stream_deletes_nothing(monkeypatch, tmp_path, capsys):
    _config(TINY_GB)
    base = _cache()

    class Broken(_Tty):
        def readline(self, *a):
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad byte")

    monkeypatch.setattr(cache_check, "is_interactive", lambda *a, **k: True)
    monkeypatch.setattr("sys.stdin", Broken())
    missing = str(tmp_path / "no-such-study")
    assert main(["info", missing]) == 2
    assert _names(base) == ALL


def test_no_stderr_means_no_check(monkeypatch):
    _config(TINY_GB)
    _cache()
    monkeypatch.setattr("sys.stderr", None)
    assert cache_check.check_cache("info", stdin=_NoRead())["checked"] is False


def test_a_linked_folder_does_not_trigger_the_warning(tmp_path):
    """Only what clearing frees counts: a link to a big folder elsewhere adds nothing."""
    import os

    _config(1 / 1024)                     # 1 MB
    base = _cache()
    big = tmp_path / "elsewhere"
    big.mkdir()
    (big / "huge.bin").write_bytes(b"h" * 2 * 1024 * KB)       # 2 MB behind a link
    os.symlink(big, base / "linked")
    os.symlink(big, base / "sordino" / "inner-link")
    assert cache_core.get_info(by_entry=True)["size"] > 2 * 1024 * KB      # the total follows links
    res = cache_check.check_cache("info", stdin=_NoRead(), stderr=_NoRead())
    assert res["checked"] and not res["warned"]
    by = {e["name"]: e for e in cache_core.get_info(by_entry=True)["entries"]}
    assert by["sordino"]["size"] == 8 * KB


def test_a_folder_named_like_the_files_group_is_never_offered():
    """y to a prompt must delete what the prompt names (wi-0074-choi-2 finding 1)."""
    _config(TINY_GB)
    base = _cache()
    odd = base / cache_core.FILES_ENTRY
    odd.mkdir()
    (odd / "x.bin").write_bytes(b"x" * 4 * KB)
    res, text = _run("n\nn\nn\nn\n")
    assert f"Clear {cache_core.FILES_ENTRY}/ " not in text
    assert res["asked"] == ["sordino", "viewer", cache_core.FILES_ENTRY]
    res, _ = _run("n\nn\ny\n")                                  # y to the loose files
    assert not (base / "loose.txt").exists() and (odd / "x.bin").exists()


def test_cache_clear_only_files_group_never_means_a_same_named_folder(capsys):
    base = _cache()
    odd = base / cache_core.FILES_ENTRY
    odd.mkdir()
    (odd / "x.bin").write_bytes(b"x")
    assert main(["cache", "clear", "--only", cache_core.FILES_ENTRY, "-y"]) == 0
    assert not (base / "loose.txt").exists() and (odd / "x.bin").exists()


def test_get_scan_failing_keeps_the_hook_error(monkeypatch):
    monkeypatch.setattr(cache_check, "is_interactive", lambda *a, **k: True)
    monkeypatch.setattr("sys.stdin", _NoRead())

    class Loader(_Loader):
        def get_scan(self, scan_id):
            raise KeyError(scan_id)

    loader = Loader([_Stop({"max_memory_gb": 7.5})])
    with pytest.raises(_Stop):
        convert_cmd._convert_scan(loader, 5, None, KW, {})


# --- through main() --------------------------------------------------------

def test_the_warning_does_not_change_the_command_result(capsys, tmp_path):
    missing = str(tmp_path / "no-such-study")
    _config(1)
    _cache()
    quiet = main(["info", missing])
    _config(TINY_GB)
    loud = main(["info", missing])
    err = capsys.readouterr().err
    assert quiet == loud
    assert "warning: the brkraw cache holds" in err
    assert _names(config_core.cache_dir(None)) == ALL      # capsys is not a terminal


def test_in_a_terminal_main_asks_before_the_command(monkeypatch, tmp_path, capsys):
    _config(TINY_GB)
    base = _cache()
    monkeypatch.setattr(cache_check, "is_interactive", lambda *a, **k: True)
    monkeypatch.setattr("sys.stdin", _Tty("y\n\n\n"))
    rc = main(["info", str(tmp_path / "no-such-study")])
    assert rc == main(["info", str(tmp_path / "no-such-study")])
    assert _names(base) == ["loose.txt", "viewer"]


def test_help_and_version_are_never_checked(monkeypatch):
    _config(TINY_GB)
    _cache()
    monkeypatch.setattr(cache_check, "check_cache", lambda *a, **k: pytest.fail("checked on help"))
    assert main(["-h"]) == 0
    with pytest.raises(SystemExit):
        main(["--version"])
    with pytest.raises(SystemExit):
        main(["convert", "-h"])


# --- brkraw cache info / clear --only --------------------------------------

def test_cache_info_lists_the_entries(capsys):
    _cache()
    assert main(["cache", "info"]) == 0
    out = capsys.readouterr().out
    assert "Entries:" in out and "sordino/" in out and "viewer/" in out and cache_core.FILES_ENTRY in out
    assert "Size:  11.00 KB" in out and "Files: 3" in out


def test_cache_clear_only_sordino(capsys):
    base = _cache()
    assert main(["cache", "clear", "--only", "sordino", "-y"]) == 0
    assert _names(base) == ["loose.txt", "viewer"]


def test_cache_clear_only_several(capsys):
    base = _cache()
    assert main(["cache", "clear", "--only", "viewer", "--only", cache_core.FILES_ENTRY, "-y"]) == 0
    assert _names(base) == ["sordino"]


def test_cache_clear_only_unknown_deletes_nothing(capsys):
    base = _cache()
    assert main(["cache", "clear", "--only", "sordino", "--only", "nothere", "-y"]) == 1
    assert _names(base) == ALL


@pytest.mark.parametrize("answer", ["", "n", "whatever"])
def test_cache_clear_only_asks_and_keeps_on_other_answers(monkeypatch, capsys, answer):
    base = _cache()
    monkeypatch.setattr("sys.stdin", io.StringIO(answer + "\n" if answer else ""))
    assert main(["cache", "clear", "--only", "sordino"]) == 1
    assert _names(base) == ALL


def test_cache_clear_only_asks_and_deletes_on_yes(monkeypatch, capsys):
    base = _cache()
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))
    assert main(["cache", "clear", "--only", "sordino"]) == 0
    assert _names(base) == ["loose.txt", "viewer"]


def test_cache_clear_without_only_is_unchanged(monkeypatch, capsys):
    base = _cache()
    monkeypatch.setattr("sys.stdin", io.StringIO("n\n"))
    assert main(["cache", "clear"]) == 1
    assert _names(base) == ALL
    assert main(["cache", "clear", "-y"]) == 0
    assert _names(base) == []


# --- retry after a hook's memory stop --------------------------------------

class _Stop(MemoryError):
    def __init__(self, retry):
        super().__init__("SORDINO: needs about 7.40 GiB of memory, above the limit.")
        self.retry_kwargs = retry


class _Scan:
    _converter_hook_name = "sordino"


class _Loader:
    def __init__(self, errors):
        self.errors = list(errors)
        self.calls = []

    def get_scan(self, scan_id):
        return _Scan()

    def convert(self, scan_id, reco_id=None, **kw):
        self.calls.append(kw)
        if self.errors:
            raise self.errors.pop(0)
        return "nii"


KW = {"space": "subject_ras", "hook_args_by_name": {"sordino": {"offset": 3, "max_memory_gb": 2}}}


def test_retry_once_with_the_hook_values_after_yes(monkeypatch, capsys):
    monkeypatch.setattr(cache_check, "is_interactive", lambda *a, **k: True)
    monkeypatch.setattr("sys.stdin", _Tty("y\n"))
    loader = _Loader([_Stop({"max_memory_gb": 7.5})])
    assert convert_cmd._convert_scan(loader, 5, None, KW, {"frames": 1}) == "nii"
    assert len(loader.calls) == 2
    assert loader.calls[1]["hook_args_by_name"]["sordino"] == {"offset": 3, "max_memory_gb": 7.5}
    assert loader.calls[1]["frames"] == 1 and loader.calls[1]["space"] == "subject_ras"
    assert KW["hook_args_by_name"]["sordino"]["max_memory_gb"] == 2          # caller's dict untouched
    err = capsys.readouterr().err
    assert "needs about 7.40 GiB" in err and "Proceed anyway with max_memory_gb=7.5 for scan 5? [y/N]" in err


@pytest.mark.parametrize("answer", ["", "n", "no", "x"])
def test_no_retry_on_other_answers(monkeypatch, capsys, answer):
    monkeypatch.setattr(cache_check, "is_interactive", lambda *a, **k: True)
    monkeypatch.setattr("sys.stdin", _Tty(answer + "\n" if answer else ""))
    loader = _Loader([_Stop({"max_memory_gb": 7.5})])
    with pytest.raises(MemoryError):
        convert_cmd._convert_scan(loader, 5, None, KW, {})
    assert len(loader.calls) == 1


def test_no_question_and_no_retry_without_a_terminal(monkeypatch):
    monkeypatch.setattr(cache_check, "is_interactive", lambda *a, **k: False)
    monkeypatch.setattr("sys.stdin", _NoRead())
    loader = _Loader([_Stop({"max_memory_gb": 7.5})])
    with pytest.raises(MemoryError):
        convert_cmd._convert_scan(loader, 5, None, KW, {})
    assert len(loader.calls) == 1


def test_only_one_retry(monkeypatch, capsys):
    monkeypatch.setattr(cache_check, "is_interactive", lambda *a, **k: True)
    monkeypatch.setattr("sys.stdin", _Tty("y\ny\n"))
    loader = _Loader([_Stop({"max_memory_gb": 7.5}), _Stop({"max_memory_gb": 9.0})])
    with pytest.raises(MemoryError):
        convert_cmd._convert_scan(loader, 5, None, KW, {})
    assert len(loader.calls) == 2


@pytest.mark.parametrize("err", [MemoryError("plain"), _Stop(None), _Stop({})])
def test_a_memory_error_without_retry_values_is_passed_on(monkeypatch, err):
    monkeypatch.setattr(cache_check, "is_interactive", lambda *a, **k: True)
    monkeypatch.setattr("sys.stdin", _NoRead())
    loader = _Loader([err])
    with pytest.raises(MemoryError):
        convert_cmd._convert_scan(loader, 5, None, KW, {})
    assert len(loader.calls) == 1


def test_hook_args_given_under_an_alias_are_kept(monkeypatch, capsys):
    """_resolve_hook_kwargs finds args under the package name too; the retry keeps them."""
    from brkraw.apps.loader import helper

    monkeypatch.setattr(helper, "_resolve_hook_kwargs",
                        lambda scan, by_name: {"offset": 4})
    monkeypatch.setattr(convert_cmd, "_resolve_hook_kwargs", helper._resolve_hook_kwargs)
    monkeypatch.setattr(cache_check, "is_interactive", lambda *a, **k: True)
    monkeypatch.setattr("sys.stdin", _Tty("y\n"))
    loader = _Loader([_Stop({"max_memory_gb": 7.5})])
    kw = {"hook_args_by_name": {"brkraw-sordino": {"offset": 4}}}
    convert_cmd._convert_scan(loader, 5, None, kw, {})
    assert loader.calls[1]["hook_args_by_name"]["sordino"] == {"offset": 4, "max_memory_gb": 7.5}
