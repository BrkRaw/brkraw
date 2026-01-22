#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
import urllib.request
from pathlib import Path

ZENODO_BADGE_URL = "https://zenodo.org/badge/DOI/10.5281/zenodo.18329489.svg"

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "docs" / "assets" / "zenodo_badge.svg"


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print("+ " + " ".join(cmd))
    return subprocess.run(cmd, check=check, text=True, capture_output=False)


def has_remote(name: str) -> bool:
    p = subprocess.run(["git", "remote"], text=True, capture_output=True)
    if p.returncode != 0:
        return False
    remotes = {line.strip() for line in p.stdout.splitlines() if line.strip()}
    return name in remotes


def main() -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"Downloading Zenodo badge:\n  {ZENODO_BADGE_URL}")
    with urllib.request.urlopen(ZENODO_BADGE_URL) as r:
        OUTPUT_PATH.write_bytes(r.read())

    print(f"Saved:\n  {OUTPUT_PATH}")

    run(["git", "add", str(OUTPUT_PATH)])

    # If nothing staged, do not commit/push
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if diff.returncode == 0:
        print("No changes staged. Nothing to commit.")
        return 0

    run(["git", "commit", "-m", "Update Zenodo DOI badge"])

    if has_remote("origin"):
        run(["git", "push", "origin"])
    else:
        print("Remote 'origin' not found. Skipping push origin.")

    if has_remote("upstream"):
        run(["git", "push", "upstream"])
    else:
        print("Remote 'upstream' not found. Skipping push upstream.")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e}", file=sys.stderr)
        raise SystemExit(1)
