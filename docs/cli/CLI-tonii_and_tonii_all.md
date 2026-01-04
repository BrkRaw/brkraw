# CLI: tonii and tonii_all

These commands convert Paravision datasets to NIfTI and optionally write JSON
sidecars.

## brkraw tonii

Convert a single dataset. If `-s/--scan-id` is omitted, all scans and recos are
converted.

Examples:

- `brkraw tonii /path/to/study -s 3 -r 1 -o out`

- `brkraw tonii /path/to/study --sidecar`

- `brkraw tonii /path/to/study -o out` (all scans, all recos)

- `brkraw tonii /path/to/study --sidecar --sidecar-map-file maps.yaml`

- `brkraw tonii /path/to/study --output-map-file output_maps.yaml`

Notes:

- `-o` with `.nii` or `.nii.gz` writes a single file.

- `-o` without an extension is treated as a directory when converting all scans.

- Multiple slice packs use `output.slicepack_suffix` from `config.yaml`.

- `--sidecar-context-map` overrides the context map used for metadata sidecars.

- `--output-context-map` overrides the context map used for output filename mapping.

## brkraw tonii_all

Convert every dataset found under a root folder (subdirectories and zip files).

Examples:

- `brkraw tonii_all /path/to/root -o /path/to/out`

Notes:

- `-o` must be a directory for `tonii_all`.

- `tonii_all` always converts all scans and recos.

- Each dataset path is logged before conversion.

## Output format

NIfTI filenames are built from `output.format_fields` in `config.yaml`. Values
come from the output format spec (defaulting to built-in study/scan info). You
can override the spec by setting `output.format_spec` in `config.yaml` (name or
path).

Each entry is appended in order when the value is present. Values are sanitized
to `A-Z`, `a-z`, `0-9`, `.`, `_`, `-`. Missing values are skipped.
Use `sep: "/"` on a field to insert folder separators.

See `docs/api/API-Output-Format.md` for the programmatic API.

Example:

```yaml
output:
  format_fields:

  - key: Study.ID

    entry: study
    hide: false

  - key: Subject.ID

    entry: sub
    hide: false

  - key: Protocol

    hide: true
```

## Environment defaults

You can set defaults via `brkraw session set --tonii-option KEY=VALUE`.
Common keys:

- `OUTPUT`, `PREFIX`, `SCAN_ID`, `RECO_ID`

- `SIDECAR`, `SIDECAR_CONTEXT_MAP`, `OUTPUT_CONTEXT_MAP`

- `UNWRAP_POSE`, `FLIP_X`

- `OVERRIDE_SUBJECT_TYPE`, `OVERRIDE_SUBJECT_POSE`

- `XYZ_UNITS`, `T_UNITS`, `HEADER`, `OUTPUT_FORMAT`
