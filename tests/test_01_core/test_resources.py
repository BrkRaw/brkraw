def test_schema_resources_loadable() -> None:
    from brkraw.specs.meta import validator as meta_validator
    from brkraw.specs.pruner import validator as pruner_validator
    from brkraw.specs.remapper import validator as remapper_validator
    from brkraw.specs.rules import validator as rules_validator

    assert isinstance(meta_validator._load_schema(), dict)
    assert isinstance(remapper_validator._load_schema(), dict)
    assert isinstance(remapper_validator._load_map_schema(), dict)
    assert isinstance(pruner_validator._load_schema(None), dict)
    assert isinstance(rules_validator._load_schema(), dict)
