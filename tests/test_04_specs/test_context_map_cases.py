"""The 0.5 "cases" examples, rewritten for context map v3 (0.6.0).

0.5 wrote per-scan alternatives with ``type: mapping`` + ``cases`` and changed
the original key in place. In 0.6.0 the same result is a first-match list in a
namespace field; the original value stays as it was, and the old words are
refused with a pointer to the new form.
"""
from __future__ import annotations

import pytest

from brkraw.specs.context_map import ContextMapError, plan_scan, validate_context_map

INFO = {"Subject": {"ID": "XXX"}, "Study": {"ID": "S1"}, "OutputKey": 1}

V3_MAP = {
    "__meta__": {"category": "context_map"},
    "out": {
        "key": [
            {"when": {"Subject.ID": "XXX", "ScanID": 1}, "from": "OutputKey", "map": {1: "A"}},
            {"when": {"Subject.ID": "XXX", "ScanID": 2}, "from": "OutputKey", "map": {1: "B"}},
            {"when": {"Subject.ID": "XXX"}, "from": "OutputKey", "map": {1: "P"}},
        ]
    },
}


def test_cases_become_a_first_match_list() -> None:
    validate_context_map(V3_MAP)
    assert plan_scan(INFO, V3_MAP, scan_id=1).namespaces["out"]["key"] == "A"
    assert plan_scan(INFO, V3_MAP, scan_id=2).namespaces["out"]["key"] == "B"


def test_fallback_is_the_last_item() -> None:
    assert plan_scan(INFO, V3_MAP, scan_id=3).namespaces["out"]["key"] == "P"
    assert INFO["OutputKey"] == 1


def test_old_cases_syntax_is_refused() -> None:
    old = {
        "OutputKey": {
            "when": {"Subject.ID": "XXX"},
            "type": "mapping",
            "override": True,
            "cases": [{"when": {"ScanID": 1}, "values": {1: "A"}}],
        }
    }
    with pytest.raises(ContextMapError, match="old context map syntax"):
        validate_context_map({"__meta__": {"category": "context_map"}, "old": old})
