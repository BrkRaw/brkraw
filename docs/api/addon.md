# API: Addon

Programmatic access to addon installation and lookup utilities.

Module: `brkraw.apps.addon`

## add

Install a spec or rule YAML file.

```python
from brkraw.apps import addon

installed = addon.add("path/to/spec.yaml")
```

Returns:

- List of installed file paths.

Errors:

- `FileNotFoundError`: source file not found.

- `ValueError`: unsupported file type or invalid YAML content.

Notes:

- Pruner specs (`pruner_spec`) are installed under `pruner_specs/`.

## list_installed

List installed specs, rules, and transforms.

```python
from brkraw.apps import addon

data = addon.list_installed()
print(data["specs"])
print(data["rules"])
print(data["transforms"])
```

Returns:

- Dict with keys `specs`, `rules`, `transforms`.

- Pruner specs are listed under `pruner_specs`.

- Each list contains dicts with fields such as `file`, `name`, `version`, `description`, `category`.

## remove

Remove an installed spec/rule/transform by filename (not `__meta__.name`).

```python
from brkraw.apps import addon

addon.remove("metadata_common.yaml", kind="spec")
addon.remove("prune.yaml", kind="pruner")
addon.remove("mrs_transforms.py", kind="transform")
```

Returns:

- List of removed file paths.

Errors:

- `FileNotFoundError`: no matching file found.

- `RuntimeError`: dependencies detected (unless `force=True`).

- `ValueError`: invalid `kind`.

## resolve_spec_reference

Resolve a spec by name or path.

```python
from brkraw.apps import addon

spec_path = addon.resolve_spec_reference(
    "metadata_common",
    category="metadata_spec",
    version="1.0.0",
)
```

Returns:

- Resolved spec path.

Errors:

- `FileNotFoundError`: spec not found for name/category/version.

- `ValueError`: multiple matches for the same name/version.

## resolve_pruner_spec_reference

Resolve a pruner spec by name or path.

```python
from brkraw.apps import addon

spec_path = addon.resolve_pruner_spec_reference("pruner_default", version="1.0.0")
```
