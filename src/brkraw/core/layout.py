from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Union, List, Sequence, Tuple
import re

import numpy as np

from ..apps.addon.core import resolve_spec_reference
from ..apps.loader import info as info_resolver
from ..specs.remapper import (
    load_spec,
    map_parameters,
    load_context_map,
    load_context_map_meta,
    apply_context_map,
)

_ENTRY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_DEFAULT_VALUE_PATTERN = r"[A-Za-z0-9._-]"
_SLICEPACK_TAG = re.compile(r"\{([^}]+)\}")
_LAYOUT_TAG = re.compile(r"\{([^}]+)\}")


def render_layout(
    loader: Any,
    scan_id: int,
    *,
    layout_entries: Optional[Iterable[Mapping[str, Any]]] = None,
    layout_template: Optional[str] = None,
    context_map: Optional[Union[str, Path]] = None,
    root: Optional[Union[str, Path]] = None,
    reco_id: Optional[int] = None,
    counter: Optional[int] = None,
    override_info_spec: Optional[Union[str, Path]] = None,
    override_metadata_spec: Optional[Union[str, Path]] = None,
) -> str:
    if layout_entries is None and layout_template is None and context_map:
        meta = load_layout_meta(context_map)
        layout_entries = meta.get("layout_entries")
        if layout_entries is None:
            layout_entries = meta.get("layout_fields")
        layout_template = meta.get("layout_template")
    info = load_layout_info(
        loader,
        scan_id,
        context_map=context_map,
        root=root,
        reco_id=reco_id,
        override_info_spec=override_info_spec,
        override_metadata_spec=override_metadata_spec,
    )
    if isinstance(layout_template, str) and layout_template:
        return _render_layout_template(layout_template, info, scan_id, reco_id=reco_id, counter=counter)
    return _render_fields(layout_entries, info, scan_id, reco_id=reco_id, counter=counter)


