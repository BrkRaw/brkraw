from __future__ import annotations


def test_context_map_cases_mapping() -> None:
    from brkraw.specs.remapper import apply_context_map

    result = {"Subject": {"ID": "XXX"}, "ScanID": 1, "OutputKey": 1}
    map_data = {
        "OutputKey": {
            "when": {"Subject.ID": "XXX"},
            "type": "mapping",
            "override": True,
            "cases": [
                {"when": {"ScanID": 1}, "values": {1: "A"}},
                {"when": {"ScanID": 2}, "values": {1: "B"}},
            ],
        }
    }

    mapped = apply_context_map(result, map_data, target="info_spec")
    assert mapped["OutputKey"] == "A"


def test_context_map_cases_fallback_to_parent() -> None:
    from brkraw.specs.remapper import apply_context_map

    result = {"Subject": {"ID": "XXX"}, "ScanID": 3, "OutputKey": 1}
    map_data = {
        "OutputKey": {
            "when": {"Subject.ID": "XXX"},
            "type": "mapping",
            "override": True,
            "values": {1: "P"},
            "cases": [
                {"when": {"ScanID": 1}, "values": {1: "A"}},
                {"when": {"ScanID": 2}, "values": {1: "B"}},
            ],
        }
    }

    mapped = apply_context_map(result, map_data, target="info_spec")
    assert mapped["OutputKey"] == "P"


def test_context_map_cases_validate() -> None:
    from brkraw.specs.remapper import validate_map_data

    map_data = {
        "OutputKey": {
            "when": {"Subject.ID": "XXX"},
            "type": "mapping",
            "override": True,
            "cases": [
                {"when": {"ScanID": 1}, "values": {1: "A"}},
                {"when": {"ScanID": 2}, "values": {1: "B"}},
            ],
        }
    }

    errors = validate_map_data(map_data, raise_on_error=False)
    assert errors == []
