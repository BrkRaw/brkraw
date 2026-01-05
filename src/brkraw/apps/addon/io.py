"""Addon IO helpers."""

from __future__ import annotations

from pathlib import Path


def write_file(target: Path, content: str) -> None:
    """Write text content to a target path.

    Args:
        target: Output file path.
        content: Text content to write.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


__all__ = [
    "write_file",
]
