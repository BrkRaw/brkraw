# prune (Python API)

Create a pruned dataset zip for sharing or archiving, using a pruner spec.

Pruning makes Paravision datasets easier to share by:

- keeping only the files you need (or dropping sensitive/unnecessary files)
- optionally stripping JCAMP comment lines (`$$ ...`)
- optionally editing or deleting specific JCAMP parameters (via `update_params`)
- writing a clean zip with an optional top-level root directory

This API is designed to be used in scripts and pipelines. It is read-only
with respect to the input dataset and writes only the destination zip.

---

## Equivalent CLI command

`brkraw prune`

---

## Entry points

```python
from brkraw.specs.pruner.logic import (
    prune_dataset_to_zip,
    prune_dataset_to_zip_from_spec,
    load_prune_spec,
)
```

- Use `prune_dataset_to_zip()` when you want to specify rules directly.
- Use `prune_dataset_to_zip_from_spec()` when you already have a prune spec
  (mapping or YAML file).
- Use `load_prune_spec()` to load and validate a prune spec from YAML.

---

## Basic usage

### Prune using explicit rules

```python
from brkraw.specs.pruner.logic import prune_dataset_to_zip

out = prune_dataset_to_zip(
    source="/path/to/dataset",
    dest="out.zip",
    files=["method", "acqp", "reco", "visu_pars", "subject"],
    mode="keep",
)
print(out)
```

### Prune using a spec file

```python
from brkraw.specs.pruner.logic import prune_dataset_to_zip_from_spec

out = prune_dataset_to_zip_from_spec(
    "/path/to/prune_spec.yaml",
    source="/path/to/dataset",
    dest="out.zip",
)
print(out)
```

Notes:

- `source` and `dest` are required when using `prune_dataset_to_zip_from_spec()`.
- `spec` may be a YAML path or an in-memory mapping.

---

## What a pruner spec controls

A prune spec is a YAML mapping that defines:

- which files to keep or drop (`files` + `mode`)
- optional directory-level filters (`dirs`)
- optional JCAMP edits (`update_params`)
- optional root folder handling inside the zip (`add_root`, `root_name`)
- optional comment stripping for JCAMP files (`strip_jcamp_comments`)

`files` is required and must contain at least one selector.

Selectors match either:

- full dataset-relative paths (e.g. `pdata/1/visu_pars`)
- basenames only (e.g. `visu_pars`)

---

## keep vs drop

### mode: keep

Only files matching `files` are included.

### mode: drop

Files matching `files` are excluded, everything else is included.

If no files remain after applying rules, pruning fails with `ValueError`.

---

## Directory rules (dirs)

`dirs` allows filtering by directory names at specific path levels.

Each rule is a mapping:

- level: integer (1-based)
- dirs: list of directory names

Example: keep only scans 3 and 5 (level 1 is typically the scan folder level)

```python
from brkraw.specs.pruner.logic import prune_dataset_to_zip

out = prune_dataset_to_zip(
    source="/path/to/dataset",
    dest="out.zip",
    files=["method", "acqp", "visu_pars"],
    mode="keep",
    dirs=[
        {"level": 1, "dirs": [3, 5]},
    ],
)
```

Example: keep only reco folders 1 and 2 (level 3 is often the pdata level)

```python
out = prune_dataset_to_zip(
    source="/path/to/dataset",
    dest="out.zip",
    files=["method", "acqp", "visu_pars"],
    mode="keep",
    dirs=[
        {"level": 3, "dirs": [1, 2]},
    ],
)
```

Notes:

- `dirs` values are normalized to strings internally.
- In this API, `dirs` rules use the same `mode` as the prune operation.
  There is no per-rule mode.

---

## JCAMP parameter edits (update_params)

`update_params` allows editing or deleting JCAMP parameter keys in selected files.

Structure:

```python
update_params = {
    "subject": {
        "SUBJECT_id": None,
        "SUBJECT_name": None,
    },
    "method": {
        "Operator": None,
    },
}
```

Rules:

- The outer keys are basenames only (not full paths).
- If an included file has that basename, it will be rewritten in the output zip.
- Values are converted to strings internally (except `None`).
- If the value is `None`, the key is removed (or cleared depending on Parameters behavior).

