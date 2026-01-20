from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping
import inspect
import re
from types import ModuleType
from typing import Any, Callable, Optional, List, Dict, Tuple, Set, Union, Iterable
import yaml
from .validator import validate_spec, validate_map_data

_MISSING = object()


def _load_transforms_from_source(src: str) -> Dict[str, Callable[[Any], Any]]:
    """Execute a Python snippet and extract public callables.

    Args:
        src: Python source code that defines transform callables.

    Returns:
        A mapping of transform names to callables defined in the snippet.
    """
    mod = ModuleType("spec_transforms")
    exec(src, mod.__dict__)
    return {
        name: obj
        for name, obj in mod.__dict__.items()
        if callable(obj) and not name.startswith("_") and not inspect.isclass(obj)
    }

def _normalize_transforms_source(
    transforms_source: Any,
    *,
    base_dir: Path,
) -> List[Path]:
    if transforms_source is None:
        return []
    sources: List[str]
    if isinstance(transforms_source, str):
        sources = [transforms_source]
    elif isinstance(transforms_source, list) and all(isinstance(item, str) for item in transforms_source):
        sources = transforms_source
    else:
        raise ValueError("transforms_source must be a string or list of strings.")
    paths: List[Path] = []
    for item in sources:
        src = Path(item)
        if not src.is_absolute():
            src = (base_dir / src).resolve()
        paths.append(src)
    return paths


def _collect_transforms_paths(spec: Dict[str, Any], spec_path: Path) -> List[Path]:
    paths: List[Path] = []
    meta = spec.get("__meta__")
    if isinstance(meta, dict) and meta.get("transforms_source"):
        paths.extend(_normalize_transforms_source(meta.get("transforms_source"), base_dir=spec_path.parent))
    for value in spec.values():
        if not isinstance(value, dict):
            continue
        child_meta = value.get("__meta__")
        if isinstance(child_meta, dict) and child_meta.get("transforms_source"):
            paths.extend(
                _normalize_transforms_source(child_meta.get("transforms_source"), base_dir=spec_path.parent)
            )
    return paths


def _load_spec_data(spec_path: Path, stack: Set[Path]) -> Tuple[Dict[str, Any], List[Path]]:
    spec_path = spec_path.resolve()
    if spec_path in stack:
        raise ValueError(f"Circular spec include detected: {spec_path}")
    if spec_path.suffix not in (".yaml", ".yml"):
        raise ValueError("Spec file must be a .yaml/.yml file.")
    stack.add(spec_path)
    try:
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        if not isinstance(spec, dict):
            raise ValueError("Spec file must contain a mapping.")
        transforms_paths = _collect_transforms_paths(spec, spec_path)
        include_list: List[str] = []
        meta = spec.get("__meta__")
        include_mode = "override"
        if isinstance(meta, dict) and meta.get("include_mode"):
            include_mode = str(meta["include_mode"])
            if include_mode not in {"override", "strict"}:
                raise ValueError("include_mode must be 'override' or 'strict'.")
        if isinstance(meta, dict) and "include" in meta:
            include = meta.get("include")
            if isinstance(include, str):
                include_list = [include]
            elif isinstance(include, list) and all(isinstance(item, str) for item in include):
                include_list = include
            else:
                raise ValueError("__meta__.include must be a string or list of strings.")

        merged: Dict[str, Any] = {}
        for item in include_list:
            inc_path = Path(item)
            if not inc_path.is_absolute():
                inc_path = (spec_path.parent / inc_path).resolve()
            inc_spec, inc_transforms = _load_spec_data(inc_path, stack)
            transforms_paths.extend(inc_transforms)
            for key, value in inc_spec.items():
                if key == "__meta__":
                    continue
                if include_mode == "strict" and key in merged:
                    raise ValueError(f"Spec include conflict for key {key!r} in {spec_path}")
                merged[key] = value

        for key, value in spec.items():
            if key == "__meta__":
                continue
            if include_mode == "strict" and key in merged:
                raise ValueError(f"Spec include conflict for key {key!r} in {spec_path}")
            merged[key] = value

        if isinstance(meta, dict):
            meta_clean = dict(meta)
            meta_clean.pop("include", None)
            meta_clean.pop("include_mode", None)
            merged["__meta__"] = meta_clean

        return merged, transforms_paths
    finally:
        stack.remove(spec_path)


