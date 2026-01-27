#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

CONCEPT_DOI = "10.5281/zenodo.3818614"
ZENODO_BADGE_URL = "https://zenodo.org/badge/DOI/{doi}.svg"
ZENODO_RECORDS_API = "https://zenodo.org/api/records"

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


def fetch_latest_doi(concept_doi: str) -> str:
    query = urllib.parse.urlencode(
        {
            "q": f'conceptdoi:"{concept_doi}"',
            "sort": "mostrecent",
            "size": 1,
        }
    )
    url = f"{ZENODO_RECORDS_API}?{query}"
    with urllib.request.urlopen(url) as r:
        payload = json.loads(r.read().decode("utf-8"))
    hits = payload.get("hits", {}).get("hits", [])
    if not hits:
        raise RuntimeError(f"No Zenodo records found for concept DOI {concept_doi}")
    doi = hits[0].get("doi")
    if not doi:
        raise RuntimeError(f"Zenodo record missing DOI for concept DOI {concept_doi}")
    return doi


def extract_doi_from_badge(svg_bytes: bytes) -> str | None:
    text = svg_bytes.decode("utf-8", errors="ignore")
    match = re.search(r"10\.\d{4,9}/[^\s\"<>]+", text)
    if not match:
        return None
    return match.group(0)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Update Zenodo badge to latest version DOI."
    )
    parser.add_argument(
        "--up-to-date-exit-code",
        type=int,
        default=0,
        help="Exit code to use when the badge is already up to date (default: 0).",
    )
    args = parser.parse_args()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    latest_doi = fetch_latest_doi(CONCEPT_DOI)
    current_doi = None
    if OUTPUT_PATH.exists():
        current_doi = extract_doi_from_badge(OUTPUT_PATH.read_bytes())
    badge_url = ZENODO_BADGE_URL.format(doi=latest_doi)
    if current_doi:
        print(f"Current badge DOI:\n  {current_doi}")
    print(f"Resolved concept DOI:\n  {CONCEPT_DOI}\nLatest DOI:\n  {latest_doi}")
    if current_doi == latest_doi:
        print("Badge already up to date. Skipping download.")
        return args.up_to_date_exit_code
    print(f"Downloading Zenodo badge:\n  {badge_url}")
    with urllib.request.urlopen(badge_url) as r:
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
