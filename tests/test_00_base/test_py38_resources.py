"""Python 3.8 has no ``importlib.resources.files`` (added in 3.9). brkraw
supports 3.8 and falls back to the ``importlib_resources`` package (declared
for python_version < '3.9'). Every file that calls ``resources.files(`` must
carry that fallback; this test finds a missing one on any Python version
(CI on 3.8 failed with ``AttributeError`` on prune, 0.6.0rc1)."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _users():
    for folder in ("src", "tests"):
        for path in sorted((REPO / folder).rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            if "resources.files(" in text:
                yield path.relative_to(REPO), text


def test_there_are_users_to_check():
    assert any(True for _ in _users())


def test_every_user_of_resources_files_has_the_38_fallback():
    missing = [str(rel) for rel, text in _users()
               if rel.name != Path(__file__).name and "import importlib_resources" not in text]
    assert missing == []


def test_the_fallback_package_is_declared_for_38():
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert "importlib-resources>=5; python_version < '3.9'" in text
