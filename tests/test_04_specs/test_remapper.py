from __future__ import annotations


def _spec_meta(name: str) -> dict:
    return {
        "name": name,
        "category": "info_spec",
        "version": "0",
        "description": "Remapper spec test.",
    }


def test_remapper_sources_mapping() -> None:
    from brkraw.specs.remapper import map_parameters

    spec = {
        "__meta__": _spec_meta("sources"),
        "FieldName": {
            "sources": [{"file": "method", "key": "Param"}],
        },
    }
    source = {"method": {"Param": 7}}

    result = map_parameters(source, spec, validate=True)
    assert result["FieldName"] == 7


def test_remapper_top_level_const_ref_mapping() -> None:
    from brkraw.specs.remapper import map_parameters

    spec = {
        "__meta__": _spec_meta("const_ref"),
        "ConstValue": {"const": 123},
        "CopyValue": {"ref": "ConstValue"},
    }

    result = map_parameters({}, spec, validate=True)
    assert result["ConstValue"] == 123
    assert result["CopyValue"] == 123


def test_remapper_inputs_const_ref_mapping() -> None:
    from brkraw.specs.remapper import map_parameters

    def add(a: int, b: int) -> int:
        return a + b

    spec = {
        "__meta__": _spec_meta("inputs"),
        "ConstValue": {"const": 5},
        "Combined": {
            "inputs": {
                "a": {"sources": [{"file": "method", "key": "Param"}]},
                "b": {"ref": "ConstValue"},
            },
            "transform": "add",
        },
    }
    source = {"method": {"Param": 7}}

    result = map_parameters(source, spec, transforms={"add": add}, validate=True)
    assert result["Combined"] == 12


def test_remapper_top_level_const_ref_validate() -> None:
    from brkraw.specs.remapper import validate_spec

    spec = {
        "__meta__": _spec_meta("const_ref_validate"),
        "ConstValue": {"const": 123},
        "CopyValue": {"ref": "ConstValue"},
    }

    errors = validate_spec(spec, raise_on_error=False)
    assert errors == []


def test_remapper_validator_rejects_missing_rule() -> None:
    from brkraw.specs.remapper import validate_spec

    spec = {
        "__meta__": _spec_meta("invalid_rule"),
        "Broken": {"transform": "noop"},
    }

    errors = validate_spec(spec, raise_on_error=False)
    assert errors
    assert any(
        "requires sources, inputs, const, or ref" in error
        or "is not valid under any of the given schemas" in error
        for error in errors
    )
