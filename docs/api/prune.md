# prune (Python API)

Copy a ParaVision study into a zip from Python. The input dataset is never
changed; only the destination zip is written. The CLI equivalent is
[`brkraw prune`](../cli/prune.md); the spec format is in
[Pruner specs](../extensions/pruner-specs.md).

```python
from brkraw.api import pruner
```

| Function | Use |
| --- | --- |
| `pruner.prune_dataset_to_zip(source, dest, files=None, ...)` | copy with options given directly |
| `pruner.prune_dataset_to_zip_from_spec(spec, source=..., dest=..., ...)` | copy with a pruner spec (path or mapping) |
| `pruner.select_files(source, files=None, mode="keep", dirs=None)` | the dataset-relative paths a prune would copy (for a dry run) |
| `pruner.resolve_prune_spec(spec, template_vars=...)` | load, validate and fill `$name` placeholders; unfilled placeholders raise `ValueError` |
| `pruner.load_prune_spec(path)` / `pruner.validate_prune_spec(spec)` | load or validate only |
| `pruner.classify_scans(paths)` | per scan: `"image"`, `"raw"` (raw data only) or `"none"` |

## Copy everything, or chosen scans

```python
from brkraw.api import pruner

report = {}
out = pruner.prune_dataset_to_zip(
    "/path/to/study",
    "study_copy.zip",
    dirs=[{"level": 1, "dirs": [3, 5]}],   # scans 3 and 5; study files are kept
    report=report,
)
print(out, report["files"], report["bytes"], report["scans"])
```

- `files=None` (the default) copies every file; with a list, `mode="keep"`
  copies only those names or relative paths and `mode="drop"` everything else.
- `dirs` rules: level 1 = scan folders, level 3 = reco folders under `pdata`.
- `overwrite=False` (default) raises `FileExistsError` when `dest` exists.
- The zip is written to a temporary file and moved into place; members over
  2 GiB use ZIP64.
- Other options: `update_params`, `strip_jcamp_comments`, `jcamp_headers`,
  `add_root`, `root_name`, `institution` (writes the name into the
  institution fields that exist).

## Copy with a spec

```python
from brkraw.api import pruner

out = pruner.prune_dataset_to_zip_from_spec(
    "lab_share.yaml",                     # or a mapping, or the built-in path
    source="/path/to/study",
    dest="M01.zip",
    template_vars={"subject_id": "M01", "study_id": "S1"},
)
```

`source` and `dest` are required. Keyword arguments `files`, `mode`, `dirs`,
`root_name`, `strip_jcamp_comments`, `institution` and `overwrite` override
the spec for that call.

## Record file

The functions write only the zip. The `.prune.yaml` record is written by the
CLI; in a script, record what you passed (spec file and its hash, options) in
your own application.
