#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_PATH = REPO_ROOT / "src" / "brkraw" / "__init__.py"
RELEASE_NOTES_PATH = REPO_ROOT / "RELEASE_NOTES.md"


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def fetch_tags(remote: str) -> None:
    result = run_git(["fetch", "--tags", remote])
    if result.returncode != 0:
        stderr = result.stderr.strip()
        print(f"Warning: failed to fetch tags from {remote}: {stderr}")
        if remote != "origin":
            fallback = run_git(["fetch", "--tags", "origin"])
            if fallback.returncode != 0:
                fallback_err = fallback.stderr.strip()
                print(f"Warning: failed to fetch tags from origin: {fallback_err}")


def read_version() -> str:
    init_text = INIT_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"^__version__(?:\s*:\s*[^=]+)?\s*=\s*['\"]([^'\"]+)['\"]",
        init_text,
        re.M,
    )
    if not match:
        raise SystemExit("No __version__ found in src/brkraw/__init__.py")
    return match.group(1)


def generate_release_notes(version: str) -> None:
    tag_result = run_git(["describe", "--tags", "--abbrev=0"])
    last_tag = tag_result.stdout.strip() if tag_result.returncode == 0 else ""
    log_range = f"{last_tag}..HEAD" if last_tag else "HEAD"
    log_result = run_git(
        ["log", log_range, "--no-merges", "--pretty=format:- %s (%h)"]
    )
    changes = log_result.stdout.strip()
    if not changes:
        changes = "- (no changes found)"

    date_str = dt.date.today().isoformat()
    header = f"# Release v{version}\n\n"
    meta = f"Date: {date_str}\n"
    scope = f"Changes since {last_tag}\n\n" if last_tag else "Changes\n\n"
    RELEASE_NOTES_PATH.write_text(header + meta + scope + changes + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate RELEASE_NOTES.md without bumping versions."
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Override version (default: read from src/brkraw/__init__.py).",
    )
    parser.add_argument(
        "--fetch-tags",
        action="store_true",
        help="Fetch tags from remote before generating notes",
    )
    parser.add_argument(
        "--remote",
        default="upstream",
        help="Remote name for fetching tags (default: upstream)",
    )
    args = parser.parse_args()

    if args.fetch_tags:
        fetch_tags(args.remote)

    version = args.version or read_version()
    generate_release_notes(version)
    print(f"Generated {RELEASE_NOTES_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
