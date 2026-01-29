#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Iterable, Literal


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_PATH = REPO_ROOT / "src" / "brkraw" / "__init__.py"
README_PATH = REPO_ROOT / "README.md"
RELEASE_NOTES_PATH = REPO_ROOT / "RELEASE_NOTES.md"
CITATION_PATH = REPO_ROOT / "CITATION.cff"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
CONTRIBUTORS_PATH = REPO_ROOT / "docs" / "dev" / "contributors.md"
RELEASE_PREP_SCRIPT = REPO_ROOT / "scripts" / "release_prep.py"
UPDATE_CONTRIBUTORS_SCRIPT = REPO_ROOT / "scripts" / "update_contributors.py"
UPDATE_README_BIBTEX_SCRIPT = REPO_ROOT / "scripts" / "update_readme_bibtex.py"

logger = logging.getLogger(__name__)


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


def ensure_remote_branch(remote: str, branch: str, *, dry_run: bool) -> None:
    if dry_run:
        logger.info("[dry-run] Would ensure remote branch exists: %s/%s", remote, branch)
        return
    head = run_git(["ls-remote", "--heads", remote, branch], check=True).stdout.strip()
    if not head:
        run_git(["push", "-u", remote, f"HEAD:{branch}"], check=True)


def has_changes(paths: Iterable[Path]) -> bool:
    for path in paths:
        rel = str(path.relative_to(REPO_ROOT))
        diff = run_git(["diff", "--name-only", rel], check=True).stdout.strip()
        if diff:
            return True
    return False


def list_changed(paths: Iterable[Path]) -> list[str]:
    changed: list[str] = []
    for path in paths:
        rel = str(path.relative_to(REPO_ROOT))
        diff = run_git(["diff", "--name-only", rel], check=True).stdout.strip()
        if diff:
            changed.append(rel)
    return changed


def commit_if_changed(
    message: str,
    paths: Iterable[Path],
    *,
    label: str,
    dry_run: bool,
) -> bool:
    if not has_changes(paths):
        logger.info("No %s changes detected; skipping commit.", label)
        return False

    changed = list_changed(paths)
    if dry_run:
        logger.info("[dry-run] Would commit (%s): %s", label, message)
        for p in changed:
            logger.info("[dry-run]   - %s", p)
        return True

    for path in paths:
        run_git(["add", str(path.relative_to(REPO_ROOT))], check=True)
    run_git(["commit", "-m", message], check=True)
    return True


