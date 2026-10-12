def test_schema_resources_loadable() -> None:
    from brkraw.specs.meta import validator as meta_validator
    from brkraw.specs.pruner import validator as pruner_validator
    from brkraw.specs.remapper import validator as remapper_validator
    from brkraw.specs.rules import validator as rules_validator

    assert isinstance(meta_validator._load_schema(), dict)
    assert isinstance(remapper_validator._load_schema(), dict)
    assert isinstance(pruner_validator._load_schema(None), dict)
    assert isinstance(rules_validator._load_schema(), dict)


def test_old_context_map_schema_is_removed() -> None:
    # BRK-0034 ②: the v2 map schema is gone with the old context map code
    from pathlib import Path

    import brkraw

    assert not (Path(brkraw.__file__).parent / "schema" / "context_map.yaml").exists()
