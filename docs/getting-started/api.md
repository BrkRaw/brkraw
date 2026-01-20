# Python API quickstart

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
nii.to_filename("scan3.nii.gz")
```

---

## Write sidecar metadata

Generate metadata dictionaries for JSON sidecar files.

```python
meta = loader.get_metadata(
    3,
    reco_id=1,
    context_map="maps.yaml",
)
```

The metadata content is controlled by context maps, rules, and specs.

---

## Customize output naming and layout

Render output paths using layout templates.

```python
from brkraw.core import layout as layout_core

name = layout_core.render_layout(
    loader,
    scan_id=3,
    layout_template="sub-{Subject.ID}/scan-{ScanID}_{Protocol}",
    context_map="maps.yaml",
)
```

This mirrors the layout behavior used by the CLI.

---

## Batch conversion example

Convert the same scan across multiple datasets.

```python
from pathlib import Path
import brkraw as brk

root = Path("/path/to/root")

for dataset in root.iterdir():
    loader = brk.load(dataset)
    for scan_id in loader.avail.keys():
        nii = loader.convert(
            scan_id,
            reco_id=1,
        )
        if nii is not None:
            out = f"{dataset.name}_scan{scan_id}.nii.gz"
            nii.to_filename(out)
```

---

## Manage addons programmatically

Add, list, and remove addons from Python.

```python
from brkraw.apps import addon

addon.add("/path/to/spec.yaml")
addon.list_installed()
addon.remove("spec.yaml", root=None)
```

For advanced usage, see the full API documentation under `docs/api/`.

If you need lower-level access (scan objects, dataset file access, `get_dataobj`,
`get_affine`), start with `docs/api/data-access.md`.