def gh_pr_number(upstream_repo: str, head_ref: str, state: Literal['open', 'closed', 'all']='open') -> str | None:
    owner, repo = upstream_repo.split("/", 1)
    result = run_cmd(
        [
            "gh",
            "api",
            f"repos/{owner}/{repo}/pulls",
            "-X",
            "GET",
            "-f",
            f"head={head_ref}",
            "-f",
            f"state={state}",
            "--jq",
            ".[0].number",
        ],
        check=False,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def gh_pr_create(
    upstream_repo: str, base_branch: str, head_ref: str, title: str, body: str, *, dry_run: bool
) -> str | None:
    if dry_run:
        logger.info(
            "[dry-run] Would create PR in %s: base=%s, head=%s",
            upstream_repo,
            base_branch,
            head_ref,
        )
        logger.info("[dry-run] Title: %s", title)
        return None
    owner, repo = upstream_repo.split("/", 1)
    result = run_cmd(
        [
            "gh",
            "api",
            f"repos/{owner}/{repo}/pulls",
            "-X",
            "POST",
            "-f",
            f"title={title}",
            "-f",
            f"head={head_ref}",
            "-f",
            f"base={base_branch}",
            "-f",
            f"body={body}",
            "--jq",
            ".number",
        ]
    )
    value = result.stdout.strip()
    return value or None


def gh_pr_edit(upstream_repo: str, pr_number: str, body: str, *, dry_run: bool) -> None:
    if dry_run:
        logger.info(
            "[dry-run] Would edit PR #%s in %s (update body)",
            pr_number,
            upstream_repo,
        )
        return
    owner, repo = upstream_repo.split("/", 1)
    run_cmd(
        [
            "gh",
            "api",
            f"repos/{owner}/{repo}/pulls/{pr_number}",
            "-X",
            "PATCH",
            "-f",
            f"body={body}",
        ]
    )


def gh_pr_add_label(upstream_repo: str, pr_number: str, label: str, *, dry_run: bool) -> None:
    if dry_run:
        logger.info(
            "[dry-run] Would add label '%s' to PR #%s in %s",
            label,
            pr_number,
            upstream_repo,
        )
        return
    owner, repo = upstream_repo.split("/", 1)
    run_cmd(
        [
            "gh",
            "api",
            f"repos/{owner}/{repo}/issues/{pr_number}/labels",
            "-X",
            "POST",
            "-f",
            f"labels[]={label}",
        ]
    )


def gh_closed_pr_has_label(
    upstream_repo: str,
    *,
    label: str,
    mode: str,
) -> tuple[bool | None, str | None]:
    owner, repo = upstream_repo.split("/", 1)
    if mode == "closed-release":
        jq = (
            '[.[] | select(.title | test("Release v"; "i"))][0]'
            ' | (.labels // []) | map(.name) | index("' + label + '")'
        )
    else:
        jq = '.[0] | (.labels // []) | map(.name) | index("' + label + '")'
    result = run_cmd(
        [
            "gh",
            "api",
            f"repos/{owner}/{repo}/pulls",
            "-X",
            "GET",
            "-f",
            "state=closed",
            "-f",
            "per_page=30",
            "--jq",
            jq,
        ],
        check=False,
    )
    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip()
        return None, err or None
    return result.stdout.strip() != "null", None


def ensure_pr(
    *,
    upstream_repo_full: str,
    base_branch: str,
    head_ref: str,
    title: str,
    body: str,
    no_pr: bool,
    dry_run: bool,
) -> str | None:
    if no_pr:
        logger.info("[no-pr] PR operations disabled; skipping PR lookup/create.")
        return None

    pr_number = gh_pr_number(upstream_repo_full, head_ref, state="open")
    if pr_number:
        logger.info(
            "Existing PR found for %s (head=%s): #%s",
            upstream_repo_full,
            head_ref,
            pr_number,
        )
        return pr_number

    created_pr = gh_pr_create(
        upstream_repo_full, base_branch, head_ref, title, body, dry_run=dry_run
    )
    if dry_run:
        return "DRY_RUN_PR"
    if created_pr:
        return created_pr

    pr_number = None
    for attempt in range(5):
        pr_number = gh_pr_number(upstream_repo_full, head_ref, state="open")
        if pr_number:
            break
        if attempt < 4:
            logger.info("Waiting for PR to become visible (%s/5)...", attempt + 1)
            time.sleep(3)
    if not pr_number:
        raise SystemExit("PR created but could not retrieve PR number.")
    else:
        logger.info("Created PR #%s", pr_number)
    return pr_number


def is_prerelease(version: str) -> bool:
    result = bool(re.search(r"(a|b|rc)\d*$", version.lower()))
    logger.info("Is prerelease: %s", result)
    return result


def get_changed_files(base_ref: str) -> list[str]:
    base_ref = base_ref.strip()
    merge_base = run_git(["merge-base", base_ref, "HEAD"], check=False)
    if merge_base.returncode == 0:
        base_sha = merge_base.stdout.strip()
        diff_result = run_git(["diff", "--name-only", f"{base_sha}..HEAD"], check=True)
    else:
        diff_result = run_git(["diff", "--name-only", f"{base_ref}..HEAD"], check=False)
        if diff_result.returncode != 0:
            diff_result = run_git(["diff", "--name-only", "HEAD~3..HEAD"], check=True)
    changed_files = [line.strip() for line in diff_result.stdout.splitlines() if line.strip()]
    logger.debug("Changed files: %s", changed_files)
    return changed_files


def run_release_prep(version: str, remote: str) -> None:
    logger.debug("> Running release_prep.py")
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


def run_update_readme_bibtex() -> None:
    logger.debug("> Running update_readme_bibtex.py")
    run_cmd(
        [
            str(Path(__file__).resolve().parent / ".." / ".venv" / "bin" / "python"),
            str(UPDATE_README_BIBTEX_SCRIPT),
        ]
    )


def run_update_contributors(repo: str) -> None:
    logger.debug("> Running update_contributors.py")
    run_cmd(
        [
            str(Path(__file__).resolve().parent / ".." / ".venv" / "bin" / "python"),
            str(UPDATE_CONTRIBUTORS_SCRIPT),
            "--source",
            "github",
            "--repo",
            repo,
            "--output",
            str(CONTRIBUTORS_PATH),
        ]
    )


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


def build_pr_body(version: str, files_block: str) -> str:
    return (
        f"## Release v{version}\n\n"
        "### Summary\n"
        "- Bump package version and metadata\n"
        "- Refresh contributors list\n"
        "- Generate release notes\n\n"
        "### Files updated\n"
        f"{files_block}\n\n"
        "### Checklist\n"
        "- [ ] CI passes\n"
        "- [ ] Release notes look correct\n"
        "- [ ] `release` label applied\n"
        "- [ ] Tag on merge\n"
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(
        description="Create a release prep PR and commit version + release notes changes."
    )
    parser.add_argument("--version", required=True, help="Release version (PEP 440)")
    parser.add_argument("--base", default="upstream/main", help="Base ref for PR (default: upstream/main)")
    parser.add_argument("--remote-upstream", default="upstream", help="Remote name for upstream (default: upstream)")
    parser.add_argument("--remote-origin", default="origin", help="Remote name for fork/origin (default: origin)")
    parser.add_argument("--pr-title", default=None, help="PR title (default: Release vX.Y.Z)")
    parser.add_argument("--pr-body", default=None, help="PR body (default: formatted release prep template)")
    parser.add_argument("--prep-message", default="chore: prepare release v{version}", help="Commit message for version bump")
    parser.add_argument("--notes-message", default="docs: release notes for v{version}", help="Commit message for release notes")

    parser.add_argument(
        "--no-pr",
        action="store_true",
        help="Do not create or update a GitHub PR (commits/push still run).",
    )
    parser.add_argument(
        "--label-check",
        choices=["closed-latest", "closed-release"],
        default=None,
        help=(
            "In --dry-run mode, check labels on a closed PR "
            "(latest or latest release PR)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without committing, pushing, or creating/editing PRs.",
    )

    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow running with a dirty working tree (useful with --dry-run).",
    )

    args = parser.parse_args()

    if not args.allow_dirty and not args.dry_run:
        require_clean_worktree()
    else:
        logger.warning("⚠️  Dirty working tree allowed (dry-run or --allow-dirty).")

    branch = get_current_branch()
    upstream_owner, upstream_repo = parse_owner_repo(get_remote_url(args.remote_upstream))
    origin_owner, _ = parse_owner_repo(get_remote_url(args.remote_origin))

    base_branch = args.base.split("/", 1)[1] if "/" in args.base else args.base
    upstream_repo_full = f"{upstream_owner}/{upstream_repo}"
    head_ref = f"{origin_owner}:{branch}"

    ensure_remote_branch(args.remote_origin, branch, dry_run=args.dry_run)

    title = args.pr_title or f"Release v{args.version}"
    initial_body = args.pr_body or build_pr_body(args.version, "- (pending)")

    # 1) contributors
    run_update_contributors(upstream_repo_full)
    commit_if_changed(
        "docs: update contributors",
        [CONTRIBUTORS_PATH],
        label="contributor",
        dry_run=args.dry_run,
    )

    # 2) release prep changes
    run_release_prep(args.version, args.remote_upstream)
    run_update_readme_bibtex()
    release_prep_group = [INIT_PATH, README_PATH, PYPROJECT_PATH, CITATION_PATH]
    commit_if_changed(
        args.prep_message.format(version=args.version),
        release_prep_group,
        label="release prep",
        dry_run=args.dry_run,
    )

    # 3) release notes
    generate_release_notes(args.version, args.base)
    commit_if_changed(
        args.notes_message.format(version=args.version),
        [RELEASE_NOTES_PATH],
        label="release notes",
        dry_run=args.dry_run,
    )

    # push early (unless dry-run)
    # Rationale: ensure commits are on the PR branch even if later GitHub API steps fail.
    if not args.dry_run:
        run_git(["push", args.remote_origin, f"HEAD:{branch}"], check=True)

    pr_number = ensure_pr(
        upstream_repo_full=upstream_repo_full,
        base_branch=base_branch,
        head_ref=head_ref,
        title=title,
        body=initial_body,
        no_pr=args.no_pr,
        dry_run=args.dry_run,
    )

    # PR body update + label (if enabled)
    if pr_number and (not args.no_pr):
        changed_files = get_changed_files(args.base)
        files_block = "\n".join(f"- `{p}`" for p in changed_files) if changed_files else "- (none)"
        final_body = args.pr_body or build_pr_body(args.version, files_block)
        gh_pr_edit(upstream_repo_full, pr_number, final_body, dry_run=args.dry_run)

        if (not is_prerelease(args.version)) and (not args.dry_run):
            gh_pr_add_label(upstream_repo_full, pr_number, "release", dry_run=args.dry_run)
    elif args.dry_run and args.label_check and (not is_prerelease(args.version)):
        has_label, label_err = gh_closed_pr_has_label(
            upstream_repo_full,
            label="release",
            mode=args.label_check,
        )
        if has_label is None:
            if label_err:
                logger.warning("Label check failed (gh api error): %s", label_err)
            else:
                logger.warning("Label check failed (gh api error).")
        elif has_label:
            logger.info("Label check passed: closed PR contains label 'release'.")
        else:
            logger.warning("Label check: closed PR does not contain label 'release'.")

    # push (dry-run message only)
    if args.dry_run:
        logger.info("[dry-run] Would push branch to %s: %s", args.remote_origin, branch)
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
