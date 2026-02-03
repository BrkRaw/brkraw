from pathlib import Path

import yaml

from brkraw.apps.addon import dependencies
from brkraw.core import config as config_core


def _write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_rules_using_spec_matches_full_path(tmp_path: Path) -> None:
    paths = config_core.ensure_initialized(root=tmp_path, create_config=False)
    target = paths.specs_dir / "ns" / "info_spec.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}", encoding="utf-8")

    (paths.specs_dir / "info_spec.yaml").write_text("{}", encoding="utf-8")

    _write_yaml(
        paths.rules_dir / "rule1.yaml",
        {"info_spec": [{"name": "base", "use": "info_spec.yaml"}]},
    )
    _write_yaml(
        paths.rules_dir / "rule2.yaml",
        {"info_spec": [{"name": "ns", "use": "specs/ns/info_spec.yaml"}]},
    )

    used_by = dependencies.rules_using_spec(target, paths.rules_dir, root=paths.root)

    assert used_by == {"rule2.yaml"}


def test_specs_including_spec_matches_resolved_path(tmp_path: Path) -> None:
    paths = config_core.ensure_initialized(root=tmp_path, create_config=False)
    target = paths.specs_dir / "ns" / "info_spec.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}", encoding="utf-8")

    _write_yaml(
        paths.specs_dir / "parent.yaml",
        {"__meta__": {"include": ["ns/info_spec.yaml"]}},
    )
    _write_yaml(
        paths.specs_dir / "other.yaml",
        {"__meta__": {"include": ["info_spec.yaml"]}},
    )

    included_by = dependencies.specs_including_spec(target, paths.specs_dir)

    assert included_by == {"parent.yaml"}


def test_warn_dependencies_ignores_hook_namespace(tmp_path: Path) -> None:
    paths = config_core.ensure_initialized(root=tmp_path, create_config=False)
    namespace = "dti"
    target = paths.specs_dir / namespace / "info_spec.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}", encoding="utf-8")

    (paths.rules_dir / namespace).mkdir(parents=True, exist_ok=True)
    _write_yaml(
        paths.rules_dir / namespace / "dti.yaml",
        {"info_spec": [{"name": "dti", "use": "specs/dti/info_spec.yaml"}]},
    )

    warned = dependencies.warn_dependencies(
        target,
        kind="spec",
        root=paths.root,
        ignore_rules_dir=paths.rules_dir / namespace,
        ignore_specs_dir=paths.specs_dir / namespace,
    )

    assert warned is False

    _write_yaml(
        paths.rules_dir / "external.yaml",
        {"info_spec": [{"name": "ext", "use": "specs/dti/info_spec.yaml"}]},
    )

    warned = dependencies.warn_dependencies(
        target,
        kind="spec",
        root=paths.root,
        ignore_rules_dir=paths.rules_dir / namespace,
        ignore_specs_dir=paths.specs_dir / namespace,
    )

    assert warned is True
