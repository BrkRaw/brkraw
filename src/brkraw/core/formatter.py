"""Render mapping/sequence data into structured, indented text using templates.

This module provides a small template renderer that supports:
- Mapping/sequence rendering via Python format strings.
- Optional wrapping and indentation.
- Per-value formatting specs for alignment, padding, repetition, and ANSI colors.
"""

from __future__ import annotations

import textwrap
from collections.abc import Mapping, Sequence
from string import Formatter
import re
from typing import Any, Callable, Literal, List, Dict, Optional, Union

MissingPolicy = Literal["error", "skip", "placeholder"]
FilterFunc = Callable[[Any], str]

_SPECIAL_VALUE_KEYS = {
    "value",
    "pattern",
    "repeat",
    "align",
    "size",
    "fill",
    "gap",
    "color",
    "underline",
    "bold",
    "italic",
}
_ANSI_COLORS = {
    "black": "30",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "white": "37",
    "gray": "90",
    "reset": "0",
}
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class _SafeFormatter(Formatter):
    """Formatter that blocks dunder access and supports mapping-based lookups."""

    def get_field(self, field_name: str, args: Sequence[Any], kwargs: Mapping[str, Any]):
        if "__" in field_name:
            raise KeyError(field_name)
        return super().get_field(field_name, args, kwargs)

    def get_value(self, key, args, kwargs):
        return super().get_value(key, args, kwargs)


def _apply_color(text: str, color: Optional[str]) -> str:
    if not color:
        return text
    code = _ANSI_COLORS.get(color, color)
    return f"\033[{code}m{text}\033[0m"


def _apply_style(
    text: str,
    *,
    underline: bool = False,
    bold: bool = False,
    italic: bool = False,
) -> str:
    if not any((underline, bold, italic)):
        return text
    codes = []
    if underline:
        codes.append("4")
    if bold:
        codes.append("1")
    if italic:
        codes.append("3")
    return f"\033[{';'.join(codes)}m{text}\033[0m"


def _visible_len(text: str) -> int:
    return len(_ANSI_ESCAPE_RE.sub("", text))


def _pad_text(text: str, width: int, align: str, fill_char: str) -> str:
    visible_len = _visible_len(text)
    if width <= visible_len:
        return text
    pad = width - visible_len
    if align == "right":
        return f"{fill_char * pad}{text}"
    if align == "center":
        left = pad // 2
        right = pad - left
        return f"{fill_char * left}{text}{fill_char * right}"
    return f"{text}{fill_char * pad}"


def _format_special_value(spec: Mapping[str, Any]) -> str:
    base = spec.get("pattern", spec.get("value", ""))
    text = str(base)
    if "repeat" in spec:
        text = text * int(spec["repeat"])

    size = spec.get("size")
    if size is None:
        styled = _apply_color(text, spec.get("color"))
        return _apply_style(
            styled,
            underline=bool(spec.get("underline", False)),
            bold=bool(spec.get("bold", False)),
            italic=bool(spec.get("italic", False)),
        )

    align = spec.get("align", "left")
    fill = spec.get("fill", spec.get("gap", " "))
    if not fill:
        fill = " "
    fill_char = str(fill)[0]
    width = int(size)

    aligned = _pad_text(text, width, align, fill_char)
    styled = _apply_color(aligned, spec.get("color"))
    return _apply_style(
        styled,
        underline=bool(spec.get("underline", False)),
        bold=bool(spec.get("bold", False)),
        italic=bool(spec.get("italic", False)),
    )


def _apply_filters(value: Any, filters: Optional[Mapping[str, FilterFunc]]) -> str:
    if isinstance(value, Mapping) and _SPECIAL_VALUE_KEYS.intersection(value):
        return _format_special_value(value)
    if filters is None:
        return str(value)
    if isinstance(value, str):
        return value
    type_name = type(value).__name__
    if type_name in filters:
        return filters[type_name](value)
    return str(value)


def _render_item(
    item: Mapping[str, Any],
    template: str,
    formatter: _SafeFormatter,
    on_missing: MissingPolicy,
    placeholder: str,
    filters: Optional[Mapping[str, FilterFunc]],
) -> str:
    class Proxy(dict):
        def __missing__(self, key):
            if on_missing == "error":
                raise KeyError(key)
            if on_missing == "skip":
                return None
            return placeholder

        def __getitem__(self, key):
            missing = False
            try:
                val = super().__getitem__(key)
            except KeyError:
                val = self.__missing__(key)
                missing = True
            if missing and val is None and on_missing == "skip":
                raise KeyError(key)
            return _apply_filters(val, filters)

    proxy = Proxy(item)
    try:
        return formatter.vformat(template, (), proxy)
    except KeyError:
        if on_missing == "skip":
            return ""
        raise


