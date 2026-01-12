#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_PATH = REPO_ROOT / "src" / "brkraw" / "__init__.py"
README_PATH = REPO_ROOT / "README.md"
RELEASE_NOTES_PATH = REPO_ROOT / "RELEASE_NOTES.md"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
RELEASE_PREP_SCRIPT = REPO_ROOT / "scripts" / "release_prep.py"


def run_git(args: Iterable[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        raise SystemExit(f"git {' '.join(args)} failed: {msg}")
    return result


def run_cmd(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        raise SystemExit(f"{args[0]} failed: {msg}")
    return result


def require_clean_worktree() -> None:
    status = run_git(["status", "--porcelain"], check=True).stdout.strip()
    if status:
        raise SystemExit("Working tree is not clean. Commit or stash changes first.")


def get_current_branch() -> str:
    return run_git(["rev-parse", "--abbrev-ref", "HEAD"], check=True).stdout.strip()


def get_remote_url(remote: str) -> str:
    return run_git(["remote", "get-url", remote], check=True).stdout.strip()


def parse_owner_repo(remote_url: str) -> tuple[str, str]:
    cleaned = remote_url.rstrip("/")
    match = re.search(r"[:/](?P<owner>[^/]+)/(?P<repo>[^/]+)$", cleaned)
    if not match:
        raise SystemExit(f"Could not parse owner/repo from remote URL: {remote_url}")
    repo = match.group("repo")
    if repo.endswith(".git"):
        repo = repo[: -len(".git")]
    return match.group("owner"), repo


def ensure_remote_branch(remote: str, branch: str) -> None:
    head = run_git(["ls-remote", "--heads", remote, branch], check=True).stdout.strip()
    if not head:
        run_git(["push", "-u", remote, f"HEAD:{branch}"], check=True)


def gh_pr_exists(upstream_repo: str, head_ref: str) -> bool:
    result = run_cmd(
        ["gh", "pr", "view", "--repo", upstream_repo, "--head", head_ref, "--json", "number"],
        check=False,
    )
    return result.returncode == 0


def gh_pr_create(
    upstream_repo: str, base_branch: str, head_ref: str, title: str, body: str
) -> None:
    args = [
        "gh",
        "pr",
        "create",
        "--repo",
        upstream_repo,
        "--base",
        base_branch,
        "--head",
        head_ref,
        "--title",
        title,
        "--body",
        body,
    ]
    run_cmd(args)


def run_release_prep(version: str, remote: str) -> None:
    run_cmd(
        [
            str(Path(__file__).resolve().parent / ".." / ".venv" / "bin" / "python"),
            str(RELEASE_PREP_SCRIPT),
            "--version",
            version,
            "--fetch-tags",
            "--remote",
            remote,
        ]
    )


def commit_files(message: str, files: Iterable[Path]) -> None:
    for path in files:
        run_git(["add", str(path.relative_to(REPO_ROOT))], check=True)
    run_git(["commit", "-m", message], check=True)


def generate_release_notes(version: str, upstream_ref: str) -> None:
    tag_result = run_git(["describe", "--tags", "--abbrev=0", upstream_ref], check=False)
    last_tag = tag_result.stdout.strip() if tag_result.returncode == 0 else None
    log_range = f"{last_tag}..HEAD" if last_tag else "HEAD"

    log_result = run_git(
        ["log", log_range, "--no-merges", "--pretty=format:- %s (%h)"], check=True
    )
    changes = log_result.stdout.strip() or "- (no changes found)"

    date_str = dt.date.today().isoformat()
    header = f"# Release v{version}\n\n"
    meta = f"Date: {date_str}\n"
    scope = f"Changes since {last_tag}\n\n" if last_tag else "Changes\n\n"
    RELEASE_NOTES_PATH.write_text(header + meta + scope + changes + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a release prep PR and commit version + release notes changes."
    )
    parser.add_argument("--version", required=True, help="Release version (PEP 440)")
    parser.add_argument("--base", default="upstream/main", help="Base ref for PR (default: upstream/main)")
    parser.add_argument(
        "--remote-upstream",
        default="upstream",
        help="Remote name for upstream (default: upstream)",
    )
    parser.add_argument(
        "--remote-origin",
        default="origin",
        help="Remote name for fork/origin (default: origin)",
    )
    parser.add_argument("--pr-title", default=None, help="PR title (default: Release vX.Y.Z)")
    parser.add_argument(
        "--pr-body",
        default=None,
        help="PR body (default: Release prep for vX.Y.Z)",
    )
    parser.add_argument(
        "--prep-message",
        default="chore: prepare release v{version}",
        help="Commit message for version bump (default: chore: prepare release v{version})",
    )
    parser.add_argument(
        "--notes-message",
        default="docs: release notes for v{version}",
        help="Commit message for release notes (default: docs: release notes for v{version})",
    )
    args = parser.parse_args()

    require_clean_worktree()

    branch = get_current_branch()
    upstream_owner, upstream_repo = parse_owner_repo(get_remote_url(args.remote_upstream))
    origin_owner, _ = parse_owner_repo(get_remote_url(args.remote_origin))

    base_branch = args.base.split("/", 1)[1] if "/" in args.base else args.base
    upstream_repo_full = f"{upstream_owner}/{upstream_repo}"
    head_ref = f"{origin_owner}:{branch}"

    ensure_remote_branch(args.remote_origin, branch)

    if not gh_pr_exists(upstream_repo_full, head_ref):
        title = args.pr_title or f"Release v{args.version}"
        body = args.pr_body or f"Release prep for v{args.version}."
        gh_pr_create(upstream_repo_full, base_branch, head_ref, title, body)

    run_release_prep(args.version, args.remote_upstream)

    prep_message = args.prep_message.format(version=args.version)
    commit_files(prep_message, [INIT_PATH, README_PATH, PYPROJECT_PATH])

    generate_release_notes(args.version, args.base)

    notes_message = args.notes_message.format(version=args.version)
    commit_files(notes_message, [RELEASE_NOTES_PATH])

    run_git(["push", args.remote_origin, f"HEAD:{branch}"], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