def load_spec(
    spec_source: Union[str, Path],
    *,
    validate: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Callable]]:
    """Load spec YAML plus optional transforms from files.

    Args:
        spec_source: YAML file path.
        validate: If True, validate the spec before returning.

    Returns:
        Tuple of (spec, transforms) where transforms is a name->callable mapping.

    Notes:
        Transforms are loaded from ``__meta__.transforms_source`` when present,
        including sources referenced via ``__meta__.include``.
    """
    spec_path = Path(spec_source)
    spec, transforms_paths = _load_spec_data(spec_path, set())
    transforms_path: List[Path] = []
    if transforms_paths:
        seen: Set[Path] = set()
        for item in transforms_paths:
            if item not in seen:
                transforms_path.append(item)
                seen.add(item)
    if validate:
        validate_spec(spec, transforms_source=transforms_path)

    transforms: Dict[str, Callable] = {}
    _attach_spec_path_meta(spec, spec_path)
    if not transforms_path:
        return spec, transforms

    for path in transforms_path:
        transforms_text = path.read_text(encoding="utf-8")
        transforms.update(_load_transforms_from_source(transforms_text))
    return spec, transforms


def _attach_spec_path_meta(spec: Dict[str, Any], spec_path: Path) -> None:
    meta = spec.get("__meta__")
    if isinstance(meta, dict):
        meta["__spec_path__"] = str(spec_path)
    for value in spec.values():
        if not isinstance(value, dict):
            continue
        child_meta = value.get("__meta__")
        if isinstance(child_meta, dict):
            child_meta["__spec_path__"] = str(spec_path)


def _get_params_from_map(params_map: Mapping[str, Any], file: str, reco_id: Optional[int]):
    if file == "subject":
        return params_map.get("subject")
    params = params_map.get(file)
    if params is None:
        return None
    if file in ("visu_pars", "reco") and isinstance(params, Mapping):
        if reco_id is None:
            if len(params) == 1:
                return next(iter(params.values()))
            return None
        return params.get(reco_id)
    return params


def _get_params(source, file: str, reco_id: Optional[int]):
    """Return the parameter container for a requested file type.

    Args:
        source: Scan-like object, Study-like object, or mapping of parameters.
        file: Parameter file identifier (method, acqp, visu_pars, reco, subject).
        reco_id: Optional reconstruction id for reco/visu_pars.

    Returns:
        Parameter container or None if the file type is unsupported.
    """
    if isinstance(source, Mapping):
        return _get_params_from_map(source, file, reco_id)
    if file == "subject":
        return getattr(source, "subject", None)
    if file == "method":
        return source.method
    if file == "acqp":
        return source.acqp
    if file == "visu_pars":
        return source.get_reco(reco_id or 1).visu_pars
    if file == "reco":
        return source.get_reco(reco_id or 1).reco
    return None


def _resolve_value(
    source,
    sources,
    transforms: Dict[str, Callable],
    result_ctx: Dict[str, Any],
    ids: Dict[str, Optional[int]],
):
    """Resolve the first available value from a list of source descriptors.

    Args:
        source: Scan-like object or mapping of parameter containers.
        sources: Iterable of dicts with file/key(/reco_id) selectors or inline inputs.
        transforms: Transform registry for post-processing.
        result_ctx: Current output context for "ref" lookups.

    Returns:
        The first matching value, or None if nothing is found.
    """
    for src in sources:
        if "inputs" in src:
            inputs = _resolve_inputs(source, src["inputs"], transforms, result_ctx, ids)
            if "transform" in src:
                return _apply_inputs_transform(inputs, transforms, src["transform"])
            return inputs
        params = _get_params(source, src["file"], src.get("reco_id"))
        if params is None:
            continue
        key = src["key"]
        if hasattr(params, key):
            return getattr(params, key)
        if isinstance(params, Mapping):
            if key in params:
                return params[key]
        elif hasattr(params, "keys"):
            if key in params.keys():
                return params[key]
    return None


