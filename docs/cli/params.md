# params

Search Paravision parameter files for a key match and print results as YAML.

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

Scan id to search. Required for scan-level and reco-level searches.

If omitted, BrkRaw will try to use `BRKRAW_SCAN_ID` (first value when comma-separated).

### -r, --reco-id

Reco id to search within a scan.

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
