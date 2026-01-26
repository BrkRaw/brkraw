"""Formatting helpers for CLI-style output.

Last updated: 2025-12-30
"""

from __future__ import annotations

import itertools
import logging
import threading
import time
from contextlib import contextmanager
from typing import Iterator, List

from brkraw.apps.loader import BrukerLoader

logger = logging.getLogger(__name__)

@contextmanager
def spinner(prefix: str = "Loading") -> Iterator[None]:
    """Display a simple CLI spinner while a block runs.

    Args:
        prefix: Text shown before the spinner glyph.

    Yields:
        None.
    """
    if logger.isEnabledFor(logging.DEBUG):
        yield
        return

    stop_event = threading.Event()
    seq = itertools.cycle("|/-\\")

    def run() -> None:
        while not stop_event.is_set():
            print(f"\r{prefix} {next(seq)}", end="", flush=True)
            time.sleep(0.08)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join()
        print("\r" + " " * (len(prefix) + 2) + "\r", end="", flush=True)


def load(path, *, prefix: str = "Loading") -> BrukerLoader:
    """Load a Bruker dataset with a CLI spinner."""
    with spinner(prefix):
        return BrukerLoader(path)


__all__ = ["spinner", "load"]

def __dir__() -> List[str]:
    return sorted(__all__)
