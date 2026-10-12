"""Setup for the manual checks in this folder (not collected by the normal test run).

Run from the repository root, after the approved anonymized zips are in place
(``<checkout>/../agent-fixtures``, or ``BRKRAW_AGENT_FIXTURES=/path``)::

    pytest -v scripts/validate/check_agent_fixtures.py

See "Tests and manual checks on real data" in docs/dev/contributing.md.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]

for _path in (str(HERE), str(REPO_ROOT), str(REPO_ROOT / "src")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from agent_fixtures import find_approved_zips, fixtures_dir  # noqa: E402
from tests.helpers import KEEP_ENV, isolate_brkraw_env  # noqa: E402


def pytest_configure(config):
    # No brkraw session variables, and a config home that is never ~/.brkraw.
    for key in list(os.environ):
        if key.startswith("BRKRAW_") and key not in KEEP_ENV:
            del os.environ[key]
    os.environ["BRKRAW_CONFIG_HOME"] = os.path.join(tempfile.gettempdir(), "brkraw-pytest-validate-config")


@pytest.fixture(autouse=True)
def _isolated_brkraw_env(tmp_path_factory, monkeypatch):
    """Every check gets its own empty config home and HOME, like the tests in ``tests/``."""
    isolate_brkraw_env(monkeypatch, tmp_path_factory.mktemp("brkraw-env"))
    before = {k for k in os.environ if k.startswith("BRKRAW_")}
    yield
    for key in [k for k in os.environ if k.startswith("BRKRAW_") and k not in before]:
        del os.environ[key]


@pytest.fixture
def cwd(tmp_path, monkeypatch):
    out = tmp_path / "work"
    out.mkdir()
    monkeypatch.chdir(out)
    return out


@pytest.fixture
def approved_zips(tmp_path):
    """Return a function ``approved_zips(pv)`` -> list of approved zips copied into ``tmp_path``.

    Unlike a test, a manual check does not skip: when the agent-fixtures folder
    is missing the run stops with a message, and when it has no approved zip
    for ``pv`` (README row not approved, file missing, SHA-256 differs) the
    check fails and says why. Nothing is written in the folder itself.
    """

    def _get(pv: str):
        folder = fixtures_dir()
        if not folder.is_dir():
            pytest.exit(
                "agent-fixtures folder not found: {}\n"
                "Put the approved anonymized zips there or set BRKRAW_AGENT_FIXTURES=/path "
                "(docs/dev/contributing.md, 'Tests and manual checks on real data').".format(folder),
                returncode=2,
            )
        found, reasons = find_approved_zips(folder, pv)
        if not found:
            pytest.fail("no approved agent fixture for {}: {}".format(pv, "; ".join(reasons)))
        dest = tmp_path / "agent-fixtures" / pv
        dest.mkdir(parents=True, exist_ok=True)
        copies = []
        for src in found:
            target = dest / src.name
            shutil.copyfile(src, target)
            copies.append(target)
        return copies

    return _get
