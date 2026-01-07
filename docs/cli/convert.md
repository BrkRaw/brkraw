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


Notes:

- `-o` with `.nii` or `.nii.gz` writes a single file.

- `-o` without an extension is treated as a directory when converting all scans.

- Multiple slice packs use `output.slicepack_suffix` from `config.yaml`.

- Output layout keys are resolved from the merged `info_spec` and `metadata_spec`
  results (metadata wins on conflicts).

- `--format nifti` with compression on writes `.nii.gz` (default).
  Use `--no-compress` to write `.nii`.

- `--prefix` supports layout tags like `{Protocol}` or `{SliceOrient}` and
  overrides any layout template from config/context maps.
- `--hook-arg` passes hook-specific options to converter hooks using
  `HOOK:KEY=VALUE` format (repeatable).


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


### Practical naming examples

Minimal `info_spec` context (from `src/brkraw/apps/loader/info/study.yaml`):
```yaml
Study.ID:
  sources:
    - file: subject
      key: SUBJECT_study_name
  transform: strip_jcamp_string
Subject.ID:
  sources:
    - file: subject
      key: SUBJECT_id
  transform: strip_jcamp_string
```
Assume the mapped values are:
```
Study.ID = S001
Subject.ID = 01
Protocol = T1w
```

Minimal entries (default prefixing):
```yaml
output:
  layout_entries:
    - key: Study.ID
      entry: study
      sep: "/"
    - key: Subject.ID
      entry: sub
      sep: "/"
    - key: Protocol
      entry: acq
```
Example result (when values exist):
```
study-S001/sub-sub-01/acq-T1w
```

Entry omitted (auto entry name):
```yaml
output:
  layout_entries:
    - key: Study.ID
      sep: "/"
    - key: Subject.ID
      sep: "/"
    - key: Protocol
```
Example result:
```
studyid-S001/subjectid-sub-01/protocol-T1w
```

Value-only entry (`hide: true`):
```yaml
output:
  layout_entries:
    - key: Study.ID
      entry: study
      sep: "/"
    - key: Subject.ID
      entry: sub
      sep: "/"
    - key: Protocol
      hide: true
```
Example result:
```
study-S001/sub-sub-01/T1w
```

Single-file output override:
```bash
brkraw convert /path/to/study -s 3 -r 1 -o /tmp/myfile.nii.gz
```
This ignores layout entries and writes the file as provided.

Template override:
```yaml
output:
  layout_template: "study-{Study.ID}/sub-{Subject.ID}/{Protocol}"
```
Example result:
```
study-S001/sub-sub-01/T1w
```

Extension handling:
- Layout outputs build the base filename only.
- The extension is added automatically based on `--format` and `--no-compress`
  (default: `.nii.gz`, `--no-compress` => `.nii`).
- Supplying `--output` with a `.nii`/`.nii.gz` filename uses that extension as-is.

Context map note:
`context_map` layout overrides are intended for BIDS-oriented workflows and are
under active development/testing/documentation.

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
