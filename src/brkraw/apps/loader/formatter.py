"""Formatting helpers for loader info output.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import textwrap
from typing import Any, Optional, List, Dict

import numpy as np

from ...core import formatter as formatter_core


def _format_value(value: Any, *, float_decimals: Optional[int] = None) -> str:
    """Format values into a human-readable string.

    Args:
        value: Value to format.
        float_decimals: Decimal precision for floats.

    Returns:
        String representation of the value.
    """
    if isinstance(value, Mapping):
        return ", ".join(
            f"{k}={_format_value(v, float_decimals=float_decimals)}"
            for k, v in value.items()
        )
    if isinstance(value, np.ndarray):
        if float_decimals is not None and np.issubdtype(value.dtype, np.floating):
            return str(np.round(value, float_decimals).tolist())
        return str(value.tolist())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return "[" + ", ".join(_format_value(v, float_decimals=float_decimals) for v in value) + "]"
    if float_decimals is not None and isinstance(value, (float, np.floating)):
        return f"{value:.{float_decimals}f}"
    return str(value)


def _kv_rows(data: Mapping[str, Any], *, float_decimals: Optional[int]) -> List[Dict[str, str]]:
    """Convert a mapping into table row dicts.

    Args:
        data: Source mapping.
        float_decimals: Decimal precision for floats.

    Returns:
        List of row dictionaries with field/value keys.
    """
    return [
        {"field": str(key), "value": _format_value(val, float_decimals=float_decimals)}
        for key, val in data.items()
    ]


def format_info_tables(
    info: Mapping[str, Any],
    *,
    width: int = 80,
    indent: int = 0,
    scan_indent: int = 2,
    reco_indent: int = 4,
    scan_transpose: bool = False,
    float_decimals: Optional[int] = None,
) -> str:
    """Format study/subject/scan info into nested tables.

    Args:
        info: Mapping containing Study/Subject/Scan(s) blocks.
        width: Total table width for layout.
        indent: Base indent for the first-level tables.
        scan_indent: Extra indent for scan blocks.
        reco_indent: Extra indent for reco blocks.
        scan_transpose: If True, print scan fields in a transposed layout.
        float_decimals: Decimal precision for float values.

    Returns:
        Rendered table string.
    """
    blocks: List[str] = []
    study = info.get("Study")
    if isinstance(study, Mapping) and study:
        blocks.append(
            formatter_core.format_table(
                "Study",
                ("field", "value"),
                _kv_rows(study, float_decimals=float_decimals),
                width=width,
            )
        )
    subject = info.get("Subject")
    if isinstance(subject, Mapping) and subject:
        blocks.append(
            formatter_core.format_table(
                "Subject",
                ("field", "value"),
                _kv_rows(subject, float_decimals=float_decimals),
                width=width,
            )
        )
    scans = info.get("Scan(s)", {})
    if isinstance(scans, Mapping):
        scan_blocks: List[str] = []
        if scans:
            scan_blocks.append("[ Scan(s) ]")
        scan_items = list(scans.items())
        for idx, (scan_id, scan_data) in enumerate(scan_items):
            if not isinstance(scan_data, Mapping):
                continue
            scan_fields = {k: v for k, v in scan_data.items() if k != "Reco(s)"}
            if scan_transpose:
                scan_blocks.extend(
                    _format_scan_transposed(
                        scan_id,
                        scan_fields,
                        width=width,
                        indent=indent + scan_indent,
                        float_decimals=float_decimals,
                    )
                )
            else:
                scan_fields = {"ScanID": scan_id, **scan_fields}
                scan_table = formatter_core.format_table(
                    "",
                    ("field", "value"),
                    _kv_rows(scan_fields, float_decimals=float_decimals),
                    width=width,
                )
                scan_blocks.append(textwrap.indent(scan_table, " " * (indent + scan_indent)))

            recos = scan_data.get("Reco(s)", {})
            if isinstance(recos, Mapping) and recos:
                reco_rows = []
                for reco_id, reco_data in recos.items():
                    if isinstance(reco_data, Mapping):
                        value = _format_value(
                            reco_data.get("Type", reco_data),
                            float_decimals=float_decimals,
                        )
                    else:
                        value = _format_value(reco_data, float_decimals=float_decimals)
                    reco_rows.append(
                        {"RecoID": {"value": str(reco_id), "align": "center"}, "value": value}
                    )
                reco_table = formatter_core.format_table(
                    "Reco(s)",
                    ("RecoID", "value"),
                    reco_rows,
                    width=width,
                )
                scan_blocks.append(textwrap.indent(reco_table, " " * (indent + reco_indent)))
                if idx < len(scan_items) - 1:
                    scan_blocks.append("")
        if scan_blocks:
            blocks.append("\n".join(scan_blocks))
    return "\n\n".join(blocks)


def _format_scan_transposed(
    scan_id: Any,
    scan_fields: Mapping[str, Any],
    *,
    width: int,
    indent: int,
    float_decimals: Optional[int],
) -> List[str]:
    """Render scan fields as a transposed table layout.

    Args:
        scan_id: Scan identifier.
        scan_fields: Mapping of scan field names to values.
        width: Total table width.
        indent: Base indent for the table.
        float_decimals: Decimal precision for floats.

    Returns:
        List of formatted table blocks.
    """
    columns = [str(key) for key in scan_fields.keys()]
    values = {
        str(key): _format_value(val, float_decimals=float_decimals)
        for key, val in scan_fields.items()
    }
    grouped = _chunk_columns(columns, values, width=width, gap=2, base_cols=["ScanID"])
    blocks: List[str] = []
    scan_id_width = max(len("ScanID"), len(str(scan_id)))
    for idx, group in enumerate(grouped):
        if idx == 0:
            title = ""
            cols = ["ScanID"] + group
            row: Dict[str, Any] = {"ScanID": {"value": str(scan_id), "align": "center"}}
        else:
            title = ""
            cols = group
            row = {}
        row.update({name: values.get(name, "") for name in group})
        table = formatter_core.format_table(
            title,
            cols,
            [row],
            width=width,
            wrap_last=False,
        )
        lines = table.splitlines()
        if idx != 0:
            if lines and lines[0].startswith("["):
                lines = lines[1:]
            table = "\n".join(lines)
            extra_indent = scan_id_width + 2
            blocks.append(textwrap.indent(table, " " * (indent + extra_indent)))
        else:
            blocks.append(textwrap.indent(table, " " * indent))
    return blocks


def _chunk_columns(
    columns: List[str],
    values: Mapping[str, str],
    *,
    width: int,
    gap: int,
    base_cols: List[str],
) -> List[List[str]]:
    """Group columns so each table fits within the width.

    Args:
        columns: Column names to group.
        values: Mapping of column values used for width estimation.
        width: Maximum table width.
        gap: Spacing between columns.
        base_cols: Columns always included in width calculations.

    Returns:
        List of grouped column name lists.
    """
    groups: List[List[str]] = []
    current: List[str] = []
    for col in columns:
        candidate = current + [col]
        if _fits_width(candidate, values, width=width, gap=gap, base_cols=base_cols):
            current = candidate
        else:
            if current:
                groups.append(current)
            current = [col]
    if current:
        groups.append(current)
    return groups


def _fits_width(
    columns: List[str],
    values: Mapping[str, str],
    *,
    width: int,
    gap: int,
    base_cols: List[str],
) -> bool:
    """Check if columns fit within a target width.

    Args:
        columns: Column names to measure.
        values: Mapping of column values used for width estimation.
        width: Maximum table width.
        gap: Spacing between columns.
        base_cols: Columns always included in width calculations.

    Returns:
        True if the columns fit within the width.
    """
    cols = base_cols + columns
    total = 0
    for idx, col in enumerate(cols):
        value_len = len(values.get(col, "")) if col in values else 0
        col_width = max(len(col), value_len)
        total += col_width
        if idx < len(cols) - 1:
            total += gap
    return total <= width


__all__ = ["format_info_tables"]

def __dir__() -> List[str]:
    return sorted(__all__)
