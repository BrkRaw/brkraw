"""Approved anonymized PvDatasets for the manual checks in ``scripts/validate/``.

The folder lives next to the repository checkout (``<checkout>/../agent-fixtures``)
and is not part of any Git repository. Its README holds a provenance table;
only rows whose last cell is exactly ``승인`` and whose zip SHA-256 matches
are used. Set ``BRKRAW_AGENT_FIXTURES`` to use another folder. The automatic
test suite in ``tests/`` never reads this folder; only the manual checks do
(``check_agent_fixtures.py``), and they stop with a message when it is missing.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

ENV_AGENT_FIXTURES = "BRKRAW_AGENT_FIXTURES"
REPO_ROOT = Path(__file__).resolve().parents[2]

_PATH = re.compile(r"`([^`]+)`")
_SHA = re.compile(r"sha256\s+`([0-9a-fA-F]{64})`")


def parse_fixture_readme(text: str) -> List[Dict[str, Union[str, bool, None]]]:
    """Return one ``{path, sha256, approved}`` dict per file row of the table.

    A file row is a line that starts with a pipe, a space and a backquote.
    ``path`` is the first backquoted text of the first cell, ``sha256`` the
    zip hash written as ``sha256 `<64 hex>``` in the first cell (lowercase,
    or None), ``approved`` is True only when the last cell is exactly ``승인``.
    """
    rows: List[Dict[str, Union[str, bool, None]]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("| `"):
            continue
        content = stripped[1:]
        if content.endswith("|"):
            content = content[:-1]
        cells = content.split("|")
        first = cells[0]
        path_match = _PATH.search(first)
        if not path_match:
            continue
        sha_match = _SHA.search(first)
        rows.append(
            {
                "path": path_match.group(1),
                "sha256": sha_match.group(1).lower() if sha_match else None,
                "approved": cells[-1].strip() == "승인",
            }
        )
    return rows


def fixtures_dir() -> Path:
    """The agent-fixtures folder: ``BRKRAW_AGENT_FIXTURES`` or ``<checkout>/../agent-fixtures``."""
    override = os.environ.get(ENV_AGENT_FIXTURES)
    if override:
        return Path(override)
    return REPO_ROOT.parent / "agent-fixtures"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def find_approved_zips(folder: Optional[Path], pv: str) -> Tuple[List[Path], List[str]]:
    """Approved zips for one ParaVision folder (``pv`` like ``"pv5.1"``) and reasons for the rest."""
    folder = Path(folder) if folder is not None else fixtures_dir()
    if not folder.is_dir():
        return [], [f"agent fixtures folder not found: {folder}"]
    readme = folder / "README.md"
    if not readme.is_file():
        return [], [f"no README.md in {folder}"]
    found: List[Path] = []
    reasons: List[str] = []
    prefix = pv.rstrip("/") + "/"
    for row in parse_fixture_readme(readme.read_text(encoding="utf-8")):
        rel = str(row["path"])
        if not rel.startswith(prefix):
            continue
        if not row["approved"]:
            reasons.append(f"{rel}: not approved")
            continue
        zip_path = folder / rel
        if not zip_path.is_file():
            reasons.append(f"{rel}: file missing")
            continue
        if not row["sha256"] or _sha256(zip_path) != row["sha256"]:
            reasons.append(f"{rel}: SHA-256 does not match the README")
            continue
        found.append(zip_path)
    if not found and not reasons:
        reasons.append(f"no rows for {pv} in {readme}")
    return found, reasons
