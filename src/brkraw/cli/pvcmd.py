"""Pick the study open in ParaVision when a command needs a path and got none.

On a scanner console, ``pvcmd`` lists the datasets open in ParaVision. brkraw
asks it only when a command that works on a dataset was given no path and no
``BRKRAW_PATH`` is set (never for ``-h``/``--version`` or commands without a
dataset path). With one open dataset it is used and announced; with several,
a terminal user picks one by number, and a run without a terminal (script,
pipe, scheduled job) prints one warning and picks nothing. A missing ``pvcmd``,
a stopped ParaVision or no open dataset never stops the command.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_PS_PATH = re.compile(r"^(?P<path>.+)/(?P<scan_id>\d+)/pdata/(?P<reco_id>\d+)$")


def parse_ps_entries(text: str) -> List[Dict[str, str]]:
    """Return ``{path, scan_id, reco_id}`` for each ``REQUEST_ATTR`` line, in order, without duplicates."""
    results: List[Dict[str, str]] = []
    for line in text.splitlines():
        if "REQUEST_ATTR" not in line:
            continue
        for field in line.split(";"):
            match = _PS_PATH.match(field.strip())
            if match:
                entry = {
                    "path": match.group("path"),
                    "scan_id": match.group("scan_id"),
                    "reco_id": match.group("reco_id"),
                }
                if entry not in results:
                    results.append(entry)
                break
    return results


def choose_entry(
    entries: List[Dict[str, str]],
    *,
    interactive: bool,
    ask: Callable[[str], str],
    tell: Callable[[str], None],
) -> Optional[Dict[str, str]]:
    """Pick one entry: none -> None; one -> it; several -> ask (terminal) or warn (no terminal)."""
    n = len(entries)
    if n == 0:
        return None
    if n == 1:
        e = entries[0]
        tell("Using the study open in ParaVision: %s (scan %s, reco %s)" % (e["path"], e["scan_id"], e["reco_id"]))
        return e
    if not interactive:
        tell('%d ParaVision datasets are open; pass a path or use "brkraw session".' % n)
        return None
    tell("ParaVision has %d open datasets:" % n)
    for i, e in enumerate(entries, 1):
        tell("  %d) %s   scan %s, reco %s" % (i, e["path"], e["scan_id"], e["reco_id"]))
    prompt = "Choose 1-%d, or press Enter to skip: " % n
    for _ in range(3):
        try:
            answer = ask(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if not answer:
            return None
        if answer.isdecimal() and 1 <= int(answer) <= n:
            return entries[int(answer) - 1]
    return None


def query_ps_text() -> Optional[str]:
    """Return ``pvcmd`` ListPs output, or None when pvcmd or ParaVision is not available."""
    if shutil.which("pvcmd") is None:
        return None
    try:
        probe = subprocess.run(
            ["pvcmd", "-e", "ParxServer"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10
        )
        if probe.returncode != 0:
            return None
        listing = subprocess.run(
            ["pvcmd", "-a", "ParxServer", "-r", "ListPs", "-csv"],
            check=True,
            text=True,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("pvcmd query failed: %s", exc)
        return None
    return listing.stdout


def is_interactive() -> bool:
    """True when both stdin and stderr are terminals (a person can answer)."""
    try:
        return sys.stdin.isatty() and sys.stderr.isatty()
    except (AttributeError, ValueError):
        return False


def _ask(prompt: str) -> str:
    sys.stderr.write(prompt)
    sys.stderr.flush()
    return input()


def _tell(message: str) -> None:
    print(message, file=sys.stderr)


def autoset_path_from_paravision(args) -> None:
    """Set ``BRKRAW_PATH`` (and scan/reco defaults not set yet) from ParaVision when needed.

    Applies only to commands whose ``path`` argument exists and is empty,
    not to ``convert --batch``, and only when ``BRKRAW_PATH`` is not set.
    """
    if not hasattr(args, "path") or args.path is not None:
        return
    if getattr(args, "batch", False):
        return
    if os.environ.get("BRKRAW_PATH"):
        return
    text = query_ps_text()
    if not text:
        return
    entry = choose_entry(parse_ps_entries(text), interactive=is_interactive(), ask=_ask, tell=_tell)
    if entry is None:
        return
    os.environ["BRKRAW_PATH"] = entry["path"]
    os.environ.setdefault("BRKRAW_SCAN_ID", entry["scan_id"])
    os.environ.setdefault("BRKRAW_RECO_ID", entry["reco_id"])


__all__ = ["parse_ps_entries", "choose_entry", "query_ps_text", "is_interactive", "autoset_path_from_paravision"]
