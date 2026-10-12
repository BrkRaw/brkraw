"""Formatting helpers for CLI-style output.

Last updated: 2025-12-30
"""

from __future__ import annotations

import itertools
import logging
import sys
import threading
import time
from contextlib import contextmanager
from typing import Iterator, List, Sequence

from brkraw.apps.loader import BrukerLoader

logger = logging.getLogger(__name__)

ROOT_HELP = "Config folder to use (default: BRKRAW_CONFIG_HOME, else ~/.brkraw)."


def add_root_argument(parser) -> None:
    """Add the common ``--root DIR`` option (config folder) to a command parser.

    brkraw's own commands all use it; plugin commands can call this so
    ``--root`` means the same everywhere. ``brkraw`` applies it for the whole
    run (it wins over ``BRKRAW_CONFIG_HOME``).
    """
    parser.add_argument("--root", default=None, metavar="DIR", help=ROOT_HELP)


def parse_scan_ids(values: Sequence[str]) -> List[int]:
    """Read scan ids given on the command line or in a session variable.

    One rule for every command: each string may hold several ids separated by
    commas (``-s 3 4``, ``-s 3,4``, ``BRKRAW_SCAN_ID="3, 4"``). Empty pieces
    are skipped, repeats are dropped (first order kept), and every piece must
    be plain ASCII digits.

    Raises:
        ValueError: A piece is not a plain number, or no id was given.
    """
    collected: List[int] = []
    seen = set()
    for text in values:
        for piece in text.split(","):
            stripped = piece.strip()
            if not stripped:
                continue
            if not (stripped.isascii() and stripped.isdecimal()):
                raise ValueError("invalid scan id: %r" % stripped)
            value = int(stripped)
            if value not in seen:
                collected.append(value)
                seen.add(value)
    if not collected:
        raise ValueError("no scan id given")
    return collected


@contextmanager
def spinner(prefix: str = "Loading") -> Iterator[None]:
    """Display a simple CLI spinner while a block runs.

    Args:
        prefix: Text shown before the spinner glyph.

    Yields:
        None.
    """
    if logger.isEnabledFor(logging.DEBUG) or not sys.stdout.isatty():
        yield
        return

    stop_event = threading.Event()
    seq = itertools.cycle("|/-\\")

    def run() -> None:
        while not stop_event.is_set():
            try:
                print(f"\r{prefix} {next(seq)}", end="", flush=True)
            except BrokenPipeError:
                stop_event.set()
                break
            time.sleep(0.08)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join()
        try:
            print("\r" + " " * (len(prefix) + 2) + "\r", end="", flush=True)
        except BrokenPipeError:
            pass


def load(path, *, prefix: str = "Loading") -> BrukerLoader:
    """Load a Bruker dataset with a CLI spinner."""
    with spinner(prefix):
        return BrukerLoader(path)


__all__ = ["spinner", "load", "add_root_argument", "parse_scan_ids"]

def __dir__() -> List[str]:
    return sorted(__all__)
