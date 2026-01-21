# session

Manage BrkRaw environment defaults for CLI workflows.

`brkraw session` does not modify your shell directly. Instead it prints shell
commands, so you can apply them using `eval ...`.

This is useful when you run multiple commands repeatedly against the same
dataset or with the same conversion defaults.

Tip:

- `brkraw init --shell-rc ~/.zshrc` (or `~/.bashrc`) can install helper
  functions `brkraw-set` and `brkraw-unset` for convenience.

---

## session set

Emit `export ...` statements for BrkRaw defaults.

Examples:

Set a default dataset path:

```bash
eval "$(brkraw session set --path /path/to/study)"
```

Set default scan/reco ids:

```bash
eval "$(brkraw session set --scan-id 3 --reco-id 1)"
```

Set a default parameter key for `brkraw params`:

```bash
eval "$(brkraw session set --param-key PVM_RepetitionTime)"
```

Set default parameter file(s) for `brkraw params`:

```bash
eval "$(brkraw session set --param-file visu_pars)"
```

Set default convert options (repeatable):

```bash
eval "$(brkraw session set --convert-option SIDECAR=true --convert-option SPACE=subject_ras)"
```

Convert option keys map to `BRKRAW_CONVERT_<OPTION>` environment variables.

Supported keys include:

- OUTPUT, PREFIX, SCAN_ID, RECO_ID, SIDECAR, CONTEXT_MAP
- COMPRESS, SPACE, FLATTEN_FG
- OVERRIDE_SUBJECT_TYPE, OVERRIDE_SUBJECT_POSE
- XYZ_UNITS, T_UNITS
- HEADER

Notes:

- `--convert-option` expects `KEY=VALUE`.
- Keys are normalized to uppercase and `-` becomes `_`.

---

## session unset

Emit `unset ...` commands to remove defaults.

Unset everything:

```bash
eval "$(brkraw session unset)"
```

Unset selected categories:

```bash
eval "$(brkraw session unset --path --scan-id --reco-id)"
```

Unset specific convert variables:

```bash
eval "$(brkraw session unset --convert-option OUTPUT --convert-option SPACE)"
```

Unset all convert variables:

```bash
eval "$(brkraw session unset --convert-option)"
```

Notes:

- `unset` flags are toggles (e.g., `--reco-id` unsets the default reco id).

---

## session env

Show current BrkRaw environment defaults (from environment variables).

```bash
brkraw session env
```

If nothing is set:

```text
(none)
```
