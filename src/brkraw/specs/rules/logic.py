from __future__ import annotations

from pathlib import Path
from typing import Any, List, Dict, Optional, Union

import yaml

from ...core import config as config_module
from ..remapper import load_spec, map_parameters
from .validator import validate_rules
import logging

logger = logging.getLogger(__name__)

RULE_CATEGORIES = ("info_spec", "metadata_spec", "converter_hook")
SPEC_CATEGORIES = ("info_spec", "metadata_spec")


def _iter_rule_files(rules_dir: Path) -> List[Path]:
    if not rules_dir.exists():
        return []
    files = list(rules_dir.rglob("*.yaml")) + list(rules_dir.rglob("*.yml"))
    return sorted({p.resolve() for p in files})


def _load_rule_file(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"Rule file must be a mapping: {path}")
    return data


def _resolve_spec_path(use: str, base: Path) -> Path:
    candidate = Path(use)
    if candidate.is_absolute():
        return candidate
    if candidate.parts and candidate.parts[0] == "specs":
        return base / candidate
    return base / "specs" / candidate


def _resolve_rule_use(rule: Dict[str, Any], *, base: Path) -> Optional[Path]:
    use = rule.get("use")
    if not isinstance(use, str):
        return None
    version = rule.get("version") if isinstance(rule.get("version"), str) else None
    category = rule.get("__category__") if isinstance(rule.get("__category__"), str) else None
    try:
        from ...apps.addon.core import resolve_spec_reference
    except Exception:
        resolve_spec_reference = None
    if resolve_spec_reference is None:
        return _resolve_spec_path(use, base)
    return resolve_spec_reference(use, category=category, version=version, root=base)


def _resolve_operand(value: Any, bindings: Dict[str, Any]) -> Any:
    if isinstance(value, str) and value.startswith("$"):
        return bindings.get(value[1:])
    return value


def _eval_expr(expr: Any, bindings: Dict[str, Any]) -> bool:
    if expr is None:
        return True
    if not isinstance(expr, dict):
        raise ValueError(f"Rule if must be a mapping, got {type(expr)!r}")
    if len(expr) != 1:
        raise ValueError("Rule if must contain a single operator.")
    op, args = next(iter(expr.items()))
    if op == "any":
        return any(_eval_expr(item, bindings) for item in args)
    if op == "all":
        return all(_eval_expr(item, bindings) for item in args)
    if op == "not":
        return not _eval_expr(args, bindings)
    if op == "always":
        if not isinstance(args, bool):
            raise ValueError("always expects a boolean.")
        return args

    if not isinstance(args, (list, tuple)) or len(args) != 2:
        raise ValueError(f"Operator {op!r} requires two arguments.")
    left = _resolve_operand(args[0], bindings)
    right = _resolve_operand(args[1], bindings)

    if left is None or right is None:
        if op == "eq":
            return left == right
        if op == "ne":
            return left != right
        return False

    if op == "eq":
        return left == right
    if op == "ne":
        return left != right
    if op == "in":
        try:
            return left in right
        except TypeError:
            return False
    if op == "regex":
        import re
        if left is None:
            return False
        return re.search(str(right), str(left)) is not None
    if op == "startswith":
        if left is None:
            return False
        return str(left).startswith(str(right))
    if op == "contains":
        if left is None:
            return False
        if isinstance(left, (list, tuple, set)):
            return right in left
        return str(right) in str(left)
    if op == "gt":
        return left > right
    if op == "ge":
        return left >= right
    if op == "lt":
        return left < right
    if op == "le":
        return left <= right
    raise ValueError(f"Unsupported operator: {op}")


