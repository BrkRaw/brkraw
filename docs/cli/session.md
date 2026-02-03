# session

Manage BrkRaw environment defaults for CLI workflows.

`brkraw session` does not modify your shell directly. Instead it prints shell
commands, so you can apply them using `eval ...`.

This is useful when you run multiple commands repeatedly against the same
dataset or with the same conversion defaults.

Tip:

- `brkraw init --shell-rc ~/.zshrc` (or `~/.bashrc`) can install helper
  functions `brkraw-set` and `brkraw-unset` for convenience.

`brkraw session` also accepts `--root`, but session defaults are stored only in
environment variables (not in the config root).

---

## Applying Session Defaults in Your Shell

`brkraw session set` and `brkraw session unset` print shell code (export/unset).
To apply it to your current shell, wrap it with `eval`:

```bash
eval "$(brkraw session set --path /path/to/study --scan-id 3 --reco-id 1)"
```

This pattern works in both `bash` and `zsh`.

---

## Shell Helpers (brkraw-set / brkraw-unset)

On Linux (and other systems using `bash`), you can install small helper
functions into your shell rc file so you don't have to type `eval "$( ... )"`
each time:

```bash
brkraw init --shell-rc ~/.bashrc
```

Then start a new shell (or reload your rc file):

```bash
source ~/.bashrc
```

Examples:

```bash
brkraw-set -p /path/to/study -s 3 -r 1
brkraw convert
```

Unset everything:

```bash
brkraw-unset
```

Unset only the dataset path:

```bash
brkraw-unset -p
```

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
- FORMAT

Notes:

- `--convert-option` expects `KEY=VALUE`.
- Keys are normalized to uppercase and `-` becomes `_`.
- When setting `--path`, the path is validated and BrkRaw checks it can load as a dataset.

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

---

## Note on BRKRAW_SCAN_ID

`BRKRAW_SCAN_ID` is stored as a comma-separated string.
Different commands may interpret it differently:

- `brkraw info` treats it as a list of scan ids.
- `brkraw convert` uses only the first scan id when `--scan-id` is omitted.
- `brkraw params` expects a single scan id; set `-s/--scan-id` explicitly if needed.

---

## Interface With ParaVision (pvcmd Auto-Detection)

When running in a ParaVision environment, BrkRaw can auto-populate session
defaults by querying ParaVision's active parameter space.

Typical scenario:

- After completing a scan, you select a protocol/scan in the ParaVision
  *Experiments* view and the *method* panel is visible.
- You open the ParaVision-provided terminal and run `brkraw`.

If `pvcmd` is available and `ParxServer` is active, `brkraw` will use `pvcmd` to
detect the current experiment path and scan context, and set these environment
variables before processing CLI arguments:

- `BRKRAW_PATH`
- `BRKRAW_SCAN_ID`
- `BRKRAW_RECO_ID`

This lets you run commands without explicitly providing `path` and `--scan-id`,
for example:

```bash
brkraw info
brkraw convert --reco-id 1
```

Internally, this uses `pvcmd` to query the active parameter space and extract a
path like `<exp_path>/<scan_id>/pdata/<reco_id>` before `argparse` parses the
command line.
