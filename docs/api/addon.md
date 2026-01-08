# addon (Python API)

Manage installed addon assets used by brkraw mapping logic.

Addons are data files installed under a configuration root and used by:
- info specs
- metadata specs
- rules
- pruner specs
- transforms referenced by specs

The addon API supports installation, listing, removal, and reference resolution.

---

## Equivalent CLI command

`brkraw addon`

---

## Entry points

```python
from brkraw.apps import addon
```

Public functions:

- `addon.add(path, root=None) -> List[pathlib.Path]`
- `addon.add_rule_data(rule_data, *, filename=None, source_path=None, root=None) -> List[pathlib.Path]`
- `addon.add_spec_data(spec_data, *, filename=None, source_path=None, root=None, transforms_dir=None) -> List[pathlib.Path]`
- `addon.add_pruner_spec_data(spec_data, *, filename=None, source_path=None, root=None) -> List[pathlib.Path]`
- `addon.install_defaults(root=None) -> List[pathlib.Path]`
- `addon.list_installed(root=None) -> Dict[str, List[Dict[str, str]]]`
- `addon.remove(filename, *, root=None, kind=None, force=False) -> List[pathlib.Path]`
- `addon.resolve_spec_reference(use, *, category=None, version=None, root=None) -> pathlib.Path`
- `addon.resolve_pruner_spec_reference(use, *, version=None, root=None) -> pathlib.Path`

---

## Configuration root

All addon installation and lookup happens under a configuration root.

Many functions accept `root`:

- `root=None` uses the default resolved root from brkraw configuration
- `root=/custom/root` scopes installation and listing to that root

---

## Install an addon file

### Install a YAML file (auto-classify)

`addon.add()` installs a YAML file and automatically classifies it as one of:

- rule
- spec (info_spec or metadata_spec)
- pruner spec

```python
from brkraw.apps import addon

installed = addon.add("/path/to/file.yaml")
for path in installed:
    print(path)
```

Behavior:

- the YAML content is loaded and validated
- the target install location is chosen based on the detected type
- transforms referenced by specs may be installed automatically (see below)

### Install from in-memory mappings

Install a spec mapping:

```python
from brkraw.apps import addon

installed = addon.add_spec_data(
    spec_data,
    filename="my_spec.yaml",
)
```

Install a rule mapping:

```python
installed = addon.add_rule_data(
    rule_data,
    filename="my_rule.yaml",
)
```

Install a pruner spec mapping:

```python
installed = addon.add_pruner_spec_data(
    pruner_spec_data,
    filename="my_pruner.yaml",
)
```

Notes:

- `filename` must end with `.yaml` or `.yml`
- if `filename` is omitted, `source_path` is required

---

## Spec transforms installation

Specs may declare transforms via `__meta__.transforms_source` (at the root
or within sections). When installing a spec with `add_spec_data()`:

- referenced transform scripts are installed into the transforms directory
- the spec mapping may be rewritten so `transforms_source` points to the
  installed transform paths relative to the spec

If transforms are referenced but cannot be resolved to a readable file,
installation fails with `FileNotFoundError`.

---

## Install bundled defaults

Install brkraw bundled default specs, rules, and pruner specs:

```python
from brkraw.apps import addon

installed = addon.install_defaults()
print(len(installed))
```

This is typically used when preparing a fresh configuration root.

---

## List installed addons

List installed specs, pruner specs, rules, and transforms:

```python
from brkraw.apps import addon

data = addon.list_installed()
print(data.keys())
```

Returned keys include:

- `specs`
- `pruner_specs`
- `rules`
- `transforms`

Each item is returned as a dictionary of string fields suitable for
display or serialization.

Notes:

- spec categories may be inferred from rules when `__meta__.category` is missing
- transforms are listed with their referencing spec labels when available

---

## Remove installed addons

Remove an installed file by filename:

```python
from brkraw.apps import addon

removed = addon.remove("my_spec.yaml")
for path in removed:
    print(path)
```

Important:

- `filename` matches the installed file name, not `__meta__.name`

### Restrict removal kind

Optionally restrict removal to one kind:

```python
addon.remove("my_rule.yaml", kind="rule")
```

Valid kinds:

- `spec`
- `pruner`
- `rule`
- `transform`

### Dependency checks and force removal

Removal checks whether the target is referenced by other installed assets.

Examples of dependency warnings:

- a spec referenced by rules
- a spec included by another spec
- a transform referenced by a spec

If dependencies are found:

- `force=False` raises `RuntimeError`
- `force=True` removes the file anyway

```python
addon.remove("my_spec.yaml", force=True)
```

---

## Resolve spec references

Rules and other assets may reference specs either by path-like values or
by logical names.

Resolve a spec reference:

```python
from brkraw.apps import addon

spec_path = addon.resolve_spec_reference(
    "MySpecName",
    category="metadata_spec",
)
print(spec_path)
```

Behavior:

- if `use` looks like a path, it is resolved under the root
- otherwise, it is treated as a logical name and the latest version is selected
- if multiple specs share the latest version, resolution fails with `ValueError`

Resolve a specific version:

```python
spec_path = addon.resolve_spec_reference(
    "MySpecName",
    category="metadata_spec",
    version="1.2.0",
)
```

Notes:

- `category` filtering is optional but recommended for disambiguation
- missing specs raise `FileNotFoundError`

---

## Resolve pruner spec references

Resolve a pruner spec by name (latest version by default):

```python
from brkraw.apps import addon

path = addon.resolve_pruner_spec_reference("minimal_share")
print(path)
```

Resolve a specific version:

```python
path = addon.resolve_pruner_spec_reference(
    "minimal_share",
    version="1.0.0",
)
```

Missing names or versions raise `FileNotFoundError`.
Tied versions raise `ValueError`.

---

## Design notes

- Addon installation is file-based and deterministic under the chosen root.
- YAML inputs are validated before writing.
- Removal is conservative by default and blocks when dependencies are detected
  unless forced.
- Reference resolution prefers the latest version and rejects ambiguous ties.