def _load_rule_transforms(rule: Dict[str, Any], base: Path) -> Dict[str, Any]:
    transforms = rule.get("__transforms__")
    if isinstance(transforms, dict):
        return transforms
    category = rule.get("__category__") if isinstance(rule.get("__category__"), str) else None
    if category and category not in SPEC_CATEGORIES:
        return {}
    use = rule.get("use")
    if not isinstance(use, str):
        return {}
    spec_path = rule.get("__spec_path__")
    if isinstance(spec_path, Path):
        _, transforms = load_spec(spec_path, validate=False)
        return transforms
    spec_path = _resolve_rule_use(rule, base=base)
    if isinstance(spec_path, Path) and spec_path.exists():
        _, transforms = load_spec(spec_path, validate=False)
        return transforms
    return {}


def rule_matches(
    source: Any,
    rule: Dict[str, Any],
    *,
    base: Path,
) -> bool:
    when = rule.get("when")
    if when is None:
        logger.debug("Rule %r: no 'when' clause, matches by default.", rule.get("name"))
        return True
    if not isinstance(when, dict):
        raise ValueError("Rule 'when' must be a mapping.")
    transforms = _load_rule_transforms(rule, base)
    bindings = map_parameters(source, when, transforms, validate=False)
    logger.debug("Rule %r: when bindings=%s", rule.get("name"), bindings)
    try:
        matched = _eval_expr(rule.get("if"), bindings)
        logger.debug(
            "Rule %r: bindings=%s if=%s matched=%s",
            rule.get("name"),
            bindings,
            rule.get("if"),
            matched,
        )
        return matched
    except Exception as exc:
        name = rule.get("name", "<unnamed>")
        raise ValueError(f"Rule {name!r} evaluation failed: {exc}") from exc


def select_rule_use(
    source: Any,
    rules: List[Dict[str, Any]],
    *,
    base: Path,
    resolve_paths: bool = True,
) -> Optional[Union[str, Path]]:
    selected: Optional[Union[str, Path]] = None
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        logger.debug("Evaluating rule %r (use=%r).", rule.get("name"), rule.get("use"))
        try:
            matched = rule_matches(source, rule, base=base)
        except Exception as exc:
            logger.debug(
                "Rule %r evaluation failed: %s",
                rule.get("name"),
                exc,
                exc_info=True,
            )
            continue
        logger.debug("Rule %r: match=%s", rule.get("name"), matched)
        if matched:
            use = rule.get("use")
            if isinstance(use, str):
                if not resolve_paths:
                    selected = use
                else:
                    spec_path = rule.get("__spec_path__")
                    if isinstance(spec_path, Path):
                        selected = spec_path
                    else:
                        selected = _resolve_spec_path(use, base)
                logger.debug("Rule %r matched, selected use=%r.", rule.get("name"), selected)
            else:
                logger.debug("Rule %r matched but has no usable 'use' entry.", rule.get("name"))
    logger.debug("Rule selection result: %r", selected)
    return selected


def load_rules(
    root: Optional[Union[str, Path]] = None,
    *,
    rules_dir: Optional[Path] = None,
    validate: bool = True,
) -> Dict[str, List[Dict[str, Any]]]:
    base = config_module.resolve_root(root)
    rules_path = rules_dir or (base / "rules")
    merged = {key: [] for key in RULE_CATEGORIES}
    transforms_cache: Dict[Path, Dict[str, Any]] = {}
    for path in _iter_rule_files(rules_path):
        data = _load_rule_file(path)
        if validate and data:
            validate_rules(data)
        for key in RULE_CATEGORIES:
            items = data.get(key, [])
            if items:
                if not isinstance(items, list):
                    raise ValueError(f"{path}: {key} must be a list.")
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    item["__category__"] = key
                    if key in SPEC_CATEGORIES:
                        use = item.get("use")
                        if not isinstance(use, str):
                            continue
                        spec_path = _resolve_rule_use(item, base=base)
                        if not isinstance(spec_path, Path) or not spec_path.exists():
                            if validate:
                                raise FileNotFoundError(spec_path)
                            continue
                        if spec_path not in transforms_cache:
                            _, transforms = load_spec(spec_path, validate=validate)
                            transforms_cache[spec_path] = transforms
                        item["__spec_path__"] = spec_path
                        item["__transforms__"] = transforms_cache[spec_path]
                merged[key].extend(items)
    return merged
