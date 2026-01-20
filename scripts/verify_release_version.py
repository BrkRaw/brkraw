#!/usr/bin/env python3
from __future__ import annotations

import os
import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - for Python < 3.11
    import tomli as tomllib

from packaging.version import parse


def read_version_from_pyproject(pyproject_path: Path) -> str:
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    version = pyproject.get("project", {}).get("version")
    if version:
        return version

    version_path = pyproject.get("tool", {}).get("hatch", {}).get("version", {}).get("path")
    if not version_path:
        raise SystemExit("No version in pyproject.toml and no hatch version path found.")

    text = Path(version_path).read_text(encoding="utf-8")
    match = re.search(r"__version__\\s*=\\s*[\"\\x27]([^\"\\x27]+)[\"\\x27]", text)
    if not match:
        raise SystemExit(f"No __version__ found in {version_path}")
    return match.group(1)


def main() -> int:
    tag = os.environ["TAG"]
    print(f"Target Tag: {tag}")

    version = read_version_from_pyproject(Path("pyproject.toml"))
    print(f"Detected Package Version: {version}")

    if parse(tag) != parse(version):
        raise SystemExit(f"Tag {tag} does not match package version {version}.")

    print("Version check passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