Important:

- Updates require parsing the file as JCAMP parameters.
- If parsing fails, pruning fails with `ValueError`.
- Updates apply only to files that are selected into the zip.

Example:

```python
from brkraw.specs.pruner.logic import prune_dataset_to_zip

out = prune_dataset_to_zip(
    source="/path/to/dataset",
    dest="out.zip",
    files=["subject", "method", "acqp"],
    mode="keep",
    update_params={
        "subject": {"SUBJECT_id": None, "SUBJECT_name": None},
        "method": {"Operator": None},
    },
)
```

---

## Strip JCAMP comments

Some Paravision parameter files include comment lines starting with `$$`.
You can remove them from included JCAMP-like files.

Enable at call time:

```python
from brkraw.specs.pruner.logic import prune_dataset_to_zip

out = prune_dataset_to_zip(
    source="/path/to/dataset",
    dest="out.zip",
    files=["method", "acqp", "visu_pars"],
    mode="keep",
    strip_jcamp_comments=True,
)
```

Or enable in the spec:

```yaml
strip_jcamp_comments: true
```

Behavior:

- If a file is rewritten due to `update_params`, comment stripping is applied
  after edits.
- If a file is included and appears to be JCAMP, comments may be stripped even
  without `update_params`.

---

## Root folder handling inside the zip

By default, pruning writes archive paths with a top-level root directory.

- `add_root=True` (default) prefixes every entry with a root directory name.
- `root_name` overrides the root directory name.
- If `root_name` is not provided, the name is derived from the dataset anchor
  or dataset root folder.

Disable the root folder:

```python
from brkraw.specs.pruner.logic import prune_dataset_to_zip

out = prune_dataset_to_zip(
    source="/path/to/dataset",
    dest="out.zip",
    files=["method", "acqp", "visu_pars"],
    mode="keep",
    add_root=False,
)
```

---

## Template variables in spec

When pruning from a spec, you can substitute `$KEY` placeholders using
`template_vars`.

```python
from brkraw.specs.pruner.logic import prune_dataset_to_zip_from_spec

out = prune_dataset_to_zip_from_spec(
    "prune.yaml",
    source="/path/to/dataset",
    dest="out.zip",
    template_vars={"Project": "CAMRI"},
)
```

In the spec:

```yaml
root_name: "$Project_shared"
```

Notes:

- Substitution is recursive for all strings in the spec.
- Unknown variables are left unchanged.

---

## Spec validation

By default, specs are validated against the schema.

Disable validation:

```python
from brkraw.specs.pruner.logic import prune_dataset_to_zip_from_spec

out = prune_dataset_to_zip_from_spec(
    "prune.yaml",
    source="/path/to/dataset",
    dest="out.zip",
    validate=False,
)
```

You can also load and validate explicitly:

```python
from brkraw.specs.pruner.logic import load_prune_spec

spec = load_prune_spec("prune.yaml", validate=True)
```

---

## Overrides when using a spec

`prune_dataset_to_zip_from_spec()` supports explicit overrides that replace
spec values at runtime:

- `strip_jcamp_comments`
- `root_name`
- `dirs`
- `mode`

Example:

```python
from brkraw.specs.pruner.logic import prune_dataset_to_zip_from_spec

out = prune_dataset_to_zip_from_spec(
    "prune.yaml",
    source="/path/to/dataset",
    dest="out.zip",
    mode="keep",
    dirs=[{"level": 1, "dirs": [3]}],
    root_name="shared_scan3",
    strip_jcamp_comments=True,
)
```

---

## Sidecar output

This module writes only the destination zip.

If you need a reproducibility sidecar (for example, `<output>.prune.yaml`),
generate it in your application layer using the resolved spec, overrides, and
paths that you pass into these functions.

---

## Common pitfalls

- `files` must contain at least one selector, or pruning fails.
- `update_params` matches by basename only (not full path).
- If filtering removes all files, pruning fails.
- If a JCAMP file cannot be parsed for updates, pruning fails.
- When using `prune_dataset_to_zip_from_spec()`, `source` and `dest` are required.
