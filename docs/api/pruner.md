# Pruner API

BrkRaw Pruner selects files from a Bruker dataset, bundles them into a ZIP,
and optionally updates JCAMP parameter values.

## Python API

Module: `brkraw.specs.pruner`

### prune_dataset_to_zip

```python
from brkraw.specs.pruner import prune_dataset_to_zip

prune_dataset_to_zip(
    source="/path/to/dataset",
    dest="out/pruned.zip",
    files=["fid", "acqp", "method", "2dseq"],
    mode="keep",
    update_params={"method": {"PVM_ScanTimeStr": "120.0"}},
    dirs=[{"level": 1, "dirs": ["adj"]}],
    add_root=True,
    root_name="study_pruned",
)
```

Behavior summary:

- Entries in `files` match either relative paths or basenames.

- `mode="keep"` includes only matching files; `mode="drop"` excludes them.

- `dirs` filters directories by path level and inherits the top-level `mode`.

- `update_params` replaces JCAMP key values for the target files.

Notes on `update_params`:

- This feature edits JCAMP parameter values and should be used with care.

- It applies to every matching parameter file (by basename), not to a specific scan id.

- Use it for de-identification or redaction when preparing datasets for sharing.

- No helper utilities are provided; you must ensure JCAMP compliance yourself.

Compatibility guidance:

- File selectors match basenames, so you can list `reco`, `visu_pars`, `2dseq`

  without the full `pdata/<reco_id>/` path.

- A minimal readable dataset needs `method`, `acqp`, plus `reco`, `visu_pars`,

  and `2dseq` from each kept reconstruction.

- Missing `visu_pars` prevents BrkRaw from recognizing the study.

- Keep `subject` only when subject metadata is required (remove it for privacy).

Dropping scans:

- Scans live under top-level numeric folders (e.g. `1/`, `2/`, `13/`).

- Use `dirs` to drop scan folders by level.

  For example, to drop scan 13:

```yaml
dirs:

  - level: 1

    dirs: ["13"]
```

### prune_dataset_to_zip_from_spec

```python
from brkraw.specs.pruner import prune_dataset_to_zip_from_spec

prune_dataset_to_zip_from_spec(
    "specs/prune.yaml",
    source="/data/study",
    dest="/data/out/study_pruned.zip",
)
```

- `source` and `dest` are required arguments.

### load_prune_spec / validate_prune_spec

```python
from brkraw.specs.pruner import load_prune_spec, validate_prune_spec

spec = load_prune_spec("specs/prune.yaml", validate=True)
validate_prune_spec(spec)
```

## Prune Spec (YAML)

Schema: `src/brkraw/schema/pruner.yaml`

Field descriptions:

- `__meta__` (object, required): Spec metadata (`name`, `version`, `description`, `category`).

- `files` (array, required): File selectors (string/number).

- `mode` (string): `"keep"` or `"drop"`.

- `update_params` (object): JCAMP update rules in `{filename: {key: value}}` format.

- `dirs` (array): Directory filter rule list.

- `add_root` (boolean): Whether to include a root folder in the zip.

- `root_name` (string): Root folder name when `add_root=True`.

### dirs

Each rule includes:

- `level`: Path level starting from 1.

- `dirs`: Directory names to filter at that level.

Rules are applied in ascending `level` order.

### Example spec (minimal compatible)

```yaml
__meta__:
  name: "pruner_default"
  version: "1.0.0"
  description: "Default pruner spec."
  category: "pruner_spec"
mode: "keep"
files:

  - "method"

  - "acqp"

  - "reco"

  - "visu_pars"

  - "2dseq"

update_params:
  method:
    PVM_ScanTimeStr: "120.0"
add_root: true
root_name: "study_pruned"
```

## Errors and notes

- `__meta__` is required and must include `name`, `version`, `description`, `category`.

- Fails if `files` is empty.

- `mode` only allows `"keep"` or `"drop"`.

- `dirs.level` must be an integer >= 1.

- `update_params` applies by filename (basename).
