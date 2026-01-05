#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRIB_PATH = REPO_ROOT / "docs" / "contrib" / "contributors.md"


def fetch_contributors(repo: str, token: str | None) -> List[Dict[str, str]]:
    contributors: List[Dict[str, str]] = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{repo}/contributors?per_page=100&page={page}"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"Failed to fetch contributors: {exc}") from exc

        if not data:
            break
        contributors.extend(data)
        page += 1
    return contributors


def filter_contributors(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    result = []
    for item in items:
        if item.get("type") == "Bot":
            continue
        login = item.get("login")
        if not login or login.endswith("[bot]"):
            continue
        result.append(item)
    return result


def render_table(items: List[Dict[str, str]], per_row: int = 6) -> str:
    rows = []
    for i in range(0, len(items), per_row):
        chunk = items[i : i + per_row]
        cells = []
        for user in chunk:
            login = user.get("login", "")
            url = user.get("html_url", "")
            avatar = user.get("avatar_url", "")
            if avatar:
                avatar = f"{avatar}&s=100"
            cell = (
                '<td align="center">'
                f'<a href="{url}">'
                f'<img src="{avatar}" width="80" height="80" alt="{login}"/><br />'
                f"<sub><b>{login}</b></sub>"
                "</a>"
                "</td>"
            )
            cells.append(cell)
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return "<table>\n" + "\n".join(rows) + "\n</table>"


def main() -> int:
    parser = argparse.ArgumentParser(description="Update contributors doc from GitHub.")
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY"),
        help="GitHub repository (owner/name). Defaults to GITHUB_REPOSITORY.",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub token for API access (recommended to avoid rate limits).",
    )
    args = parser.parse_args()

    if not args.repo:
        raise SystemExit("Repository not specified. Use --repo or GITHUB_REPOSITORY.")

    contributors = fetch_contributors(args.repo, args.token)
    contributors = filter_contributors(contributors)

    header = "# Contributors\n\n"
    intro = "Thanks to everyone who has contributed to BrkRaw.\n\n"
    note = "_This page is auto-generated from GitHub contributors._\n\n"
    table = render_table(contributors)
    updated = f"_Last updated: {dt.date.today().isoformat()}_\n"

    content = header + intro + note + table + "\n\n" + updated
    CONTRIB_PATH.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