def load_layout_info(
    loader: Any,
    scan_id: int,
    *,
    context_map: Optional[Union[str, Path]],
    root: Optional[Union[str, Path]] = None,
    reco_id: Optional[int],
    override_info_spec: Optional[Union[str, Path]] = None,
    override_metadata_spec: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    info, metadata = load_layout_info_parts(
        loader,
        scan_id,
        context_map=context_map,
        root=root,
        reco_id=reco_id,
        override_info_spec=override_info_spec,
        override_metadata_spec=override_metadata_spec,
    )
    merged = dict(info)
    merged.update(metadata)
    return merged


def load_layout_info_parts(
    loader: Any,
    scan_id: int,
    *,
    context_map: Optional[Union[str, Path]],
    root: Optional[Union[str, Path]] = None,
    reco_id: Optional[int],
    override_info_spec: Optional[Union[str, Path]] = None,
    override_metadata_spec: Optional[Union[str, Path]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    map_data = None
    if context_map:
        map_data = load_context_map(context_map)
    scan = loader.get_scan(scan_id)
    if override_info_spec:
        spec_path = resolve_spec_reference(
            str(override_info_spec),
            category="info_spec",
            root=root,
        )
        spec_data, transforms = load_spec(spec_path, validate=False)
        params_map = _build_params_map(loader, scan, reco_id=reco_id)
        mapped = map_parameters(
            params_map,
            spec_data,
            transforms,
            validate=False,
            context_map=None,
            context={"scan_id": scan_id, "reco_id": reco_id},
        )
        if not isinstance(mapped, dict):
            raise ValueError("override_info_spec must resolve to a mapping.")
        info = mapped
        study_info = info_resolver.study(loader) or {}
        if isinstance(study_info, dict):
            if "Study" in study_info and "Study" not in info:
                info["Study"] = study_info["Study"]
            if "Subject" in study_info and "Subject" not in info:
                info["Subject"] = study_info["Subject"]
    else:
        study_info = info_resolver.study(loader) or {}
        scan_info = info_resolver.scan(scan) or {}
        if isinstance(study_info, dict):
            scan_info = dict(scan_info)
            if "Study" in study_info:
                scan_info["Study"] = study_info["Study"]
            if "Subject" in study_info:
                scan_info["Subject"] = study_info["Subject"]
        info = scan_info if isinstance(scan_info, dict) else {}
    if map_data:
        info = apply_context_map(
            info,
            map_data,
            target="info_spec",
            context={"scan_id": scan_id, "reco_id": reco_id},
        )
    metadata: Dict[str, Any] = {}
    if map_data or override_metadata_spec:
        meta = loader.get_metadata(
            scan_id,
            reco_id=reco_id,
            context_map=context_map,
            spec=override_metadata_spec,
        )
        if isinstance(meta, dict):
            metadata = meta
    return info, metadata


def load_layout_meta(context_map: Optional[Union[str, Path]]) -> Dict[str, Any]:
    if not context_map:
        return {}
    return load_context_map_meta(context_map)


def render_slicepack_suffixes(
    info: Mapping[str, Any],
    *,
    count: int,
    template: str = "_slpack{index}",
    counter: Optional[int] = None,
) -> List[str]:
    suffixes: List[str] = []
    for idx in range(count):
        suffixes.append(_render_slicepack_suffix(template, info, idx, counter=counter))
    return suffixes


def _render_slicepack_suffix(
    template: str,
    info: Mapping[str, Any],
    idx: int,
    *,
    counter: Optional[int],
) -> str:
    def _replace(match: re.Match[str]) -> str:
        tag = match.group(1)
        if tag.lower() == "index":
            return str(idx + 1)
        value = _resolve_tag(tag, info, idx + 1, reco_id=None, counter=counter)
        chosen = _select_indexed_value(value, idx)
        if chosen is None:
            return str(idx + 1)
        rendered = _format_value_with_options(
            chosen,
            value_pattern=None,
            value_replace="",
            max_length=None,
        )
        return rendered or str(idx + 1)

    return _SLICEPACK_TAG.sub(_replace, template)


def _select_indexed_value(value: Any, idx: int) -> Any:
    if value is None:
        return None
    if isinstance(value, np.ndarray):
        items = value.tolist()
        return items[idx] if idx < len(items) else None
    if isinstance(value, (list, tuple)):
        return value[idx] if idx < len(value) else None
    return value


def _build_params_map(loader: Any, scan: Any, *, reco_id: Optional[int]) -> Dict[str, Any]:
    params_map: Dict[str, Any] = {
        "method": getattr(scan, "method", None),
        "acqp": getattr(scan, "acqp", None),
    }
    study = getattr(loader, "_study", None)
    subject = getattr(study, "subject", None)
    if subject is not None:
        params_map["subject"] = subject

    if reco_id is None:
        reco_ids = list(getattr(scan, "avail", {}).keys())
        reco_id = reco_ids[0] if reco_ids else None
    if reco_id is not None:
        reco = scan.get_reco(reco_id)
        params_map["visu_pars"] = {reco_id: reco.visu_pars}
        params_map["reco"] = {reco_id: reco.reco}
    return params_map


def _render_fields(
    fields: Optional[Iterable[Mapping[str, Any]]],
    info: Mapping[str, Any],
    scan_id: int,
    *,
    reco_id: Optional[int],
    counter: Optional[int],
) -> str:
    parts: List[str] = []
    seps: List[Optional[str]] = []
    entry_values: Dict[str, Any] = {}

    for field in fields or []:
        if not isinstance(field, Mapping):
            continue
        key = field.get("key")
        use_entry = field.get("use_entry")
        hide = bool(field.get("hide"))
        entry = field.get("entry")
        sep = field.get("sep")
        value_pattern = field.get("value_pattern")
        value_replace = field.get("value_replace", "")
        max_length = field.get("max_length")

        if key is not None and use_entry is not None:
            continue
        if key is None and use_entry is None:
            continue

        value_str: Optional[str] = None
        entry_clean: Optional[str] = None

        if key is not None:
            if not isinstance(key, str) or not key.strip():
                continue
            if isinstance(entry, str) and entry.strip():
                entry_clean = entry.strip()
                if not _ENTRY_PATTERN.match(entry_clean):
                    continue
            elif not hide:
                entry_clean = key.replace(".", "").lower()
                if not _ENTRY_PATTERN.match(entry_clean):
                    continue
            value = _resolve_tag(key, info, scan_id, reco_id=reco_id, counter=counter)
            value_str = _format_value_with_options(
                value,
                value_pattern=value_pattern,
                value_replace=value_replace,
                max_length=max_length,
            )
            if value_str is None:
                continue
            if entry_clean:
                entry_values[entry_clean] = value
        else:
            if not isinstance(use_entry, str) or not use_entry.strip():
                continue
            entry_clean = use_entry.strip()
            if not _ENTRY_PATTERN.match(entry_clean):
                continue
            raw_value = entry_values.get(entry_clean)
            if raw_value is None:
                continue
            value_str = _format_value_with_options(
                raw_value,
                value_pattern=value_pattern,
                value_replace=value_replace,
                max_length=max_length,
            )
            if value_str is None:
                continue

        if hide:
            parts.append(value_str)
        else:
            parts.append(f"{entry_clean}-{value_str}")
        if isinstance(sep, str) and sep:
            seps.append(sep)
        else:
            seps.append(None)

    if not parts:
        return f"scan-{scan_id}"
    result = parts[0]
    for idx in range(1, len(parts)):
        joiner = seps[idx - 1] if seps[idx - 1] is not None else "_"
        result = f"{result}{joiner}{parts[idx]}"
    return result


def _render_layout_template(
    template: str,
    info: Mapping[str, Any],
    scan_id: int,
    *,
    reco_id: Optional[int],
    counter: Optional[int],
) -> str:
    if not _LAYOUT_TAG.search(template):
        return template
    rendered = _LAYOUT_TAG.sub(
        lambda m: _resolve_layout_tag(m, info, scan_id, reco_id=reco_id, counter=counter),
        template,
    )
    return rendered or template


def _resolve_layout_tag(
    match: re.Match[str],
    info: Mapping[str, Any],
    scan_id: int,
    *,
    reco_id: Optional[int],
    counter: Optional[int],
) -> str:
    tag = match.group(1) or ""
    if not tag:
        return ""
    value = _resolve_tag(tag.strip(), info, scan_id, reco_id=reco_id, counter=counter)
    rendered = _format_value(value)
    return rendered or ""


def _resolve_tag(
    tag: str,
    info: Mapping[str, Any],
    scan_id: int,
    *,
    reco_id: Optional[int] = None,
    counter: Optional[int] = None,
) -> Any:
    if tag in {"ScanID", "scan_id", "scanid"}:
        return scan_id
    if tag in {"RecoID", "reco_id", "recoid"}:
        return reco_id
    if tag in {"Counter", "counter"}:
        return counter
    if "." in tag:
        root_key, rest = tag.split(".", 1)
        root_val = info.get(root_key)
        if isinstance(root_val, Mapping):
            return _resolve_nested(root_val, rest)
        return None
    return info.get(tag)


def _format_value(value: Any) -> Optional[str]:
    return _format_value_with_options(
        value,
        value_pattern=None,
        value_replace="",
        max_length=None,
    )


def _format_value_with_options(
    value: Any,
    *,
    value_pattern: Optional[str],
    value_replace: Optional[str],
    max_length: Optional[Any],
) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, Mapping):
        parts = []
        for k, v in value.items():
            k_str = _sanitize_value(k, value_pattern, value_replace, None)
            v_str = _format_value_with_options(
                v,
                value_pattern=value_pattern,
                value_replace=value_replace,
                max_length=None,
            )
            if k_str and v_str:
                parts.append(f"{k_str}-{v_str}")
        raw = "-".join(parts)
    elif isinstance(value, np.ndarray):
        raw = "-".join(str(v) for v in value.tolist())
    elif isinstance(value, (list, tuple)):
        items = [
            v for v in (
                _format_value_with_options(
                    v,
                    value_pattern=value_pattern,
                    value_replace=value_replace,
                    max_length=None,
                )
                for v in value
            )
            if v
        ]
        raw = "-".join(items)
    else:
        raw = str(value).strip()
    if not raw:
        return None
    cleaned = _sanitize_value(raw, value_pattern, value_replace, max_length)
    return cleaned or None


def _sanitize_value(
    raw: Any,
    value_pattern: Optional[str],
    value_replace: Optional[str],
    max_length: Optional[Any],
) -> Optional[str]:
    text = str(raw).strip()
    if not text:
        return None
    pattern = value_pattern or _DEFAULT_VALUE_PATTERN
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid value_pattern: {pattern!r}") from exc
    repl = "" if value_replace is None else str(value_replace)
    cleaned = "".join(
        ch if regex.fullmatch(ch) else repl for ch in text
    )
    if isinstance(max_length, int) and max_length > 0:
        cleaned = cleaned[:max_length]
    return cleaned or None


def _resolve_nested(value: Mapping[str, Any], dotted: str) -> Any:
    current: Any = value
    for part in dotted.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current
