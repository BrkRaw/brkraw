"""Context map v3 (BRK-0016, BRK-0021 ... BRK-0024).

A context map is a YAML file next to a dataset (same name) or given
explicitly. It never changes the original information (subject, study,
session, scan info, scan and reco IDs); it defines output values in
namespaces that the user names (for example ``bids:``), with four value
forms: a direct value, ``{from: KEY}``, ``{from: KEY, map: {...}, default: X}``
and any of those with ``when: {...}``. A list of value specs gives the first
item whose ``when`` matches.

Reserved top-level names: ``convert`` (``false`` skips a scan), ``split``
(parts of one scan), ``sidecar`` (metadata added; an empty value removes the
key) and ``utils`` (values brkraw fills at the layout step; never defined in
a file). Namespace fields read original values only; ``convert``, ``split``,
``sidecar`` and the layout template read originals and namespaces.

Bundle B4 implements loading, validation, include and value evaluation.
Path rendering, ``utils`` values, collisions and split slicing are separate.
"""
from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import yaml

logger = logging.getLogger(__name__)

RESERVED = ("convert", "split", "sidecar", "utils")
META_KEYS = {"category", "include", "name", "version", "description", "layout_template", "on_collision"}
META_NOT_INHERITED = {"include", "name", "version", "description", "category"}
ON_COLLISION = ("error", "suffix")
SPEC_WORDS = {"when", "value", "from", "map", "default"}
OLD_SPEC_WORDS = {"type", "values", "cases", "selector", "target", "override", "ref"}
OLD_META = {"layout_entries", "include_mode"}
ORIGINAL_TOP = {"Subject", "Study", "Session", "ScanID", "RecoID", "Method", "MethodBase", "Protocol"}
UTILS_NAMES = ("counter", "slicepack", "split")
CONDITION_OPS = {"not", "in", "regex"}
CATEGORY = "context_map"

_NS_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_TEMPLATE_TAG = re.compile(r"(?<!\\)\{([^}]*)\}")
_OLD_SYNTAX = (
    "old context map syntax ({words}) is not supported in brkraw 0.6: define values in a namespace "
    "with value / from / map / default / when (see 'Migrating to 0.6')"
)


class ContextMapError(ValueError):
    """A context map file that cannot be used (syntax, structure or include)."""


@dataclass
class ScanPlan:
    """What a context map decides for one scan."""

    namespaces: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    convert: bool = True
    split: Optional[List[Any]] = None
    sidecar: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# YAML without base-60 numbers (YAML 1.2 behaviour for "1:30")
# ---------------------------------------------------------------------------

_INT = "tag:yaml.org,2002:int"
_FLOAT = "tag:yaml.org,2002:float"


class _Loader(yaml.SafeLoader):
    """SafeLoader whose int/float resolvers drop the YAML 1.1 sexagesimal forms."""


