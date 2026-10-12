"""Context map output: path template, utils values, split by frames, name collisions.

- ``render_template``: ``{ns.field}`` tags, ``[ ... ]`` groups that drop out
  when a tag inside is empty, ``\\[``/``\\]`` for literal brackets (reference
  function by Lee Minjun, wi-0039-lee-3).
- Split (BRK-0022, BRK-0024): each part is ``{axis, frames}``; ``axis`` is a
  lowercase frame-axis name (``echo``, ``cycle`` ...; brkraw's ``shape_desc``
  from index 3) or a data-axis number; ``frames`` follows numpy: an int picks
  one frame and removes the axis, a list keeps the axis in that order, a
  quoted ``"start:stop[:step]"`` is a Python slice.
- ``resolve_names``: collisions are an error by default; ``suffix`` adds
  ``_2``, ``_3`` ... (collision rule by Lee Minjun, wi-0038-lee-8).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

import numpy as np

from .logic import ContextMapError

SPATIAL_AXES = ("slice", "spatial", "without_slice")


class SplitError(ContextMapError):
    """A split that cannot be applied to a scan."""


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------


def _value_text(values: Mapping[str, Any], name: str) -> str:
    val = values.get(name)
    if val is None or val == "":
        return ""
    if isinstance(val, (list, tuple)):
        parts = [str(item) for item in val if item is not None and item != ""]
        return "-".join(parts)
    return str(val)


def render_template(template: str, values: Mapping[str, Any]) -> Tuple[str, List[str]]:
    """Render a context map path template; returns (path, warnings)."""
    result: List[str] = []
    warnings: List[str] = []
    in_group = False
    group: List[Any] = []
    group_has_tag = False
    i, n = 0, len(template)
    while i < n:
        char = template[i]
        if char == "\\":
            if i + 1 < n and template[i + 1] in "[]":
                (group if in_group else result).append(template[i + 1])
                i += 2
                continue
            (group if in_group else result).append("\\")
            i += 1
            continue
        if char == "[":
            if in_group:
                raise ValueError("nested [ ] groups are not allowed")
            in_group, group, group_has_tag = True, [], False
            i += 1
            continue
        if char == "]":
            if not in_group:
                raise ValueError("unmatched ]")
            if group_has_tag:
                texts = []
                complete = True
                for item in group:
                    if isinstance(item, tuple):
                        txt = _value_text(values, item[0])
                        if not txt:
                            complete = False
                            break
                        texts.append(txt)
                    else:
                        texts.append(item)
                if complete:
                    result.append("".join(texts))
            else:
                result.append("".join(group))
            in_group = False
            i += 1
            continue
        if char == "{":
            i += 1
            start = i
            while i < n and template[i] != "}":
                if template[i] == "{":
                    raise ValueError("nested { } tags are not allowed")
                if template[i] in "[]":
                    raise ValueError("a bracket inside a tag is not allowed")
                i += 1
            if i >= n:
                raise ValueError("unclosed tag")
            name = template[start:i].strip()
            i += 1
            if in_group:
                group_has_tag = True
                group.append((name,))
            else:
                txt = _value_text(values, name)
                if txt:
                    result.append(txt)
                else:
                    warnings.append(f"empty tag {{{name}}} outside [ ]")
            continue
        if char == "}":
            raise ValueError("unmatched }")
        (group if in_group else result).append(char)
        i += 1
    if in_group:
        raise ValueError("unclosed [ ] group")
    return "".join(result), warnings


def template_tags(template: str) -> List[str]:
    """Tag names used in a template (in order)."""
    import re

    return [t.strip() for t in re.findall(r"(?<!\\)\{([^}]*)\}", template)]


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------


def frame_axes(shape_desc: Sequence[str]) -> List[Tuple[int, str]]:
    """Frame axes are ``shape_desc[3:]`` (index 0-2 are the spatial axes)."""
    return [(i, name) for i, name in enumerate(shape_desc) if i >= 3]


def pick_axis(shape_desc: Sequence[str], axis: Any) -> int:
    axes = frame_axes(shape_desc)
    names = [name for _, name in axes]
    if not axes:
        raise SplitError("split: this scan has no frame axis (3D data)")
    if axis is None:
        if len(axes) == 1:
            return axes[0][0]
        raise SplitError(f"split: axis required, frame axes are {names}")
    if isinstance(axis, bool):
        raise SplitError("split: axis must be a name or a number")
    if isinstance(axis, int):
        if axis < 3 or axis >= len(shape_desc):
            raise SplitError(f"split: axis number {axis} is not a frame axis (3..{len(shape_desc) - 1})")
        return axis
    if not isinstance(axis, str) or axis != axis.lower():
        raise SplitError(f"split: axis name must be lowercase, got {axis!r}")
    if axis in SPATIAL_AXES:
        raise SplitError(f"split: '{axis}' is a spatial axis; slice packs use utils.slicepack")
    hits = [i for i, name in axes if name == axis]
    if not hits:
        raise SplitError(f"split: no axis '{axis}', frame axes are {names}")
    if len(hits) > 1:
        raise SplitError(f"split: axis '{axis}' appears {len(hits)} times, use its number {hits}")
    return hits[0]


def parse_frames(frames: Any, length: int) -> Tuple[Any, bool, List[int], List[str]]:
    """Return (numpy index, axis kept, frame list, warnings)."""
    warnings: List[str] = []
    if isinstance(frames, bool):
        raise SplitError("split: frames must be int, list or 'a:b' text")
    if isinstance(frames, int):
        if not -length <= frames < length:
            raise SplitError(f"split: frame {frames} out of range for {length} frames")
        return frames, False, [frames % length], warnings
    if isinstance(frames, (list, tuple)):
        if not frames or not all(isinstance(v, int) and not isinstance(v, bool) for v in frames):
            raise SplitError("split: frames list must hold ints")
        for v in frames:
            if not -length <= v < length:
                raise SplitError(f"split: frame {v} out of range for {length} frames")
        norm = [v % length for v in frames]
        if len(set(norm)) != len(norm):
            raise SplitError(f"split: frame repeated in {list(frames)}")
        return list(frames), True, norm, warnings
    if isinstance(frames, str):
        bits = frames.split(":")
        if len(bits) not in (2, 3):
            raise SplitError(f"split: '{frames}' is not start:stop[:step]")
        try:
            vals = [int(b) if b.strip() else None for b in bits]
        except ValueError:
            raise SplitError(f"split: '{frames}' is not start:stop[:step]") from None
        if len(vals) == 3 and vals[2] == 0:
            raise SplitError("split: slice step cannot be zero")
        sl = slice(*vals)
        for end in (vals[0], vals[1]):
            if end is not None and not -length <= end <= length:
                warnings.append(f"split: '{frames}' reaches past {length} frames; Python clamps it")
                break
        norm = list(range(length))[sl]
        if not norm:
            raise SplitError(f"split: '{frames}' selects no frame of {length}")
        return sl, True, norm, warnings
    raise SplitError("split: frames must be int, list or 'a:b' text")


def plan_split(
    shape_desc: Sequence[str], shape: Sequence[int], parts: Sequence[Mapping[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Check split parts against a scan's frame layout; returns (per-part plans, notes)."""
    if not isinstance(parts, (list, tuple)) or not parts:
        raise SplitError("split: value must be a non-empty list of parts")
    axis_ids = {pick_axis(shape_desc, p.get("axis")) for p in parts}
    if len(axis_ids) != 1:
        raise SplitError("split: all parts of one scan must use the same axis")
    ax = axis_ids.pop()
    length = int(shape[ax])
    plans: List[Dict[str, Any]] = []
    notes: List[str] = []
    used: List[int] = []
    for n, part in enumerate(parts, start=1):
        if "frames" not in part:
            raise SplitError(f"split: part {n} has no frames")
        index, keep, norm, warns = parse_frames(part["frames"], length)
        notes.extend(warns)
        plans.append({"part": n, "axis": ax, "index": index, "keep": keep, "frames": norm})
        used.extend(norm)
    overlap = sorted({f for f in used if used.count(f) > 1})
    missing = sorted(set(range(length)) - set(used))
    if overlap:
        notes.append(f"note: frames {overlap} are in more than one part")
    if missing:
        notes.append(f"note: frames {missing} are in no part (not written)")
    return plans, notes