def _set_nested(d: Dict[str, Any], dotted: str, value: Any) -> None:
    """Assign a value into a nested dict using dotted keys.

    Args:
        d: Target dictionary to mutate.
        dotted: Dotted key path like "a.b.c".
        value: Value to set at the leaf key.
    """
    cur = d
    parts = dotted.split(".")
    for key in parts[:-1]:
        if key not in cur or not isinstance(cur[key], dict):
            cur[key] = {}
        cur = cur[key]
    cur[parts[-1]] = value


def _get_nested(d: Dict[str, Any], dotted: str) -> Any:
    """Fetch a nested value from a dict using dotted keys.

    Args:
        d: Dictionary to traverse.
        dotted: Dotted key path like "a.b.c".

    Returns:
        The nested value or None if the path does not exist.
    """
    cur: Any = d
    for key in dotted.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _apply_transform_chain(value: Any, transforms: Dict[str, Callable], names: Any) -> Any:
    """Apply one or more transform functions to a value.

    Args:
        value: Input value.
        transforms: Mapping of transform names to callables.
        names: Transform name or list of names; falsy means no-op.

    Returns:
        The transformed value.

    Notes:
        Transforms are applied even when ``value`` is ``None``. If a transform
        cannot handle ``None``, it should guard accordingly.
    """
    if not names:
        return value
    chain = names if isinstance(names, list) else [names]
    val = value
    for tname in chain:
        val = transforms[tname](val)
    return val


def _enforce_study_rules(spec: Mapping[str, Any]) -> None:
    has_subject_source = False
    disallowed_files: Set[str] = set()

    def check_sources(sources: List[Dict[str, Any]]) -> None:
        nonlocal has_subject_source
        for src in sources:
            file = src.get("file")
            if file == "subject":
                has_subject_source = True
            elif file is not None:
                disallowed_files.add(str(file))

    for _, rule in spec.items():
        if "sources" in rule:
            check_sources(rule.get("sources", []))
        if "inputs" in rule:
            for input_spec in rule.get("inputs", {}).values():
                if "sources" in input_spec:
                    check_sources(input_spec.get("sources", []))

    if disallowed_files:
        raise ValueError(
            "Study remap only supports subject sources; "
            f"found: {sorted(disallowed_files)}."
        )
    if not has_subject_source:
        raise ValueError("Study remap requires at least one subject source.")


def _is_study_like(source: Any) -> bool:
    return hasattr(source, "scans") and hasattr(source, "has_subject")


def _resolve_input(
    source,
    spec: Any,
    transforms: Dict[str, Callable],
    result_ctx: Dict[str, Any],
    ids: Dict[str, Optional[int]],
) -> Any:
    """Resolve a single input value based on a spec entry.

    Args:
        source: Scan-like object or mapping of parameter containers.
        spec: Input spec containing sources/const/ref/default/transform.
        transforms: Transform registry for post-processing.
        result_ctx: Current output context for "ref" lookups.

    Returns:
        The resolved input value, possibly transformed.
    """
    if isinstance(spec, str):
        if spec.startswith("$"):
            value = _resolve_context_value(spec[1:], result_ctx, ids)
            return None if value is _MISSING else value
        raise ValueError(f"Input shorthand must start with '$': {spec!r}")
    if not isinstance(spec, dict):
        raise ValueError(f"Input spec must be a mapping or $var: {spec!r}")
    if "const" in spec:
        return spec["const"]
    if "ref" in spec:
        return _get_nested(result_ctx, spec["ref"])

    raw = _resolve_value(source, spec.get("sources", []), transforms, result_ctx, ids)
    if raw is None:
        if "default" in spec:
            raw = spec["default"]
        elif spec.get("required", False):
            raise KeyError(f"Required input missing: {spec}")
        else:
            return None

    return _apply_transform_chain(raw, transforms, spec.get("transform"))


