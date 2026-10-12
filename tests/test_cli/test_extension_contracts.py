"""Public entry-point contracts of the installed core distribution."""

import argparse
from importlib import metadata

from brkraw.specs.hook import resolve_hook


def _entry_points(group):
    return [ep for ep in metadata.distribution("brkraw").entry_points if ep.group == group]


def test_core_cli_entry_points_register_commands():
    entry_points = _entry_points("brkraw.cli")
    assert entry_points
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    for ep in entry_points:
        register = ep.load()
        assert callable(register), ep.name
        register(subparsers)
        assert ep.name in subparsers.choices


def test_converter_hook_rejects_invalid_mapping():
    valid = resolve_hook({"get_dataobj": lambda scan: scan})
    assert callable(valid["get_dataobj"])

    try:
        resolve_hook({"not_a_hook": lambda scan: scan})
    except ValueError as exc:
        assert "invalid key" in str(exc)
    else:
        raise AssertionError("invalid converter hook was accepted")
