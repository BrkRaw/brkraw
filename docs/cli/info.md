# CLI: Inspecting datasets (info & params)

These commands provide **read-only inspection utilities** for Paravision
datasets. They are designed to help users understand dataset structure and
metadata **before** running any conversion.

Typical workflow:

1. Use `brkraw info` to understand study and scan structure
2. Use `brkraw params` to inspect acquisition parameters
3. Proceed to `convert` or `convert-batch`

---

## brkraw info

Print a formatted summary of a Paravision dataset.

This command is intended to answer questions such as:

- What scans are present in this study?
- How are scans and recos organized?
- What metadata is available at the study and scan levels?

### Basic usage of info

```bash
brkraw info /path/to/study
```

If no path is provided, the command uses `BRKRAW_PATH`.

### Scope control

```bash
brkraw info /path/to/study --scope study
brkraw info /path/to/study --scope scan
brkraw info /path/to/study --scope full
```

Available scopes:

- `study`: study-level summary only
- `scan`: scan-level summary only
- `full` (default): study and scan

### Scan filtering

```bash
brkraw info /path/to/study --scope scan -s 3 4
```

Multiple scan IDs may be provided.

### Reco visibility

```bash
brkraw info /path/to/study --show-reco
```

Include reco entries under each scan.

### Environment defaults

The following environment variables are respected:

- `BRKRAW_PATH`: default dataset path
- `BRKRAW_SCAN_ID`: default scan IDs (comma-separated)

---

## brkraw params

Search parameter files and print matching entries as YAML.

This command is useful for:

- Inspecting acquisition parameters before conversion
- Debugging sequence-specific behavior
- Verifying values used by specs and rules

### Basic usage

```bash
brkraw params /path/to/study -k PVM_RepetitionTime -s 3
```

### Restrict to specific parameter files

```bash
brkraw params -k VisuAcqEchoTime -s 4 -f visu_pars
```

Supported parameter files include:

- `method`
- `acqp`
- `visu_pars`
- `reco`

### Reco-level parameters

```bash
brkraw params -k RECO_size -s 3 -r 1
```

The reco ID is optional and only required for reco-level files.

### Environment defaults

If options are omitted, the following environment variables are used:

- `BRKRAW_PATH`
- `BRKRAW_SCAN_ID`
- `BRKRAW_RECO_ID`
- `BRKRAW_PARAM_KEY`
- `BRKRAW_PARAM_FILE`

---

## Design notes

- `info` focuses on structural, human-readable summaries
- `params` focuses on key-based, machine-readable output (YAML)
- Neither command modifies data or configuration
- Both commands are safe to run on shared or read-only datasets
