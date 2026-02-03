# Python API

This page provides a minimal, task-oriented introduction to the
BrkRaw Python API. The examples mirror common CLI workflows and are
intended for interactive use and scripting.

---

## Load a dataset

Load a Paravision dataset from a directory, zip archive, or
`.PvDatasets` file.

```python
import brkraw as brk

loader = brk.load("/path/to/study")
```

The returned object acts as a dataset loader and entry point for
inspection and conversion.

---

## List available scans and reconstructions

Before converting, it is often helpful to list available scan and reconstruction IDs.

```python
scan_ids = list(loader.avail)
print("Scan IDs:", scan_ids)

scan = loader.get_scan(scan_ids[0])
reco_ids = list(scan.avail)
print("Reco IDs for first scan:", reco_ids)
```

---

## Inspect dataset information (CLI: `brkraw info`)

Retrieve structured metadata describing the study and scans.

```python
info = loader.info(scope="full", as_dict=True)
print(info["Study"])
```

This is the API equivalent of running `brkraw info` on the command line.

---

## Search scan parameters (CLI: `brkraw params`)

Query parameters across scans or within a specific scan.

```python
params = loader.search_params(
    "PVM_RepetitionTime",
    scan_id=3,
)
print(params)
```

This is useful for quickly checking acquisition settings before
conversion.

---

## Convert a scan to NIfTI (CLI: `brkraw convert`)

Convert a scan using the default reconstruction.

```python
nii = loader.convert(
    3,
    reco_id=1,
)
```

Save the output to disk:

```python
if nii is None:
    raise RuntimeError("Conversion returned no output.")

if isinstance(nii, tuple):
    for i, img in enumerate(nii, start=1):
        img.to_filename(f"scan3_part{i}.nii.gz")
else:
    nii.to_filename("scan3.nii.gz")
```

---

## Convert with hooks (optional)

Converter hooks are optional extensions that can modify reconstruction, metadata, or output behavior.
To list and install hooks, use the CLI:

```bash
brkraw hook list
brkraw hook install <hook-name>
```

To pass hook arguments from Python, use `hook_args_by_name`:

```python
nii = loader.convert(
    3,
    reco_id=1,
    hook_args_by_name={
        "<hook-name>": {
            # Fill this with the hook's supported arguments.
        }
    },
)
```

To generate a YAML preset template of hook arguments, run:

```bash
brkraw hook preset <hook-name>
```

For details, see [Hooks](../api/hook.md).

---

## Write sidecar metadata

Generate metadata dictionaries for JSON sidecar files.

```python
meta = loader.get_metadata(
    3,
    reco_id=1,
)
```

The metadata content is controlled by rules and specs.

---

## Build output paths

Render output paths using layout templates, then pass the result to `to_filename()`.

```python
from pathlib import Path
from brkraw.core import layout as layout_core

out_path = layout_core.render_layout(
    loader,
    scan_id=3,
    layout_template="sub-{Subject.ID}/scan-{ScanID}_{Protocol}",
)

Path(out_path).parent.mkdir(parents=True, exist_ok=True)

nii = loader.convert(3, reco_id=1)
if nii is None:
    raise RuntimeError("Conversion returned no output.")
if isinstance(nii, tuple):
    for i, img in enumerate(nii, start=1):
        img.to_filename(f"{out_path}_part{i}.nii.gz")
else:
    nii.to_filename(f"{out_path}.nii.gz")
```

This mirrors the layout behavior used by the CLI, but `render_layout()` only builds a path string.

---

## Batch conversion example

Convert the same scan across multiple datasets.

```python
from pathlib import Path
import brkraw as brk

root = Path("/path/to/root")

for dataset in root.iterdir():
    if not dataset.is_dir():
        continue
    try:
        loader = brk.load(dataset)
    except ValueError:
        # Not a Paravision dataset directory.
        continue

    for scan_id in loader.avail:
        nii = loader.convert(scan_id, reco_id=1)
        if nii is None:
            continue

        if isinstance(nii, tuple):
            for i, img in enumerate(nii, start=1):
                img.to_filename(f"{dataset.name}_scan{scan_id}_part{i}.nii.gz")
        else:
            nii.to_filename(f"{dataset.name}_scan{scan_id}.nii.gz")
```

For advanced usage, see the API reference:

- [Overview](../api/overview.md)
- [Data access](../api/data-access.md)
- [Info and params](../api/info.md)
- [Convert](../api/convert.md)
- [Addons](../api/addon.md)
- [Hooks](../api/hook.md)
- [Layout and naming](../api/layout.md)

If you need lower-level access (scan objects, dataset file access, `get_dataobj`,
`get_affine`), start with [Data access](../api/data-access.md).