def select_frames(data: np.ndarray, shape_desc: Sequence[str], axis: Any, frames: Any) -> Tuple[np.ndarray, List[str]]:
    """Apply one ``{axis, frames}`` selection to an array laid out as ``shape_desc``."""
    if data.ndim != len(shape_desc):
        raise SplitError(f"split: data has {data.ndim} axes but the layout names {len(shape_desc)}")
    ax = pick_axis(shape_desc, axis)
    index, _, _, notes = parse_frames(frames, data.shape[ax])
    sel: List[Any] = [slice(None)] * data.ndim
    sel[ax] = index
    return data[tuple(sel)], notes


def validate_split_parts(parts: Any, namespaces: Sequence[str]) -> None:
    """Shape of evaluated split parts: ``{axis, frames, <namespace>: {...}, sidecar: {...}}``."""
    if not isinstance(parts, (list, tuple)) or not parts:
        raise SplitError("split: value must be a non-empty list of parts")
    allowed = {"axis", "frames", "sidecar", *namespaces}
    for n, part in enumerate(parts, start=1):
        if not isinstance(part, Mapping):
            raise SplitError(f"split: part {n} must be a mapping {{axis, frames, ...}}")
        if "cycle_index" in part or "cycle_count" in part:
            raise SplitError(
                f"split: part {n} uses cycle_index/cycle_count; brkraw 0.6 splits with "
                "{axis: cycle, frames: ...}"
            )
        unknown = sorted(set(map(str, part)) - allowed)
        if unknown:
            raise SplitError(f"split: part {n} has unknown key(s) {unknown}; allowed: axis, frames, sidecar, "
                             "and namespace names")
        if "frames" not in part:
            raise SplitError(f"split: part {n} has no frames")
        for key, value in part.items():
            if key in ("axis", "frames"):
                continue
            if not isinstance(value, Mapping):
                raise SplitError(f"split: part {n}: {key} must be a mapping of field: value")


