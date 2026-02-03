# Inspecting datasets (info and params)

The brkraw Python API provides read-only inspection utilities for
Paravision datasets.

These APIs are designed to help users understand dataset structure
and metadata before running any conversion.

Typical workflow:

1. Use `loader.info()` to understand study and scan structure
2. Use `loader.search_params()` to inspect acquisition parameters
3. Proceed to conversion

---

## Dataset loader

All inspection APIs operate on a loaded dataset.

```python
from brkraw.api import BrukerLoader

loader = BrukerLoader("/path/to/study")
```

The loader performs validation on load and does not modify the dataset.

---

## List available scans and reconstructions

```python
scan_ids = list(loader.avail)
print("Scan IDs:", scan_ids)

scan = loader.get_scan(scan_ids[0])
reco_ids = list(scan.avail)
print("Reco IDs for first scan:", reco_ids)
```

---

## Study and scan summaries (CLI: `brkraw info`)

Retrieve structured summaries describing the dataset.

This API is intended to answer questions such as:

- What scans are present in this study?
- How are scans and recos organized?
- What metadata is available at the study and scan levels?

### Basic usage

```python
info = loader.info(scope="full", as_dict=True)
print(info)
```

### Scope control

```python
loader.info(scope="study", as_dict=True)
loader.info(scope="scan", as_dict=True)
loader.info(scope="full", as_dict=True)
```

Available scopes:

- `study`: study-level summary only
- `scan`: scan-level summary only
- `full`: study and scan summaries

### Scan filtering

```python
loader.info(
    scope="scan",
    scan_id=[3, 4],
    as_dict=True,
)
```

Multiple scan IDs may be provided.

### Reco visibility

```python
loader.info(
    scope="scan",
    show_reco=True,
    as_dict=True,
)
```

When enabled, reco entries are included under each scan.

Note: `show_reco` defaults to `True` in the Python API. If you want the default
CLI-like behavior (hide reco rows), pass `show_reco=False`.

### Return format

- When `as_dict=True`, the result is a structured dictionary suitable for scripting.
- When `as_dict=False`, BrkRaw prints a formatted table to stdout and returns `None`.

The exact structure of the returned dictionary is stable within a
major version.

---

## Parameter search (CLI: `brkraw params`)

Search parameter files and retrieve matching entries.

This API is useful for:

- Inspecting acquisition parameters before conversion
- Debugging sequence-specific behavior
- Verifying values used by specs and rules

### Basic usage

```python
params = loader.search_params(
    "PVM_RepetitionTime",
    scan_id=3,
)
print(params)
```

### Restrict to specific parameter files

```python
params = loader.search_params(
    "VisuAcqEchoTime",
    scan_id=4,
    file="visu_pars",
)
```

Supported parameter files include:

- `method`
- `acqp`
- `visu_pars`
- `reco`

### Reco-level parameters

```python
params = loader.search_params(
    "RECO_size",
    scan_id=3,
    reco_id=1,
)
```

The reco ID is optional and only required for reco-level parameter files.

### Return format

The result is a structured mapping suitable for programmatic use.
No formatting or filtering is applied beyond key and scope selection.

---

## Design notes

- Inspection APIs are strictly read-only
- No files or configuration are modified
- No implicit defaults or environment variables are used
- All scope and selection must be explicit at call time

These APIs are safe to use on shared or read-only datasets.
