#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import urllib.error
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = REPO_ROOT / "docs" / "dev" / "contributors.md"

_GITHUB_LOGIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,37}[a-z0-9])?$")


def _infer_github_login(name: str, email: str) -> Optional[str]:
    email_lower = email.lower().strip()
    if email_lower.endswith("@users.noreply.github.com"):
        local = email_lower.split("@", 1)[0]
        if "+" in local:
            local = local.split("+", 1)[1]
        local = local.strip()
        if local and not local.endswith("[bot]"):
            return local
    name = name.strip()
    if name.startswith("@") and len(name) > 1:
        return name[1:]
    # Heuristic: when the author name itself looks like a GitHub login (e.g. "dvm-shlee"),
    # treat it as such. Keep this conservative to avoid incorrect matches for common names.
    if (
        name
        and name == name.lower()
        and ("-" in name or any(ch.isdigit() for ch in name))
        and _GITHUB_LOGIN_RE.fullmatch(name)
    ):
        return name
    return None


def git_contributors() -> List[Dict[str, str]]:
    try:
        out = subprocess.check_output(
            ["git", "shortlog", "-sne", "--all"],
            cwd=REPO_ROOT,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"Failed to read git shortlog: {exc}") from exc

    contributors: List[Dict[str, str]] = []
    for line in out.splitlines():
        raw = line.strip()
        if not raw:
            continue
        # Format: "<count>\tName <email>"
        try:
            count_str, rest = raw.split("\t", 1)
            count = int(count_str.strip())
        except ValueError:
            continue
        if "<" not in rest or ">" not in rest:
            continue
        name = rest.split("<", 1)[0].strip()
        email = rest.split("<", 1)[1].split(">", 1)[0].strip()
        if not name or not email:
            continue
        if "[bot]" in name.lower() or email.lower().endswith("[bot]"):
            continue
        login = _infer_github_login(name, email)
        contributors.append(
            {
                "name": name,
                "email": email,
                "count": str(count),
                "login": login or "",
            }
        )
    return contributors


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


def _render_markdown_list(items: List[Dict[str, str]]) -> str:
    lines: List[str] = []
    for item in items:
        login = (item.get("login") or "").strip()
        name = (item.get("name") or login or "").strip()
        if not name:
            continue
        if login:
            lines.append(f"- [{login}](https://github.com/{login})")
        else:
            lines.append(f"- {name}")
    return "\n".join(lines)


def _avatar_url_with_size(url: str, *, size: int = 96) -> str:
    url = (url or "").strip()
    if not url:
        return url
    # Keep URLs short to reduce markdownlint MD013 noise (especially in ref defs).
    parts = urllib.parse.urlsplit(url)
    base = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    size_param = "size" if parts.netloc.lower() == "github.com" else "s"
    return f"{base}?{size_param}={size}"


def _escape_table_text(text: str) -> str:
    return (text or "").replace("|", "\\|").strip()


def _render_github_avatar_table(items: List[Dict[str, str]], *, per_row: int = 6) -> str:
    users = []
    for item in items:
        login = (item.get("login") or "").strip()
        if not login:
            continue
        display = (item.get("name") or login).strip() or login
        html_url = (item.get("html_url") or f"https://github.com/{login}").strip()
        avatar_url = (item.get("avatar_url") or f"https://github.com/{login}.png").strip()
        users.append(
            {
                "login": login,
                "display": display,
                "url": html_url,
                "avatar": _avatar_url_with_size(avatar_url, size=96),
            }
        )

    if not users:
        return ""

    cols = per_row
    header = "| " + " | ".join([""] * cols) + " |"
    sep = "| " + " | ".join(["---"] * cols) + " |"
    lines: List[str] = [header, sep]

    refs: List[str] = []
    for idx in range(0, len(users), cols):
        chunk = users[idx : idx + cols]
        row_cells: List[str] = []
        for user in chunk:
            ref_profile = user["login"].lower()
            ref_avatar = f"{ref_profile}-avatar"
            label = _escape_table_text(user["display"])
            row_cells.append(f"[![{label}][{ref_avatar}]][{ref_profile}]<br>{label}")
            refs.append(f"[{ref_profile}]: {user['url']}")
            refs.append(f"[{ref_avatar}]: {user['avatar']}")
        while len(row_cells) < cols:
            row_cells.append("")
        lines.append("| " + " | ".join(row_cells) + " |")

    lines.append("")
    lines.extend(refs)
    return "\n".join(lines)


