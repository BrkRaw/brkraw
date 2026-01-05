# CLI: Info and Params

This guide covers the inspection commands that read dataset metadata and
parameter files.

## brkraw info

Show formatted study/scan summaries.

Examples:

- `brkraw info /path/to/study`

- `brkraw info /path/to/study --scope scan -s 3 4`

- `brkraw info --scope study` (uses `BRKRAW_PATH`)

Options:

- `--scope full|study|scan`: choose output scope (default: full).

- `-s/--scan-id`: filter scan ids when scope is `scan` or `full`.

- `--show-reco`: include reco entries.

- `--root`: override config root for defaults like output width.

Environment defaults:

- `BRKRAW_PATH`: default dataset path.

- `BRKRAW_SCAN_ID`: default scan ids (comma-separated list).

## brkraw params

Search parameter files for a key and print results as YAML.

Examples:

- `brkraw params /path/to/study -k PVM_RepetitionTime -s 3`

- `brkraw params -k VisuAcqEchoTime -s 4 -f visu_pars`

Options:

- `-k/--key`: parameter key to search for.

- `-s/--scan-id`: scan id (required for scan-level parameter files).

- `-r/--reco-id`: reco id (optional).

- `-f/--file`: restrict to parameter files (method, acqp, visu_pars, reco).

Environment defaults:

- `BRKRAW_PATH`

- `BRKRAW_SCAN_ID`

- `BRKRAW_RECO_ID`

- `BRKRAW_PARAM_KEY`

- `BRKRAW_PARAM_FILE`
