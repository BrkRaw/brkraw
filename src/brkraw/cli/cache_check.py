"""Cache size warning before a command, with a per-entry [y/N] clean-up (WI-0074).

Before a ``brkraw`` command runs (not ``cache``, ``config`` or ``init``), the
size of the cache folder is compared with ``cache.warn_size_gb`` from the
config (default 10; 0 turns the warning off). Above it, a warning with a table
of the cache entries (one per subfolder, such as ``sordino/``, and one for the
files directly in the folder) goes to stderr. Only when stdin and stderr are
both a terminal, brkraw then asks for each entry, largest first, whether to
delete it; only ``y`` or ``yes`` deletes, any other answer (Enter included)
and end of input keep it. Without a terminal (scripts, CI, pipes) nothing is
asked and nothing is deleted. ``BRKRAW_NO_CACHE_CHECK=1`` skips the check.
The check never changes the command's own result.
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO, Union

from ..core import cache as cache_core
from ..core import config as config_core

ENV_DISABLE = "BRKRAW_NO_CACHE_CHECK"
CONFIG_KEY = "warn_size_gb"
DEFAULT_WARN_SIZE_GB = 10.0
GB = 1024 ** 3
#: Commands that manage the cache or the config themselves: no check before them.
SKIP_COMMANDS = frozenset({"cache", "config", "init"})
YES = frozenset({"y", "yes"})


def format_size(size: Union[int, float]) -> str:
    """``1536`` -> ``"1.50 KB"`` (steps of 1024, as ``brkraw cache info``)."""
    value = float(size)
    unit = "B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            break
        value /= 1024
    return f"{value:.2f} {unit}"


def entry_label(entry: Dict[str, Any]) -> str:
    """``sordino/`` for a subfolder, the group name for the loose files."""
    return f"{entry['name']}/" if entry.get("is_dir") else str(entry["name"])


def _is_shadowed(entry: Dict[str, Any]) -> bool:
    """A real subfolder literally named like the loose-files group: ``clear(only=[name])``
    would clear the loose files instead, so it is never offered (wi-0074-choi-2 finding 1)."""
    return bool(entry.get("is_dir")) and entry.get("name") == cache_core.FILES_ENTRY


def entry_table(entries: List[Dict[str, Any]]) -> List[str]:
    """One aligned line per entry: label, size, file count."""
    if not entries:
        return []
    width = max(len(entry_label(e)) for e in entries)
    return [f"  {entry_label(e):<{width}}  {format_size(e['size']):>10}  {e['count']} files"
            for e in entries]


def warn_size_bytes(root: Optional[Union[str, Path]] = None) -> Optional[int]:
    """The warning size in bytes from ``cache.warn_size_gb``, or None when it is 0 (off).

    A value that is not a number >= 0 is reported and the default is used.
    """
    try:
        section = config_core.resolve_config(root=root).get("cache")
    except Exception:  # an unreadable config must not stop the command
        section = None
    value: Any = DEFAULT_WARN_SIZE_GB
    if isinstance(section, dict) and CONFIG_KEY in section:
        value = section[CONFIG_KEY]
    try:
        gb = float(value)
        if gb < 0 or gb != gb:          # negative or NaN
            raise ValueError
    except (TypeError, ValueError):
        if sys.stderr is not None:
            print(f"warning: config cache.{CONFIG_KEY} must be a number >= 0 (0 turns the check off), "
                  f"not {value!r}; using {DEFAULT_WARN_SIZE_GB:g}.", file=sys.stderr)
        gb = DEFAULT_WARN_SIZE_GB
    if gb == 0 or math.isinf(gb):       # 0 or .inf: never warn (wi-0074-choi-1 F1)
        return None
    return int(gb * GB)


def is_interactive(stdin: Optional[TextIO] = None, stderr: Optional[TextIO] = None) -> bool:
    """True only when stdin and stderr are both a terminal (a person can see and answer)."""
    stdin = sys.stdin if stdin is None else stdin
    stderr = sys.stderr if stderr is None else stderr
    try:
        return bool(stdin.isatty() and stderr.isatty())
    except (AttributeError, ValueError):   # closed or replaced streams
        return False


def ask_yes(question: str, *, stdin: Optional[TextIO] = None, stderr: Optional[TextIO] = None) -> Optional[bool]:
    """Ask on stderr, read one line from stdin: True for y/yes, False otherwise, None at end of input."""
    stdin = sys.stdin if stdin is None else stdin
    stderr = sys.stderr if stderr is None else stderr
    stderr.write(question)
    stderr.flush()
    line = stdin.readline()
    if line == "":
        stderr.write("\n")
        return None
    return line.strip().lower() in YES


def check_cache(
    command: Optional[str],
    *,
    root: Optional[Union[str, Path]] = None,
    stdin: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
    interactive: Optional[bool] = None,
) -> Dict[str, Any]:
    """Warn about a large cache before ``command`` and offer to clear entries.

    Returns what happened: ``checked`` (bool), ``warned`` (bool), ``asked``
    (entry names asked about) and ``cleared`` (entry names deleted). Problems
    measuring or clearing the cache are reported on stderr; other errors (a
    broken stream, for example) can raise, so ``main()`` calls it through
    ``run_check``, which never raises.
    """
    result: Dict[str, Any] = {"checked": False, "warned": False, "asked": [], "cleared": []}
    if command in SKIP_COMMANDS or os.environ.get(ENV_DISABLE, "").strip() not in ("", "0"):
        return result
    stderr = sys.stderr if stderr is None else stderr
    if stderr is None:                  # no place to warn (for example pythonw)
        return result
    limit = warn_size_bytes(root)
    if limit is None:
        return result
    result["checked"] = True
    try:
        info = cache_core.get_info(root=root, by_entry=True)
    except Exception as exc:  # noqa: BLE001 - a warning must not stop the command
        print(f"warning: could not measure the brkraw cache: {exc}", file=stderr)
        return result
    # what clearing can free: the entries (links are not followed), not the total,
    # which also counts files behind a linked folder (wi-0074-choi-1 F2)
    entries = sorted((e for e in info["entries"] if (e["size"] > 0 or e["count"] > 0)
                      and not _is_shadowed(e)),
                     key=lambda e: (-e["size"], e["name"]))
    size = sum(int(e["size"]) for e in entries)
    count = sum(int(e["count"]) for e in entries)
    if size <= limit:
        return result
    result["warned"] = True
    print(f"warning: the brkraw cache holds {format_size(size)} in {count} files, "
          f"more than {format_size(limit)} (cache.{CONFIG_KEY}):", file=stderr)
    print(f"  {info['path']}", file=stderr)
    for line in entry_table(entries):
        print(line, file=stderr)
    if interactive is None:
        interactive = is_interactive(stdin, stderr)
    if not interactive:
        print("  Nothing was deleted. Free space with 'brkraw cache clear --only NAME' "
              f"(or turn this off with cache.{CONFIG_KEY}: 0 or {ENV_DISABLE}=1).", file=stderr)
        return result
    freed = 0
    for entry in entries:
        result["asked"].append(entry["name"])
        answer = ask_yes(f"Clear {entry_label(entry)} ({format_size(entry['size'])}, "
                         f"{entry['count']} files)? [y/N]: ", stdin=stdin, stderr=stderr)
        if answer is None:     # end of input: keep this and every later entry
            break
        if not answer:
            continue
        try:
            cache_core.clear(root=root, only=[entry["name"]])
        except Exception as exc:  # noqa: BLE001
            print(f"warning: could not clear {entry_label(entry)}: {exc}", file=stderr)
            continue
        result["cleared"].append(entry["name"])
        freed += int(entry["size"])
    if result["cleared"]:
        print(f"Cleared {format_size(freed)} ({', '.join(result['cleared'])}).", file=stderr)
    else:
        print("Nothing was deleted.", file=stderr)
    return result


def run_check(command: Optional[str]) -> None:
    """``check_cache`` for ``main()``: any error is swallowed, so the command always runs
    and keeps its own result (wi-0074-choi-1 F1). Nothing is deleted after an error,
    because deleting happens only after a y/yes answer was read."""
    try:
        check_cache(command)
    except Exception:  # noqa: BLE001 - the warning is optional, the command is not
        pass


__all__ = ["check_cache", "run_check", "ask_yes", "is_interactive", "warn_size_bytes", "format_size",
           "entry_table", "SKIP_COMMANDS", "ENV_DISABLE", "DEFAULT_WARN_SIZE_GB"]
