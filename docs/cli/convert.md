# CLI: convert

These commands convert Paravision datasets to NIfTI and optionally write JSON
sidecars.

## brkraw convert

Convert a single dataset. If `-s/--scan-id` is omitted, all scans and recos are
converted.

Examples:

- `brkraw convert /path/to/study -s 3 -r 1 -o out`

- `brkraw convert /path/to/study --sidecar`

- `brkraw convert /path/to/study -o out` (all scans, all recos)

- `brkraw convert /path/to/study --sidecar --context-map maps.yaml`

Notes:

- `-o` with `.nii` or `.nii.gz` writes a single file.

- `-o` without an extension is treated as a directory when converting all scans.

- Multiple slice packs use `output.slicepack_suffix` from `config.yaml` or
  `__meta__.slicepack_suffix` in the context map.

- `--context-map` controls metadata/output mapping and selector filtering.
  Selector keys in the map (`selector: true`) limit conversions to matching scans.
  Use `target` in map rules to choose `info_spec` or `metadata_spec`.

- Output layout keys are resolved from the merged `info_spec` and `metadata_spec`
  results (metadata wins on conflicts).

- `--format nifti` with compression on writes `.nii.gz` (default).
  Use `--no-compress` to write `.nii`.

- `--prefix` supports layout tags like `{Protocol}` or `{SliceOrient}` and
  overrides any layout template from config/context maps.

## brkraw convert-batch

Convert every dataset found under a root folder (subdirectories and zip files).

Examples:

- `brkraw convert-batch /path/to/root -o /path/to/out`

Notes:

- `-o` must be a directory for `convert-batch`.

- `convert-batch` always converts all scans and recos.

- Each dataset path is logged before conversion.

## Output layout

NIfTI filenames are built from layout fields or a layout template. Values come
from merged `info_spec` + `metadata_spec` results.

Priority order:

1. CLI `--prefix` (template override).

2. `context_map.__meta__` (`layout_entries`, `layout_template`).

3. `config.yaml` (`output.layout_entries`, `output.layout_template`).

Each entry is appended in order when the value is present. Values are sanitized
to `A-Z`, `a-z`, `0-9`, `.`, `_`, `-`. Missing values are skipped.
Use `sep: "/"` on a field to insert folder separators.

See `docs/api/layout.md` for the programmatic API.

Example:

```yaml
output:
  layout_entries:

  - key: Study.ID

    entry: study
    hide: false

  - key: Subject.ID

    entry: sub
    hide: false

  - key: Protocol
    hide: true
```

Context map layout overrides:

```yaml
__meta__:
  layout_entries:
    - key: Study.ID
      entry: study
      sep: "/"
    - key: Subject.ID
      entry: sub
      sep: "/"
    - key: Protocol
      hide: true
  layout_template: "study-{Study.ID}/sub-{Subject.ID}/{Protocol}"
  slicepack_suffix: "_sl{index}"
```

## Environment defaults

You can set defaults via `brkraw session set --convert-option KEY=VALUE`.
Common keys:

- `OUTPUT`, `PREFIX`, `SCAN_ID`, `RECO_ID`

- `SIDECAR`, `CONTEXT_MAP`, `SPACE`, `COMPRESS`, `FORMAT`

- `FLIP_X`

- `OVERRIDE_SUBJECT_TYPE`, `OVERRIDE_SUBJECT_POSE`

- `XYZ_UNITS`, `T_UNITS`, `HEADER`