def _resolve_inputs(
    source,
    inputs_spec: Dict[str, Any],
    transforms: Dict[str, Callable],
    result_ctx: Dict[str, Any],
    ids: Dict[str, Optional[int]],
) -> Dict[str, Any]:
    """Resolve a dict of input values for a rule.

    Args:
        source: Scan-like object or mapping of parameter containers.
        inputs_spec: Mapping of input names to input specs.
        transforms: Transform registry for post-processing.
        result_ctx: Current output context for "ref" lookups.

    Returns:
        Mapping of input names to resolved values.
    """
    inputs: Dict[str, Any] = {}
    for name, spec in inputs_spec.items():
        inputs[name] = _resolve_input(source, spec, transforms, result_ctx, ids)
    return inputs


def _apply_inputs_transform(
    inputs: Dict[str, Any],
    transforms: Dict[str, Callable],
    name: Union[str, List[str]],
) -> Any:
    if isinstance(name, list):
        if not name:
            raise ValueError("Transform chain cannot be empty.")
        head, *tail = name
        value = _apply_inputs_transform(inputs, transforms, head)
        return _apply_transform_chain(value, transforms, tail)

    transform = transforms[name]
    signature = inspect.signature(transform)
    params = signature.parameters
    var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    if not var_kw:
        expected = {
            p.name
            for p in params.values()
            if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        }
        required = {
            p.name
            for p in params.values()
            if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
            and p.default is inspect._empty
        }
        extra = set(inputs.keys()) - expected
        missing = required - set(inputs.keys())
        if extra or missing:
            raise ValueError(
                f"Transform {name!r} kwargs mismatch. "
                f"extra={sorted(extra)} missing={sorted(missing)}"
            )
    return transform(**inputs)