_Loader.yaml_implicit_resolvers = {
    key: [(tag, rx) for tag, rx in value if tag not in (_INT, _FLOAT)]
    for key, value in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Loader.add_implicit_resolver(
    _INT,
    re.compile(
        r"""^(?:[-+]?0b[0-1_]+
            |[-+]?0[0-7_]+
            |[-+]?(?:0|[1-9][0-9_]*)
            |[-+]?0x[0-9a-fA-F_]+)$""",
        re.X,
    ),
    list("-+0123456789"),
)
_Loader.add_implicit_resolver(
    _FLOAT,
    re.compile(
        r"""^(?:[-+]?(?:[0-9][0-9_]*)\.[0-9_]*(?:[eE][-+]?[0-9]+)?
            |[-+]?(?:[0-9][0-9_]*)(?:[eE][-+]?[0-9]+)
            |\.[0-9_]+(?:[eE][-+]?[0-9]+)?
            |[-+]?\.(?:inf|Inf|INF)
            |\.(?:nan|NaN|NAN))$""",
        re.X,
    ),
    list("-+0123456789."),
)


def load_yaml(text: str, *, source: Optional[str] = None) -> Any:
    """Parse context map YAML. Unquoted ``1:30`` stays text (no base-60 numbers)."""
    try:
        return yaml.load(text, Loader=_Loader)  # noqa: S506 - SafeLoader subclass
    except yaml.YAMLError as exc:
        where = f"{source}: " if source else ""
        raise ContextMapError(f"{where}YAML error: {exc}") from exc


# ---------------------------------------------------------------------------
# Evaluation core (conditions, references, value specs)
# ---------------------------------------------------------------------------


class _Missing:
    def __repr__(self) -> str:
        return "MISSING"


MISSING = _Missing()


def matches_condition(value: Any, cond: Any) -> bool:
    """``cond`` is a plain value (equality) or a mapping of operators ``not``, ``in``, ``regex``."""
    if isinstance(cond, Mapping):
        for op, expected in cond.items():
            if op == "not":
                if matches_condition(value, expected):
                    return False
            elif op == "in":
                if not isinstance(expected, (list, tuple, set)):
                    expected = [expected]
                if isinstance(value, (list, tuple, set)):
                    if not any(item in expected for item in value):
                        return False
                elif value not in expected:
                    return False
            elif op == "regex":
                if re.search(str(expected), str(value)) is None:
                    return False
            else:
                raise ValueError("unknown condition operator: " + str(op))
        return True
    return value == cond


def resolve_ref(key: str, look: Mapping[str, Any], ids: Mapping[str, Any]) -> Any:
    """Value of ``key`` (``ScanID``/``RecoID``, a plain key or a dotted path); None counts as MISSING."""
    low = key.lower()
    if low in ids and ids[low] is not None:
        return ids[low]
    if key in look:
        value = look[key]
    elif "." in key:
        value = look
        for part in key.split("."):
            if isinstance(value, Mapping) and part in value:
                value = value[part]
            else:
                return MISSING
    else:
        return MISSING
    return MISSING if value is None else value


def matches_when(when: Any, look: Mapping[str, Any], ids: Mapping[str, Any]) -> bool:
    """True when every ``key: condition`` of ``when`` holds; a missing key never matches."""
    if not isinstance(when, Mapping):
        raise ValueError("when must be a mapping")
    for key, cond in when.items():
        actual = resolve_ref(str(key), look, ids)
        if actual is MISSING or not matches_condition(actual, cond):
            return False
    return True


def _lookup(value: Any, table: Mapping[Any, Any], default: Any) -> Any:
    try:
        if value in table:
            return table[value]
    except TypeError:
        return default
    if str(value) in table:
        return table[str(value)]
    return default


def evaluate(spec: Any, look: Mapping[str, Any], ids: Mapping[str, Any]) -> Any:
    """Value of one value spec (or a first-match list of them); nothing matching gives None."""
    items = spec if isinstance(spec, list) else [spec]
    for item in items:
        if not isinstance(item, Mapping):
            return item
        if "when" in item and not matches_when(item["when"], look, ids):
            continue
        if "value" in item:
            return item["value"]
        raw = resolve_ref(str(item["from"]), look, ids)
        raw = None if raw is MISSING else raw
        default = item.get("default")
        if "map" not in item:
            return raw if raw is not None else default
        table = item["map"]
        if raw is None:
            return default
        if isinstance(raw, (list, tuple)):
            return [_lookup(v, table, default) for v in raw]
        return _lookup(raw, table, default)
    return None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _items(spec: Any) -> List[Any]:
    return spec if isinstance(spec, list) else [spec]


def _check_condition(where: str, cond: Any) -> None:
    if isinstance(cond, Mapping):
        unknown = sorted(set(map(str, cond)) - CONDITION_OPS)
        if unknown:
            raise ContextMapError(
                f"{where}: unknown condition operator(s) {unknown}; allowed: {sorted(CONDITION_OPS)}"
            )
        if "not" in cond:
            _check_condition(where, cond["not"])


def _check_spec(where: str, spec: Any, *, namespaces: Sequence[str], inside_namespace: bool) -> None:
    for item in _items(spec):
        if not isinstance(item, Mapping):
            continue
        words = set(map(str, item))
        old = sorted(words & OLD_SPEC_WORDS)
        if old:
            raise ContextMapError(f"{where}: " + _OLD_SYNTAX.format(words=", ".join(old)))
        unknown = sorted(words - SPEC_WORDS)
        if unknown:
            raise ContextMapError(f"{where}: unknown word(s) {unknown}; allowed: {sorted(SPEC_WORDS)}")
        if "value" in item and "from" in item:
            raise ContextMapError(f"{where}: use either value or from, not both")
        if ("map" in item or "default" in item) and "from" not in item:
            raise ContextMapError(f"{where}: map/default need from")
        if "value" not in item and "from" not in item:
            raise ContextMapError(f"{where}: needs value or from")
        if "map" in item and not isinstance(item["map"], Mapping):
            raise ContextMapError(f"{where}: map must be a table (original value: new value)")
        when = item.get("when")
        if "when" in item and not isinstance(when, Mapping):
            raise ContextMapError(f"{where}: when must be a mapping (key: condition)")
        refs = [item.get("from")] + list((when or {}).keys())
        for key, cond in (when or {}).items():
            _check_condition(f"{where} when {key}", cond)
        for ref in refs:
            if not isinstance(ref, str):
                continue
            head = ref.split(".")[0]
            if head == "utils":
                raise ContextMapError(
                    f"{where}: {ref!r} — utils exists only at the layout step (layout_template), "
                    "not in namespace fields, convert, split or sidecar"
                )
            if inside_namespace and head in namespaces:
                raise ContextMapError(
                    f"{where}: a namespace field reads only original values, not {ref!r}"
                )


def _check_file(name: str, data: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Structure checks for one file; returns (rules, meta)."""
    if data is None:
        data = {}
    if not isinstance(data, Mapping):
        raise ContextMapError(f"{name}: a context map must be a mapping")
    raw_meta = data.get("__meta__") or {}
    if not isinstance(raw_meta, Mapping):
        raise ContextMapError(f"{name}: __meta__ must be a mapping")
    meta = dict(raw_meta)
    if "slicepack_suffix" in meta:
        raise ContextMapError(
            f"{name}: __meta__.slicepack_suffix is not used in context maps; put [_sp{{utils.slicepack}}] "
            "in layout_template instead (the config's slicepack_suffix is unchanged)"
        )
    old = sorted(set(meta) & OLD_META)
    if old:
        raise ContextMapError(f"{name}: " + _OLD_SYNTAX.format(words=", ".join(f"__meta__.{k}" for k in old)))
    unknown = sorted(set(map(str, meta)) - META_KEYS)
    if unknown:
        raise ContextMapError(f"{name}: unknown __meta__ key(s) {unknown}; allowed: {sorted(META_KEYS)}")
    if "on_collision" in meta and meta["on_collision"] not in ON_COLLISION:
        raise ContextMapError(f"{name}: __meta__.on_collision must be 'error' or 'suffix'")
    if "category" in meta and meta["category"] != CATEGORY:
        raise ContextMapError(f"{name}: __meta__.category is {meta['category']!r}, not {CATEGORY!r}")
    rules: Dict[str, Any] = {}
    for key, block in data.items():
        if key == "__meta__":
            continue
        key = str(key)
        if key == "__split__":
            raise ContextMapError(f"{name}: " + _OLD_SYNTAX.format(words="__split__"))
        if key == "utils":
            raise ContextMapError(f"{name}: utils is filled by brkraw at the layout step and cannot be defined")
        if "." in key:
            raise ContextMapError(
                f"{name}: {key!r} would change an original value; put it in a namespace, "
                "for example bids: {sub: ...}"
            )
        if key in ORIGINAL_TOP:
            raise ContextMapError(f"{name}: {key!r} is an original info name; choose another namespace name")
        if key in ("convert", "split"):
            rules[key] = block
            continue
        if not isinstance(block, Mapping):
            raise ContextMapError(f"{name}: {key!r} must be a namespace (name: {{field: value}})")
        if key != "sidecar" and not _NS_NAME.match(key):
            raise ContextMapError(f"{name}: {key!r} is not a valid namespace name (letters, digits, _)")
        rules[key] = dict(block)
    return rules, meta


def _check_merged(rules: Mapping[str, Any], meta: Mapping[str, Any], name: str) -> None:
    namespaces = [k for k in rules if k not in RESERVED]
    for ns in namespaces:
        for fld, spec in rules[ns].items():
            _check_spec(f"{name}: {ns}.{fld}", spec, namespaces=namespaces, inside_namespace=True)
    for key in ("convert", "split"):
        if key in rules:
            _check_spec(f"{name}: {key}", rules[key], namespaces=namespaces, inside_namespace=False)
    for fld, spec in (rules.get("sidecar") or {}).items():
        _check_spec(f"{name}: sidecar.{fld}", spec, namespaces=namespaces, inside_namespace=False)
    template = meta.get("layout_template")
    if template is not None:
        if not isinstance(template, str):
            raise ContextMapError(f"{name}: __meta__.layout_template must be text")
        for tag in _TEMPLATE_TAG.findall(template):
            ref = tag.strip()
            head = ref.split(".")[0]
            if head == "utils":
                if ref[len("utils."):] not in UTILS_NAMES:
                    raise ContextMapError(
                        f"{name}: layout_template tag {{{ref}}} — utils has only "
                        + ", ".join(f"utils.{n}" for n in UTILS_NAMES)
                    )
            elif head not in namespaces or "." not in ref:
                raise ContextMapError(
                    f"{name}: layout_template tag {{{ref}}} is not a namespace field; a context map "
                    "template uses only namespace fields ({ns.field}) and utils values"
                )


# ---------------------------------------------------------------------------
# Loading and include
# ---------------------------------------------------------------------------


def _looks_like_path(value: str) -> bool:
    return "/" in value or "\\" in value or value.startswith(".") or value.endswith((".yaml", ".yml"))


def _resolve_include(item: Any, base_dir: Path, name: str) -> Path:
    if isinstance(item, Mapping):
        use, version = item.get("use"), item.get("version")
        if not isinstance(use, str) or not use:
            raise ContextMapError(f"{name}: include {{use, version}} needs a name in use")
    elif isinstance(item, str):
        use, version = item, None
        if _looks_like_path(use):
            path = (base_dir / use).expanduser().resolve()
            if not path.is_file():
                raise ContextMapError(f"{name}: included file not found: {use}")
            return path
    else:
        raise ContextMapError(f"{name}: include items are file paths, installed names or {{use, version}}")
    from ...apps.addon.dependencies import resolve_context_map_reference

    label = use + (f" version {version}" if version else "")
    try:
        return Path(resolve_context_map_reference(use, version=None if version is None else str(version)))
    except (FileNotFoundError, ValueError) as exc:
        raise ContextMapError(f"{name}: context map include not found: {label} ({exc})") from exc


def _prepend(new: Any, old: Any) -> Any:
    """BRK-0015 (2) A: the newer file's items go first; the base's items stay as fall-through."""
    return new if old is None else _items(new) + _items(old)


def _merge_into(merged: Dict[str, Any], rules: Mapping[str, Any]) -> None:
    for key, block in rules.items():
        if key in ("convert", "split"):
            merged[key] = _prepend(block, merged.get(key))
        else:
            target = merged.setdefault(key, {})
            for fld, spec in block.items():
                target[fld] = _prepend(spec, target.get(fld))


def _load(
    data: Any, name: str, base_dir: Path, stack: Tuple[Path, ...]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    rules, meta = _check_file(name, data)
    includes = meta.get("include") or []
    if isinstance(includes, (str, Mapping)):
        includes = [includes]
    merged_rules: Dict[str, Any] = {}
    merged_meta: Dict[str, Any] = {}
    for item in includes:
        path = _resolve_include(item, base_dir, name)
        if path in stack:
            chain = " -> ".join(p.name for p in stack + (path,))
            raise ContextMapError(f"circular include: {chain}")
        text = path.read_text(encoding="utf-8")
        inc_rules, inc_meta = _load(load_yaml(text, source=str(path)), path.name, path.parent, stack + (path,))
        _merge_into(merged_rules, inc_rules)
        merged_meta.update(inc_meta)
    _merge_into(merged_rules, rules)
    merged_meta.update({k: v for k, v in meta.items() if k not in META_NOT_INHERITED})
    return merged_rules, merged_meta


def load_context_map(path: Union[str, Path]) -> Dict[str, Any]:
    """Load, include and validate a context map file.

    Returns one mapping: ``{"__meta__": merged meta, <namespace>: {...},
    "convert": ..., "split": ..., "sidecar": {...}}``. Included files come
    first and the file's own items are placed in front of them per field.
    """
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise ContextMapError(f"context map not found: {path}")
    data = load_yaml(path.read_text(encoding="utf-8"), source=str(path))
    rules, meta = _load(data, path.name, path.parent, (path,))
    _check_merged(rules, meta, path.name)
    return {"__meta__": meta, **copy.deepcopy(rules)}


def validate_context_map(source: Union[str, Path, Mapping[str, Any]]) -> None:
    """Raise ``ContextMapError`` if a file (or an already-parsed mapping) is not a valid context map."""
    if isinstance(source, Mapping):
        rules, meta = _load(source, "<mapping>", Path.cwd(), ())
        _check_merged(rules, meta, "<mapping>")
        return
    load_context_map(source)


def find_context_map(dataset: Union[str, Path]) -> Optional[Path]:
    """The same-name YAML next to a dataset, or None.

    A folder uses its whole name; a file drops its last extension
    (``20240101_mouse01.zip`` -> ``20240101_mouse01.yaml``). ``.yaml`` or
    ``.yml``; both present is an error.
    """
    dataset = Path(dataset).expanduser()
    stem = dataset.name if dataset.is_dir() or not dataset.suffix else dataset.name[: -len(dataset.suffix)]
    found = [dataset.parent / f"{stem}{ext}" for ext in (".yaml", ".yml")]
    found = [p for p in found if p.is_file()]
    if len(found) > 1:
        raise ContextMapError(f"both {found[0].name} and {found[1].name} are next to {dataset.name}; keep one")
    return found[0] if found else None


def resolve_context_map(
    dataset: Union[str, Path], context_map: Optional[Union[str, Path]] = "auto"
) -> Optional[Dict[str, Any]]:
    """The context map to use for a dataset.

    ``"auto"`` (default): the same-name file, used only when its
    ``__meta__.category`` is ``context_map`` (otherwise a warning and None).
    ``None``: no context map. A path: that file.
    """
    if context_map is None:
        return None
    if isinstance(context_map, str) and context_map == "auto":
        path = find_context_map(dataset)
        if path is None:
            return None
        data = load_yaml(path.read_text(encoding="utf-8"), source=str(path))
        meta = data.get("__meta__") if isinstance(data, Mapping) else None
        if not isinstance(meta, Mapping) or meta.get("category") != CATEGORY:
            logger.warning(
                "Ignoring %s: a context map found by name needs __meta__.category: %s",
                path.name,
                CATEGORY,
            )
            return None
        return load_context_map(path)
    return load_context_map(context_map)


# ---------------------------------------------------------------------------
# Applying a context map to one scan
# ---------------------------------------------------------------------------


def _split_map(map_data: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    meta = dict(map_data.get("__meta__") or {})
    rules = {k: v for k, v in map_data.items() if k != "__meta__"}
    return rules, meta


def plan_scan(
    info: Mapping[str, Any],
    map_data: Mapping[str, Any],
    *,
    scan_id: Optional[int] = None,
    reco_id: Optional[int] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> ScanPlan:
    """Evaluate a loaded context map for one scan.

    ``info`` is the original study and scan information (never changed).
    ``Session.ID`` is ``Study.ID`` unless the information gives one.
    ``metadata`` is the sidecar content before the map's ``sidecar`` fields.
    Every returned value is a copy.
    """
    rules, _ = _split_map(map_data)
    look: Dict[str, Any] = dict(info)
    session = info.get("Session") if isinstance(info.get("Session"), Mapping) else {}
    if not (session or {}).get("ID"):
        study = info.get("Study") if isinstance(info.get("Study"), Mapping) else {}
        look["Session"] = {**dict(session or {}), "ID": (study or {}).get("ID")}
    ids = {"scanid": scan_id, "scan_id": scan_id, "recoid": reco_id, "reco_id": reco_id}

    namespaces: Dict[str, Dict[str, Any]] = {}
    for ns, fields in rules.items():
        if ns in RESERVED:
            continue
        if ns in info:
            raise ContextMapError(f"namespace {ns!r} is also an original info name; choose another name")
        namespaces[ns] = {fld: copy.deepcopy(evaluate(spec, look, ids)) for fld, spec in fields.items()}

    layered = {**look, **dict(metadata or {}), **namespaces}
    convert = evaluate(rules["convert"], layered, ids) if "convert" in rules else None
    split = copy.deepcopy(evaluate(rules["split"], layered, ids)) if "split" in rules else None
    sidecar = copy.deepcopy(dict(metadata or {}))
    for fld, spec in (rules.get("sidecar") or {}).items():
        value = evaluate(spec, layered, ids)
        if value is None:
            sidecar.pop(fld, None)
        else:
            sidecar[fld] = copy.deepcopy(value)
    return ScanPlan(namespaces=namespaces, convert=convert is not False, split=split, sidecar=sidecar)


def apply_context_map(
    info: Mapping[str, Any],
    map_data: Mapping[str, Any],
    *,
    target: str = "info_spec",
    scan_id: Optional[int] = None,
    reco_id: Optional[int] = None,
    metadata: Optional[Mapping[str, Any]] = None,
    context: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Apply a loaded context map without changing its inputs.

    ``target="info_spec"``: a new dict = a copy of ``info`` plus one key per
    namespace. ``target="metadata_spec"``: the sidecar after the map's
    ``sidecar`` fields (``metadata`` defaults to ``info``). ``context`` may
    give ``scan_id``/``reco_id`` (the brkraw-viewer call style).
    """
    if context:
        scan_id = context.get("scan_id", scan_id)
        reco_id = context.get("reco_id", reco_id)
    if target == "info_spec":
        plan = plan_scan(info, map_data, scan_id=scan_id, reco_id=reco_id, metadata=metadata)
        out = copy.deepcopy(dict(info))
        out.update(plan.namespaces)
        return out
    if target == "metadata_spec":
        meta_in = info if metadata is None else metadata
        return plan_scan(info, map_data, scan_id=scan_id, reco_id=reco_id, metadata=meta_in).sidecar
    raise ValueError("target must be 'info_spec' or 'metadata_spec'")


__all__ = [
    "CATEGORY",
    "ContextMapError",
    "MISSING",
    "RESERVED",
    "ScanPlan",
    "UTILS_NAMES",
    "apply_context_map",
    "evaluate",
    "find_context_map",
    "load_context_map",
    "load_yaml",
    "matches_condition",
    "matches_when",
    "plan_scan",
    "resolve_context_map",
    "resolve_ref",
    "validate_context_map",
]