# ---------------------------------------------------------------------------
# Collisions
# ---------------------------------------------------------------------------


def resolve_names(
    items: Sequence[Tuple[str, str]],
    *,
    mode: str,
    taken: Set[str],
    exists: Callable[[str], bool],
) -> List[str]:
    """Final output names; ``mode`` "error" (default in context maps) or "suffix"."""
    if mode not in ("error", "suffix"):
        raise ValueError("on_collision must be 'error' or 'suffix'")
    if not items:
        return []
    if mode == "error":
        problems: List[str] = []
        first: Dict[str, str] = {}
        for label, name in items:
            if name in first:
                problems.append(f"{label} and {first[name]} -> {name}")
                continue
            first[name] = label
            if name in taken or exists(name):
                problems.append(f"{label} -> {name} (already exists)")
        if problems:
            raise ValueError("output name collision:\n" + "\n".join(f"  {p}" for p in problems))
        return [name for _, name in items]
    used = set(taken)
    result: List[str] = []
    for _, name in items:
        candidate = name
        counter = 2
        while candidate in used or exists(candidate):
            candidate = f"{name}_{counter}"
            counter += 1
        used.add(candidate)
        result.append(candidate)
    return result


def utils_values(
    counter: Optional[int] = None, slicepack: Optional[int] = None, split: Optional[int] = None
) -> Dict[str, Optional[int]]:
    """``utils`` values for one output (1-based; None = empty)."""
    return {"utils.counter": counter, "utils.slicepack": slicepack, "utils.split": split}


__all__ = [
    "SplitError",
    "frame_axes",
    "parse_frames",
    "pick_axis",
    "plan_split",
    "render_template",
    "resolve_names",
    "select_frames",
    "template_tags",
    "utils_values",
    "validate_split_parts",
]
