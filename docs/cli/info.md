# info

Print a formatted summary of a Paravision dataset.

This command is intended to answer questions such as:

- What scans are present in this study?
- How are scans and recos organized?
- What metadata is available at the study and scan levels?

---

## Basic usage

```bash
brkraw info /path/to/study
```

If no path is provided, the command uses `BRKRAW_PATH`.

---

## Scope control

```bash
brkraw info /path/to/study --scope study
brkraw info /path/to/study --scope scan
brkraw info /path/to/study --scope full
```

Available scopes:

- `study`: study-level summary only
- `scan`: scan-level summary only
- `full` (default): study and scan

---

## Scan filtering

```bash
brkraw info /path/to/study --scope scan -s 3 4
```

Multiple scan IDs may be provided.

---

## Reco visibility

```bash
brkraw info /path/to/study --show-reco
```

Include reco entries under each scan.

---

## Config Root Override

Some formatting defaults (for example output width) are read from the config root.
Override it with:

```bash
brkraw info /path/to/study --root /path/to/config
```

---

## Environment defaults

The following environment variables are respected:

- `BRKRAW_PATH`: default dataset path
- `BRKRAW_SCAN_ID`: default scan IDs (comma-separated)
