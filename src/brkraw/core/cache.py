from __future__ import annotations

import os
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Union

from . import config

logger = logging.getLogger("brkraw.cache")


def get_info(
    root: Optional[Union[str, Path]] = None,
    path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Get information about the current cache directory.

    Args:
        root: Configuration root directory (used to resolve default cache path).
        path: Explicit path to the cache directory. If provided, overrides 'root'.

    Returns:
        Dict with keys:
            - path: Path to cache directory
            - size: Total size in bytes
            - count: Number of files
    """
    if path is not None:
        cache_path = Path(path)
    else:
        cache_path = config.cache_dir(root)

    if not cache_path.exists():
        return {"path": cache_path, "size": 0, "count": 0}

    total_size = 0
    file_count = 0
    
    for dirpath, _, filenames in os.walk(str(cache_path), followlinks=True):
        for f in filenames:
            try:
                fp = Path(dirpath) / f
                if fp.is_symlink():
                    continue
                total_size += fp.stat().st_size
                file_count += 1
            except OSError as e:
                continue
    
    return {
        "path": cache_path,
        "size": total_size,
        "count": file_count
    }


def clear(
    root: Optional[Union[str, Path]] = None,
    path: Optional[Union[str, Path]] = None,
) -> None:
    """
    Clear all files in the cache directory.

    Args:
        root: Configuration root directory (used to resolve default cache path).
        path: Explicit path to the cache directory. If provided, overrides 'root'.
    """
    if path is not None:
        cache_path = Path(path)
    else:
        cache_path = config.cache_dir(root)

    if not cache_path.exists():
        return

    logger.info("Clearing cache at: %s", cache_path)
    for item in cache_path.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception as exc:
            logger.warning("Failed to remove %s: %s", item, exc)
