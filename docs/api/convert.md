# Convert scans to NIfTI (Python API)

The brkraw Python API provides explicit functions for converting Bruker
Paravision scans into NIfTI files, with optional metadata sidecars and
extensible conversion logic via hooks.

This API is suitable for interactive use, scripting, and batch processing
in research pipelines.

---

## Entry point

All conversions are performed through a dataset loader.

```python
import brkraw as brk
loader = brk.load("/path/to/study")
```

---

## Basic usage (CLI: `brkraw convert`)

Convert a single scan and reconstruction:

```python
nii = loader.convert(
    scan_id=3,
    reco_id=1,
)
```

The returned object supports `to_filename()` and represents the converted image in memory.
Writing to disk is explicit:

```python
nii.to_filename("scan3.nii.gz")
```

By default:

- Output is generated in memory
- Files are compressed when written (.nii.gz)
- Affines are computed in subject_ras space
- Metadata follows configured layout and specs

---

## Selecting scans and reconstructions

### scan_id

Specify the scan ID to convert.

```python
loader.convert(scan_id=5, reco_id=1)
```

If `scan_id` is omitted, the call is rejected.
Batch behavior must be implemented explicitly.

### reco_id

Specify the reconstruction ID.

```python
loader.convert(scan_id=5, reco_id=2)
```

Notes:

- Default is 1
- If omitted and multiple recos exist, all recos are converted and returned
  as a list
- Some converter hooks may not use reco IDs explicitly

---

## Batch conversion pattern (CLI: `brkraw convert-batch`)

The Python API does not provide a separate batch command.
Batch behavior is implemented explicitly by iterating over datasets
or scans.

Example: convert all scans in a study.

```python
for scan_id in loader.avail.keys():
    nii = loader.convert(
        scan_id=scan_id,
        reco_id=1,
    )
    if nii is not None:
        out = f"scan{scan_id}.nii.gz"
        nii.to_filename(out)
```

Example: convert multiple datasets.

```python
from pathlib import Path
import brkraw as brk

root = Path("/path/to/datasets")

for dataset in root.iterdir():
    loader = brk.load(dataset)
    for scan_id in loader.avail.keys():
        nii = loader.convert(
            scan_id=scan_id,
            reco_id=1,
        )
```

Failures are raised as exceptions and should be handled by the caller.

---

## Output control

### Writing outputs

The API does not implicitly write files.
All outputs must be written explicitly by the caller.

```python
nii.to_filename("out/scan3.nii.gz")
```

This design avoids accidental overwrites and enables flexible workflows.

### Filename layout

Layout templates may be rendered using the layout API.

```python
from brkraw.core import layout as layout_core

path = layout_core.render_layout(
    loader,
    scan_id=3,
    layout_template="{Protocol}_{ScanID}",
    context_map="map.yaml",
)

nii.to_filename(path + ".nii.gz")
```

---

## Metadata sidecars (CLI: `--sidecar`)

Generate metadata dictionaries for JSON sidecar files.

```python
meta = loader.get_metadata(
    scan_id=3,
    reco_id=1,
    context_map="map.yaml",
)
```

Sidecar metadata is generated from:

- Built-in info specs
- Installed metadata specs
- Optional context maps

Writing JSON files is the responsibility of the caller.

---

## Affine handling

### Affine space

Select the affine space used for conversion.

```python
loader.convert(
    scan_id=3,
    reco_id=1,
    space="subject_ras",
)
```

Valid values are case-sensitive:

- raw
- scanner
- subject_ras

### Subject overrides

Override subject type or pose when computing subject-view affines
(`space="subject_ras"` only).

```python
loader.convert(
    scan_id=3,
    reco_id=1,
    override_subject_type="Quadruped",
    override_subject_pose="Head_Supine",
)
```

Invalid overrides raise an exception.

### Axis flips

Flip axes in the output affine.

```python
loader.convert(
    scan_id=3,
    reco_id=1,
)
```

### Flatten frame-group dimensions

Flatten frame-group dimensions into a 4D time axis when data is 5D or higher.

```python
loader.convert(
    scan_id=3,
    reco_id=1,
    flatten_fg=True,
)
```

Notes:

- 4D or smaller data is unchanged.
- Extra dimensions are collapsed into the 4th dimension in order.

---

## Units and headers

### Spatial and temporal units

```python
loader.convert(
    scan_id=3,
    reco_id=1,
    xyz_units="mm",
    t_units="sec",
)
```

Values are validated strictly and are case-sensitive.

### Header overrides

Override NIfTI header fields using a YAML file.

```python
loader.convert(
    scan_id=3,
    reco_id=1,
    header="header_override.yaml",
)
```

---

## Context maps and selection

Apply metadata remapping and conditional selection logic.

```python
loader.convert(
    scan_id=3,
    reco_id=1,
    context_map="map.yaml",
    sidecar=True,
)
```

Context maps can:

- Select or skip scans
- Modify metadata fields
- Override layout rules and suffixes

---

## Converter hooks

Pass arguments to installed converter hooks.

```python
loader.convert(
    scan_id=3,
    reco_id=1,
    hook_args={
        "mrs": {
            "reference": "water",
        }
    },
)
```

Values are parsed as bool, int, float, or string.

---

## Design notes

- Conversion APIs are explicit and non-destructive
- No implicit defaults or environment variables are used
- Batch behavior is implemented by the caller
- All affine and override options are case-sensitive
- Errors are raised early and must be handled explicitly