def _normalize_github_items(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for item in items:
        login = (item.get("login") or "").strip()
        if not login:
            continue
        normalized.append(
            {
                "login": login,
                "name": login,
                "html_url": (item.get("html_url") or "").strip(),
                "avatar_url": (item.get("avatar_url") or "").strip(),
            }
        )
    return normalized


def _normalize_git_items(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    by_email: Dict[str, Dict[str, str]] = {}
    for item in items:
        email = (item.get("email") or "").strip().lower()
        if not email:
            continue
        name = (item.get("name") or "").strip()
        login = (item.get("login") or "").strip()
        count = int((item.get("count") or "0").strip() or "0")

        current = by_email.get(email)
        if current is None:
            by_email[email] = {"email": email, "name": name, "login": login, "count": str(count)}
            continue

        current["count"] = str(int(current.get("count", "0")) + count)
        if not current.get("login") and login:
            current["login"] = login
        if name and (" " in name) and (" " not in (current.get("name") or "")):
            current["name"] = name
        elif name and not current.get("name"):
            current["name"] = name

    merged = list(by_email.values())
    merged.sort(key=lambda x: int(x.get("count", "0")), reverse=True)

    seen: set[str] = set()
    normalized: List[Dict[str, str]] = []
    for item in merged:
        login = (item.get("login") or "").strip()
        name = (item.get("name") or "").strip()
        key = login or name
        if not key or key in seen:
            continue
        seen.add(key)
        normalized.append({"login": login, "name": name})
    return normalized


def _parse_source(value: str) -> str:
    src = (value or "").strip().lower()
    if src in {"git", "github"}:
        return src
    raise SystemExit("--source must be 'git' or 'github'.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Update contributors doc (from local git history or GitHub)."
    )
    parser.add_argument(
        "--source",
        default=os.environ.get("BRKRAW_CONTRIBUTORS_SOURCE", "git"),
        help="Data source: git (default) or github. Can set BRKRAW_CONTRIBUTORS_SOURCE.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help=f"Output markdown path. Defaults to {DEFAULT_OUTPUT_PATH}.",
    )
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

    source = _parse_source(args.source)
    output_path = Path(args.output)

    if source == "github":
        if not args.repo:
            raise SystemExit("Repository not specified. Use --repo or GITHUB_REPOSITORY.")
        contributors = _normalize_github_items(filter_contributors(fetch_contributors(args.repo, args.token)))
        source_note = "This page is auto-generated from GitHub contributors."
    else:
        contributors = _normalize_git_items(git_contributors())
        source_note = "This page is auto-generated from local git history."

    header = "# Contributors\n\n"
    intro = (
        "BrkRaw is developed and maintained as a community-driven open source project.\n"
        "We gratefully acknowledge everyone who has contributed code, documentation,\n"
        "ideas, and feedback.\n\n"
    )
    note = f"{source_note}\n\n"
    with_login = [c for c in contributors if (c.get("login") or "").strip()]
    without_login = [c for c in contributors if not (c.get("login") or "").strip()]
    body = _render_github_avatar_table(with_login, per_row=6)
    if without_login:
        if body:
            body += "\n\n"
        body += _render_markdown_list(without_login)
    updated = f"\n\nLast updated: {dt.date.today().isoformat()}\n"

    content = header + intro + note + body + updated
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
