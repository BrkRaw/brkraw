# API: CLI Equivalents

This page maps common CLI workflows to their Python API equivalents.

## Inspect info (`brkraw info`)

```python
import brkraw as brk

loader = brk.load("/path/to/study")
info = loader.info(scope="full", as_dict=True)
print(info["Study"])
```

## Search parameters (`brkraw params`)

```python
params = loader.search_params("PVM_RepetitionTime", scan_id=3)
print(params)
```

## Convert (`brkraw convert`)

```python
nii = loader.convert(3, reco_id=1, format="nifti")
nii.to_filename("scan3.nii.gz")
```

Write sidecar metadata:

```python
meta = loader.get_metadata(3, reco_id=1, context_map="maps.yaml")
```

Customize the output layout:

```python
from brkraw.core import layout as layout_core

name = layout_core.render_layout(
    loader,
    scan_id=3,
    layout_template="sub-{Subject.ID}/scan-{ScanID}_{Protocol}",
    context_map="maps.yaml",
)
```

## Convert a batch (`brkraw convert-batch`)

```python
from pathlib import Path

root = Path("/path/to/root")
for dataset in root.iterdir():
    loader = brk.load(dataset)
    for scan_id in loader.avail.keys():
        nii = loader.convert(scan_id, reco_id=1, format="nifti")
        if nii is not None:
            nii.to_filename(f"{dataset.name}_scan{scan_id}.nii.gz")
```

## Manage addons (`brkraw addon`)

```python
from brkraw.apps import addon

addon.add("/path/to/spec.yaml")
addon.list_installed()
addon.remove("spec.yaml", root=None)
```

See `docs/api/addon.md` for more details.
