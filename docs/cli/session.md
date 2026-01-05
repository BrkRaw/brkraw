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

- `brkraw session set --convert-option FORMAT=nifti --convert-option COMPRESS=1`

- `brkraw session set --convert-option OUTPUT=./out --convert-option SIDECAR=1`

- `eval "$(brkraw session set -p /path/to/study -s 3)"`

Convert options (set as `BRKRAW_CONVERT_<KEY>`):

- `OUTPUT`, `PREFIX`, `SCAN_ID`, `RECO_ID`

- `SIDECAR`, `CONTEXT_MAP`, `COMPRESS`, `FORMAT`

- `UNWRAP_POSE`, `FLIP_X`

- `OVERRIDE_SUBJECT_TYPE`, `OVERRIDE_SUBJECT_POSE`

- `XYZ_UNITS`, `T_UNITS`, `HEADER`

`FORMAT`/`COMPRESS` control the NIfTI file extension (`nii` or `nii.gz`), not the
filename layout. The filename entries are configured via `output.layout_entries`
and `output.layout_template` in `config.yaml`.

## brkraw session unset

Emit `unset` statements. Behavior matches the old `brkraw unset`.

Examples:

- `brkraw session unset`

- `brkraw session unset --path --scan-id`

- `brkraw session unset --convert-option`

- `brkraw session unset --convert-option OUTPUT --convert-option SCAN_ID`

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
