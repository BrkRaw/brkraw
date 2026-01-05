# Python API

Examples below show common patterns when using BrkRaw as a library.

## Load a dataset

```python
import brkraw as brk

loader = brk.load("/path/to/study")
```

## Inspect info

```python
info = loader.info(scope="full", as_dict=True)
print(info["Study"])
```

## Read scan data

```python
scan = loader.get_scan(3)
data = scan.get_dataobj(reco_id=1)
```

## Build a NIfTI image

```python
nii = loader.convert(3, reco_id=1, format="nifti")
if isinstance(nii, tuple):
    # Multiple slice packs (suffix controlled by output.slicepack_suffix in config)
    for i, img in enumerate(nii, start=1):
        img.to_filename(f"scan3_slpack{i}.nii.gz")
else:
    nii.to_filename("scan3.nii.gz")
```

## Read metadata (sidecar)

```python
meta = loader.get_metadata(3, reco_id=1)
print(meta)
```

To capture the spec metadata used during resolution:

```python
meta, spec_info = loader.get_metadata(3, reco_id=1, return_spec=True)
print(spec_info["name"], spec_info.get("version"))
```

Override context map:

```python
meta = loader.get_metadata(3, reco_id=1, context_map="maps.yaml")
```

## Layout rendering

```python
from brkraw.core import layout as layout_core

name = layout_core.render_layout(
    loader,
    scan_id=3,
    layout_template="sub-{Subject.ID}/scan-{ScanID}_{Protocol}",
    context_map="maps.yaml",
)
```

Override info/metadata specs (testing only):

```python
name = layout_core.render_layout(
    loader,
    scan_id=3,
    layout_entries=[{"key": "Protocol", "hide": True}],
    override_info_spec="info_override.yaml",
    override_metadata_spec="metadata_override.yaml",
)
```

## Parameter search

```python
params = loader.search_params("PVM_RepetitionTime", scan_id=3)
print(params)
```
