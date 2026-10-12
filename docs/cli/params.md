# params

Search ParaVision parameter files for a key match and print results as YAML
to standard output (`(none)` when nothing matches), whatever the logging level.

This command is useful for quick inspection and debugging before conversion,
or when writing/modifying specs and rules.

---

## Basic usage

Search within a scan:

```bash
brkraw params /path/to/study -k PVM_RepetitionTime -s 3
```

Search within a reconstruction (reco-level parameters):

```bash
brkraw params /path/to/study -k RECO_size -s 3 -r 1
```

---

## Options

### path (positional)

Path to the Bruker study. If omitted, `BRKRAW_PATH` is used.

### -k, --key

Parameter key to search for (required unless `BRKRAW_PARAM_KEY` is set).

### -s, --scan-id

Scan ID to search (one). A study path needs it: without a scan ID nothing is
found.

If omitted, BrkRaw uses `BRKRAW_SCAN_ID`. It must hold one scan ID; several
(`3,4`) are an error for `params`.

### -r, --reco-id

Reco ID to search within a scan.

If omitted, BrkRaw will try to use `BRKRAW_RECO_ID`.

### -f, --file

One or more parameter files to search.

Supported values:

- `method`
- `acqp`
- `visu_pars`
- `reco`

Examples:

```bash
brkraw params /path/to/study -k VisuAcqEchoTime -s 4 -f visu_pars
brkraw params /path/to/study -k PVM_SpecSWH -s 7 -f method acqp
```

If omitted, BrkRaw searches the default set for the current scope. You can
set a default list via `BRKRAW_PARAM_FILE` (comma-separated).

---

## Environment Defaults

This command respects:

- `BRKRAW_PATH`
- `BRKRAW_PARAM_KEY`
- `BRKRAW_SCAN_ID`
- `BRKRAW_RECO_ID`
- `BRKRAW_PARAM_FILE`
