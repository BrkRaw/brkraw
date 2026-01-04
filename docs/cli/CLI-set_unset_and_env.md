# CLI: session

Manage environment defaults for repeated CLI use.

## Shell helpers

Install helpers into your shell rc:

- `brkraw init --shell-rc ~/.zshrc`

Then you can use:

- `brkraw-set ...` (exports vars in the current shell)

- `brkraw-unset ...` (unsets vars in the current shell)

## brkraw session set

Emit `export` statements for environment defaults.

Examples:

- `brkraw session set -p /path/to/study -s 3 -r 1`

- `brkraw session set --output-format nii.gz`

- `brkraw session set --tonii-option OUTPUT=./out --tonii-option SIDECAR=1`

- `eval "$(brkraw session set -p /path/to/study -s 3)"`

Tonii options (set as `BRKRAW_TONII_<KEY>`):

- `OUTPUT`, `PREFIX`, `SCAN_ID`, `RECO_ID`

- `SIDECAR`, `UNWRAP_POSE`, `FLIP_X`

- `SIDECAR_CONTEXT_MAP`, `OUTPUT_CONTEXT_MAP`

- `OVERRIDE_SUBJECT_TYPE`, `OVERRIDE_SUBJECT_POSE`

- `XYZ_UNITS`, `T_UNITS`, `HEADER`, `OUTPUT_FORMAT`

`OUTPUT_FORMAT` controls the NIfTI file extension (`nii` or `nii.gz`), not the
filename format. The filename fields are configured via `output.format_fields`
in `config.yaml`.

## brkraw session unset

Emit `unset` statements. Behavior matches the old `brkraw unset`.

Examples:

- `brkraw session unset`

- `brkraw session unset --path --scan-id`

- `brkraw session unset --tonii-option`

- `brkraw session unset --tonii-option OUTPUT --tonii-option SCAN_ID`

- `eval "$(brkraw session unset --path --scan-id)"`

## brkraw session env

Show current environment defaults.

## Help output (example)

```bash
brkraw session -h
```

```text
usage: brkraw session [-h] [--root ROOT] {set,unset,env} ...
```
