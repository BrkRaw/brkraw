from __future__ import annotations

import os
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Union, Sequence

from . import config

logger = logging.getLogger("brkraw.cache")

#: Name of the one entry that groups the files (and links) lying directly in the
#: cache folder, next to its subfolders (WI-0074).
FILES_ENTRY = "(files)"


def get_info(
    root: Optional[Union[str, Path]] = None,
    path: Optional[Union[str, Path]] = None,
    *,
    by_entry: bool = False,
) -> Dict[str, Any]:
    """
    Get information about the current cache directory.

    Args:
        root: Configuration root directory (used to resolve default cache path).
        path: Explicit path to the cache directory. If provided, overrides 'root'.
        by_entry: If True, include detailed information for each cache entry:
            each real subfolder, and ``FILES_ENTRY`` for the other items directly in
            the folder. Entry sizes do not follow links (what clearing frees), so
            their sum can be below ``size`` when the cache holds a link to a folder.

    Returns:
        Dict with keys:
            - path: Path to cache directory
            - size: Total size in bytes
            - count: Number of files
            - entries: (if by_entry=True) List of dicts for each entry
    """
    if path is not None:
        cache_path = Path(path)
    else:
        cache_path = config.cache_dir(root)

    if not cache_path.exists():
        res = {"path": cache_path, "size": 0, "count": 0}
        if by_entry:
            res["entries"] = []
        return res

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
            except OSError:
                continue
    
    res = {
        "path": cache_path,
        "size": total_size,
        "count": file_count
    }

    if by_entry:
        entries = []
        files_entry_data = {"name": FILES_ENTRY, "path": cache_path, "is_dir": False, "size": 0, "count": 0}
        has_files_entry = False

        for item in sorted(cache_path.iterdir(), key=lambda p: p.name):
            try:
                if item.is_dir() and not item.is_symlink():
                    item_size = 0
                    item_count = 0
                    # links are not followed: an entry's size is what clearing it frees
                    # (rmtree removes a link, not its target); the total above still
                    # follows folder links as before (wi-0074-choi-1 F2)
                    for dirpath, _, filenames in os.walk(str(item), followlinks=False):
                        for f in filenames:
                            try:
                                fp = Path(dirpath) / f
                                if fp.is_symlink():
                                    continue
                                item_size += fp.stat().st_size
                                item_count += 1
                            except OSError:
                                continue
                    entries.append({
                        "name": item.name,
                        "path": item,
                        "is_dir": True,
                        "size": item_size,
                        "count": item_count
                    })
                else:
                    has_files_entry = True
                    # like the total: a link adds nothing (clearing removes only the link)
                    if item.is_file() and not item.is_symlink():
                        files_entry_data["size"] += item.stat().st_size
                        files_entry_data["count"] += 1
            except OSError:
                if not (item.is_dir() and not item.is_symlink()):
                    has_files_entry = True
        
        if has_files_entry:
            entries.append(files_entry_data)
        res["entries"] = entries

    return res


def clear(
    root: Optional[Union[str, Path]] = None,
    path: Optional[Union[str, Path]] = None,
    *,
    only: Optional[Sequence[str]] = None,
) -> None:
    """
    Clear all files in the cache directory.

    Args:
        root: Configuration root directory (used to resolve default cache path).
        path: Explicit path to the cache directory. If provided, overrides 'root'.
        only: Optional list of entry names (subfolders or FILES_ENTRY) to delete.
              Invalid or unknown names raise ValueError before any deletion.
    """
    if path is not None:
        cache_path = Path(path)
    else:
        cache_path = config.cache_dir(root)

    if not cache_path.exists():
        return

    if only is None:
        logger.info("Clearing cache at: %s", cache_path)
        for item in cache_path.iterdir():
            try:
                if item.is_file() or item.is_symlink():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            except Exception as exc:
                logger.warning("Failed to remove %s: %s", item, exc)
    else:
        for name in only:
            if not name or name in (".", "..") or "/" in name or os.sep in name:
                raise ValueError(f"not a cache entry name: {name!r}")
            if os.altsep and os.altsep in name:
                raise ValueError(f"not a cache entry name: {name!r}")
            
            if name == FILES_ENTRY:
                pass
            else:
                target = cache_path / name
                if not (target.is_dir() and not target.is_symlink()):
                    raise ValueError(f"no cache entry {name!r} in {cache_path}")
        
        logger.info("Clearing cache entries %s at: %s", list(only), cache_path)
        for name in only:
            try:
                if name == FILES_ENTRY:
                    for item in cache_path.iterdir():
                        if not (item.is_dir() and not item.is_symlink()):
                            try:
                                item.unlink()
                            except Exception as exc:
                                logger.warning("Failed to remove %s: %s", item, exc)
                else:
                    shutil.rmtree(cache_path / name)
            except Exception as exc:
                if name != FILES_ENTRY:
                    logger.warning("Failed to remove %s: %s", cache_path / name, exc)