def map_parameters(
    source,
    spec: Mapping[str, Any],
    transforms: Optional[Dict[str, Callable]] = None,
    *,
    validate: bool = False,
    context_map: Optional[Union[str, Path]] = None,
    context: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Map parameters to a nested dict according to spec rules.

    Args:
        source: Scan/Study-like object or mapping of parameter containers.
        spec: Mapping of output keys to resolution rules.
        transforms: Transform registry used by rules (optional).
        validate: If True, validate the spec before mapping.
        context_map: Optional context map override.
        context: Optional context values (e.g., scan_id/reco_id).

    Returns:
        Nested dictionary of mapped outputs.

    Notes:
        Transforms are invoked even when the resolved value is ``None``. Make
        sure transform functions handle ``None`` when missing data is expected.
    """
    if validate:
        validate_spec(spec)
    if _is_study_like(source):
        _enforce_study_rules(spec)
    if transforms is None:
        transforms = {}
    map_data = _load_map_data(spec, context_map=context_map)
    ids = _get_source_ids(source, context=context)
    result: Dict[str, Any] = {}
    for out_key, rule in spec.items():
        if out_key == "__meta__":
            continue
        try:
            if "inputs" in rule:
                inputs = _resolve_inputs(source, rule["inputs"], transforms, result, ids)
                if "transform" in rule:
                    val = _apply_inputs_transform(inputs, transforms, rule["transform"])
                else:
                    val = inputs
            elif "sources" in rule:
                raw = _resolve_value(source, rule.get("sources", []), transforms, result, ids)
                val = _apply_transform_chain(raw, transforms, rule.get("transform"))
            elif "const" in rule:
                val = _apply_transform_chain(rule.get("const"), transforms, rule.get("transform"))
            elif "ref" in rule:
                val = _apply_transform_chain(_get_nested(result, rule["ref"]), transforms, rule.get("transform"))
            else:
                val = _apply_transform_chain(rule.get("default"), transforms, rule.get("transform"))

            if "." in out_key:
                _set_nested(result, out_key, val)
            else:
                result[out_key] = val
        except Exception as exc:
            msg = f"Error mapping {out_key!r} with rule {rule!r}: {exc}"
            raise type(exc)(msg) from exc
    if map_data:
        result = _apply_map_rules(result, map_data, source, context=context)
    return result


def load_context_map(path: Union[str, Path]) -> Dict[str, Any]:
    map_data, _ = load_context_map_data(path)
    return map_data


def load_context_map_data(
    path: Union[str, Path],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    resolved = _resolve_map_path(path, base=None)
    if resolved is None:
        return {}, {}
    data = _read_map_file(resolved)
    return _split_map_data(data)


def load_context_map_meta(path: Union[str, Path]) -> Dict[str, Any]:
    _, meta = load_context_map_data(path)
    return meta


def get_selector_keys(map_data: Mapping[str, Any], *, target: Optional[str] = None) -> List[str]:
    selectors: List[str] = []
    for out_key, raw_rule in map_data.items():
        if not _rule_applies_to_target(raw_rule, target):
            continue
        if _is_selector_rule(raw_rule):
            selectors.append(out_key)
    return selectors


def matches_context_map_selectors(
    result: Union[Mapping[str, Any], Tuple[Mapping[str, Any], Mapping[str, Any]]],
    map_data: Mapping[str, Any],
    *,
    target: Optional[str] = None,
) -> bool:
    selector_keys = get_selector_keys(map_data, target=None)
    if not selector_keys:
        return True
    for key in selector_keys:
        if not _selector_value_present(result, key):
            return False
    return True


def _selector_value_present(
    result: Union[Mapping[str, Any], Tuple[Mapping[str, Any], Mapping[str, Any]]],
    out_key: str,
) -> bool:
    results: Iterable[Mapping[str, Any]]
    if isinstance(result, tuple):
        results = result
    else:
        results = (result,)
    for item in results:
        found, value = _get_output_value(dict(item), out_key)
        if found and value is not None:
            return True
    return False


def apply_context_map(
    result: Mapping[str, Any],
    map_data: Mapping[str, Any],
    *,
    target: Optional[str],
    context: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    filtered = _filter_map_data(map_data, target=target)
    if not filtered:
        return dict(result)
    return _apply_map_rules(dict(result), filtered, None, context=context)


def _load_map_data(
    spec: Mapping[str, Any],
    *,
    context_map: Optional[Union[str, Path]],
) -> Dict[str, Any]:
    override_path = _resolve_map_path(context_map, base=None)
    if override_path is not None:
        return _read_map_file(override_path)
    return {}


def _resolve_map_path(
    value: Optional[Union[str, Path]],
    *,
    base: Optional[Path],
) -> Optional[Path]:
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        if base is not None:
            path = (base / path).resolve()
        else:
            path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def _read_map_file(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    validate_map_data(data)
    return dict(data) if isinstance(data, Mapping) else {}


def _split_map_data(data: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    meta: Dict[str, Any] = {}
    raw_meta = data.get("__meta__")
    if isinstance(raw_meta, Mapping):
        meta = dict(raw_meta)
    rules = {key: value for key, value in data.items() if key != "__meta__"}
    return rules, meta


def _apply_map_rules(
    result: Dict[str, Any],
    map_data: Dict[str, Any],
    source: Any,
    *,
    context: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    ids = _get_source_ids(source, context=context)
    base = dict(result)
    for out_key, raw_rule in map_data.items():
        rules = _normalize_map_rules(raw_rule)
        if not rules:
            continue
        found, current = _get_output_value(base, out_key)
        for rule in rules:
            if "when" in rule and not _matches_when(rule["when"], base, ids):
                continue
            new_value, has_value = _resolve_rule_value(rule, current if found else None)
            if not has_value:
                break
            override = bool(rule.get("override", True))
            if override or not found or current is None:
                _set_nested(result, out_key, new_value)
                found = True
                current = new_value
            break
    return result


def _normalize_map_rules(raw_rule: Any) -> List[Dict[str, Any]]:
    if isinstance(raw_rule, list):
        rules = [dict(rule) for rule in raw_rule if isinstance(rule, Mapping)]
        return _expand_case_rules(rules)
    if isinstance(raw_rule, Mapping):
        return _expand_case_rules([dict(raw_rule)])
    raise ValueError("Map rule must be a mapping or list of mappings.")


def _is_selector_rule(raw_rule: Any) -> bool:
    return any(rule.get("selector") for rule in _iter_rule_objects(raw_rule))


def _rule_targets(raw_rule: Any) -> Set[str]:
    targets: Set[str] = set()
    for rule in _iter_rule_objects(raw_rule):
        value = rule.get("target")
        if isinstance(value, str):
            targets.add(value)
    return targets


def _iter_rule_objects(raw_rule: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(raw_rule, Mapping):
        yield raw_rule
        cases = raw_rule.get("cases")
        if isinstance(cases, list):
            for case in cases:
                yield from _iter_rule_objects(case)
    elif isinstance(raw_rule, list):
        for rule in raw_rule:
            yield from _iter_rule_objects(rule)


def _expand_case_rules(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    expanded: List[Dict[str, Any]] = []
    for rule in rules:
        expanded.extend(_expand_rule_cases(rule))
    return expanded


def _expand_rule_cases(rule: Dict[str, Any]) -> List[Dict[str, Any]]:
    cases = rule.get("cases")
    if not isinstance(cases, list):
        return [dict(rule)]
    parent = dict(rule)
    parent.pop("cases", None)
    expanded: List[Dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, Mapping):
            continue
        merged = _merge_case_rule(parent, case)
        if "cases" in merged:
            expanded.extend(_expand_rule_cases(merged))
        else:
            expanded.append(merged)
    if _rule_has_value(parent):
        expanded.append(parent)
    return expanded


def _merge_case_rule(parent: Mapping[str, Any], case: Mapping[str, Any]) -> Dict[str, Any]:
    merged = dict(parent)
    parent_when = parent.get("when")
    case_when = case.get("when")
    if isinstance(parent_when, Mapping) and isinstance(case_when, Mapping):
        merged["when"] = {**parent_when, **case_when}
    elif case_when is not None:
        merged["when"] = case_when
    elif parent_when is not None:
        merged["when"] = parent_when
    for key, value in case.items():
        if key == "when":
            continue
        merged[key] = value
    return merged


def _rule_has_value(rule: Mapping[str, Any]) -> bool:
    if "value" in rule:
        return True
    if "values" in rule:
        return isinstance(rule.get("values"), Mapping)
    if "default" in rule and "when" not in rule:
        return True
    rule_type = rule.get("type")
    if rule_type == "const":
        return "value" in rule
    if rule_type == "mapping":
        return isinstance(rule.get("values"), Mapping)
    return False


def _rule_applies_to_target(raw_rule: Any, target: Optional[str]) -> bool:
    if target is None:
        return True
    targets = _rule_targets(raw_rule)
    if not targets:
        return target == "info_spec"
    return target in targets


def _filter_map_data(map_data: Mapping[str, Any], *, target: Optional[str]) -> Dict[str, Any]:
    if target is None:
        return dict(map_data)
    return {
        key: raw_rule
        for key, raw_rule in map_data.items()
        if _rule_applies_to_target(raw_rule, target)
    }


def _get_output_value(result: Dict[str, Any], out_key: str) -> Tuple[bool, Any]:
    if "." in out_key:
        value = _get_nested(result, out_key)
        return (value is not None), value
    if out_key in result:
        return True, result[out_key]
    return False, None


def _get_source_ids(source: Any, *, context: Optional[Mapping[str, Any]] = None) -> Dict[str, Optional[int]]:
    scan_id = getattr(source, "scan_id", None)
    reco_id = getattr(source, "reco_id", None)
    if context:
        if "scan_id" in context:
            scan_id = context.get("scan_id")
        if "reco_id" in context:
            reco_id = context.get("reco_id")
    return {
        "scanid": scan_id,
        "scan_id": scan_id,
        "recoid": reco_id,
        "reco_id": reco_id,
    }


def _matches_when(when: Any, result: Dict[str, Any], ids: Dict[str, Optional[int]]) -> bool:
    if not isinstance(when, Mapping):
        raise ValueError("when must be a mapping.")
    for key, cond in when.items():
        actual = _resolve_context_value(str(key), result, ids)
        if actual is _MISSING:
            return False
        if not _matches_condition(actual, cond):
            return False
    return True


def _resolve_context_value(key: str, result: Dict[str, Any], ids: Dict[str, Optional[int]]) -> Any:
    normalized = key.lower()
    if normalized in ids and ids[normalized] is not None:
        return ids[normalized]
    if "." in key:
        value = _get_nested(result, key)
        return value if value is not None else _MISSING
    if key in result:
        return result[key]
    return _MISSING


def _matches_condition(value: Any, cond: Any) -> bool:
    if isinstance(cond, Mapping):
        for op, expected in cond.items():
            if op == "not":
                if _matches_condition(value, expected):
                    return False
                continue
            if op == "in":
                if not isinstance(expected, (list, tuple, set)):
                    expected = [expected]
                if isinstance(value, (list, tuple, set)):
                    if not any(item in expected for item in value):
                        return False
                else:
                    if value not in expected:
                        return False
                continue
            if op == "regex":
                if not re.search(str(expected), str(value)):
                    return False
                continue
            if value != expected:
                return False
        return True
    return value == cond


def _resolve_rule_value(rule: Mapping[str, Any], current: Any) -> Tuple[Any, bool]:
    if "default" in rule and "when" not in rule:
        return rule.get("default"), True
    rule_type = rule.get("type")
    if rule_type is None:
        if "values" in rule:
            rule_type = "mapping"
        elif "value" in rule:
            rule_type = "const"
    if rule_type == "mapping":
        mapping = rule.get("values")
        if not isinstance(mapping, Mapping):
            raise ValueError("map values must be a mapping.")
        has_default = "default" in rule
        default = rule.get("default")
        if current is None and not has_default and None not in mapping:
            return current, False
        return _map_lookup(current, mapping, default, has_default=has_default), True
    if rule_type == "const":
        return rule.get("value"), True
    if "value" in rule:
        return rule.get("value"), True
    if "default" in rule:
        return rule.get("default"), True
    return current, False


def _map_lookup(
    value: Any,
    mapping: Mapping[Any, Any],
    default: Any,
    *,
    has_default: bool,
) -> Any:
    if isinstance(value, (list, tuple)):
        mapped = [
            _map_lookup(item, mapping, default, has_default=has_default) for item in value
        ]
        return type(value)(mapped)
    if value in mapping:
        return mapping[value]
    if not isinstance(value, str):
        as_str = str(value)
        if as_str in mapping:
            return mapping[as_str]
    if has_default:
        return default
    return value


__all__ = [
    "load_spec",
    "map_parameters",
    "load_context_map",
    "get_selector_keys",
    "matches_context_map_selectors",
    "apply_context_map",
    "load_context_map_data",
    "load_context_map_meta",
]