def format_data(
    data: Union[Mapping[str, Any], Sequence[Mapping[str, Any]]],
    template: str,
    *,
    indent: int = 0,
    width: Optional[int] = None,
    on_missing: MissingPolicy = "error",
    placeholder: str = "?",
    max_output_length: Optional[int] = None,
    filters: Optional[Mapping[str, FilterFunc]] = None,
) -> str:
    formatter = _SafeFormatter()
    if isinstance(data, Mapping):
        rendered_items = [_render_item(data, template, formatter, on_missing, placeholder, filters)]
    elif isinstance(data, Sequence) and not isinstance(data, (str, bytes)):
        rendered_items = []
        for item in data:
            if not isinstance(item, Mapping):
                raise TypeError("Sequence items must be mappings for templating.")
            rendered = _render_item(item, template, formatter, on_missing, placeholder, filters)
            if rendered:
                rendered_items.append(rendered)
    else:
        raise TypeError("data must be a mapping or a sequence of mappings.")

    joined = "\n".join(rendered_items)
    if width:
        joined = "\n".join(textwrap.fill(line, width=width) for line in joined.splitlines())

    result = textwrap.indent(joined, " " * indent) if indent else joined
    if max_output_length is not None and len(result) > max_output_length:
        result = result[: max_output_length - 3] + "..."
    return result


def _cell_value(cell: Any) -> str:
    if isinstance(cell, Mapping) and "value" in cell:
        return str(cell.get("value", ""))
    return str(cell)


def _cell_align(cell: Any) -> str:
    if isinstance(cell, Mapping):
        align = cell.get("align")
        if align in {"left", "right", "center"}:
            return align
    return "left"


def _cell_color(cell: Any, default_color: Optional[str]) -> Optional[str]:
    if isinstance(cell, Mapping) and "color" in cell:
        return cell.get("color")  # type: ignore[return-value]
    return default_color


def compute_column_widths(
    columns: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
    *,
    include_header: bool = True,
    wrap_last: bool = True,
) -> Dict[str, int]:
    widths: Dict[str, int] = {}
    target_cols = columns[:-1] if wrap_last and columns else columns
    if include_header:
        for col in target_cols:
            widths[col] = len(col.upper())
    for row in rows:
        for col in target_cols:
            widths[col] = max(widths.get(col, 0), len(_cell_value(row.get(col, ""))))
    return widths


def format_table(
    title: str,
    columns: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
    *,
    width: int = 80,
    colors: Optional[Mapping[str, str]] = None,
    title_color: Optional[str] = None,
    col_widths: Optional[Mapping[str, int]] = None,
    gap: int = 2,
    wrap_last: bool = True,
    min_last_col_width: int = 30,
) -> str:
    if not columns:
        return ""
    if col_widths is None:
        col_widths = compute_column_widths(columns, rows, include_header=True, wrap_last=wrap_last)

    header_cols = columns[:-1] if wrap_last else columns
    header_row = (" " * gap).join(
        _apply_style(
            _pad_text(col, col_widths.get(col, len(col)), "center", " "),
            underline=True,
        )
        for col in header_cols
    )
    if wrap_last:
        header_row += (" " * gap) + _apply_style(
            _pad_text(columns[-1], col_widths.get(columns[-1], len(columns[-1])), "center", " "),
            underline=True,
        )

    lines: List[str] = []
    if title:
        title_text = _apply_color(f"[ {title} ]", title_color)
        lines.append(title_text)
    lines.append(header_row)

    if not rows:
        lines.append("(none)")
        return "\n".join(lines)

    for row in rows:
        prefix_parts = []
        for col in header_cols:
            value = _cell_value(row.get(col, ""))
            align = _cell_align(row.get(col, ""))
            padded = _pad_text(value, col_widths.get(col, len(value)), align, " ")
            color = _cell_color(row.get(col, ""), colors.get(col) if colors else None)
            prefix_parts.append(_apply_color(padded, color))

        prefix = (" " * gap).join(prefix_parts)
        prefix_plain_parts = []
        for col in header_cols:
            value = _cell_value(row.get(col, ""))
            align = _cell_align(row.get(col, ""))
            prefix_plain_parts.append(_pad_text(value, col_widths.get(col, len(value)), align, " "))
        prefix_plain = (" " * gap).join(prefix_plain_parts)

        if wrap_last:
            desc = _cell_value(row.get(columns[-1], ""))
            desc_color = _cell_color(row.get(columns[-1], ""), colors.get(columns[-1]) if colors else None)
            indent = " " * (len(prefix_plain) + gap)
            wrap_width = max(1, width - len(prefix_plain) - gap)
            if desc:
                if wrap_width < min_last_col_width:
                    lines.append(prefix)
                    wrapped = textwrap.fill(
                        desc,
                        width=width,
                        initial_indent=" " * gap,
                        subsequent_indent=" " * gap,
                        break_long_words=False,
                        break_on_hyphens=False,
                    )
                    for line in wrapped.splitlines():
                        lines.append(_apply_color(line, desc_color))
                else:
                    wrapped = textwrap.fill(
                        desc,
                        width=wrap_width,
                        initial_indent="",
                        subsequent_indent="",
                        break_long_words=False,
                        break_on_hyphens=False,
                    )
                    wrapped_lines = wrapped.splitlines()
                    lines.append(f"{prefix}{' ' * gap}{_apply_color(wrapped_lines[0], desc_color)}")
                    for extra in wrapped_lines[1:]:
                        lines.append(f"{indent}{_apply_color(extra, desc_color)}")
            else:
                lines.append(prefix)
        else:
            lines.append(prefix)

    return "\n".join(lines)


__all__ = ["format_data", "format_table", "compute_column_widths"]


def __dir__() -> List[str]:
    return sorted(__all__)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
