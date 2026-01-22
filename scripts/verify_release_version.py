#!/usr/bin/env python3
from __future__ import annotations

import argparse
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

    version_path = (
        pyproject.get("tool", {}).get("hatch", {}).get("version", {}).get("path")
    )
    if not version_path:
        raise SystemExit("No version in pyproject.toml and no hatch version path found.")

    text = Path(version_path).read_text(encoding="utf-8")
    match = re.search(r"""__version__\s*=\s*["']([^"']+)["']""", text)
    if not match:
        raise SystemExit(f"No __version__ found in {version_path}")
    return match.group(1)


def normalize_tag(tag: str) -> str:
    tag = tag.strip()
    if tag.startswith("refs/tags/"):
        tag = tag.removeprefix("refs/tags/")
    # Common convention: v1.2.3
    if tag.startswith("v") and len(tag) > 1 and tag[1].isdigit():
        tag = tag[1:]
    return tag


def resolve_tag(cli_tag: str | None) -> str:
    if cli_tag:
        return cli_tag

    env_tag = os.environ.get("TAG")
    if env_tag:
        return env_tag

    ref_name = os.environ.get("GITHUB_REF_NAME")
    if ref_name:
        return ref_name

    ref = os.environ.get("GITHUB_REF")
    if ref:
        return ref  # will be normalized later (refs/tags/...)

    raise SystemExit(
        "No tag provided. Pass --tag <tag>, or set TAG env var, or run under GitHub Actions."
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Verify that the git tag matches the package version."
    )
    ap.add_argument(
        "--tag",
        help="Release tag to verify (e.g. 1.2.3 or v1.2.3). If omitted, uses TAG/GITHUB_REF_NAME/GITHUB_REF.",
        default=None,
    )
    args = ap.parse_args()

    raw_tag = resolve_tag(args.tag)
    tag = normalize_tag(raw_tag)
    print(f"Target Tag: {raw_tag} (normalized: {tag})")

    version = read_version_from_pyproject(Path("pyproject.toml"))
    print(f"Detected Package Version: {version}")

    if parse(tag) != parse(version):
        raise SystemExit(f"Tag {raw_tag} does not match package version {version}.")

    print("Version check passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
