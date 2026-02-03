# Convert (Python API)

Convert Bruker Paravision scans into NIfTI objects, with optional hook arguments.

---

## Equivalent CLI commands

- `brkraw convert`
- `brkraw convert-batch`

In the CLI, output naming, selection, and sidecars are handled for you.
In the Python API, conversion returns in-memory objects and you decide how to
name and write outputs.

---

## Entry point

```python
from brkraw.api import BrukerLoader

loader = BrukerLoader("/path/to/study")
```

To disable hook application entirely for this loader:

```python
loader = BrukerLoader("/path/to/study", disable_hook=True)
```

---

## Convert a scan

```python
nii = loader.convert(3, reco_id=1)
```

Return shape:

- `None` when required metadata is unavailable or conversion fails.
- A single `nibabel.Nifti1Image` when there is one slice pack.
- A tuple of `nibabel.Nifti1Image` when there are multiple slice packs.

Writing to disk is explicit:

```python
if nii is None:
    raise RuntimeError("Conversion returned no output.")

if isinstance(nii, tuple):
    for i, img in enumerate(nii, start=1):
        img.to_filename(f"scan3_part{i}.nii.gz")
else:
    nii.to_filename("scan3.nii.gz")
```

Notes:

- `reco_id` is optional. If omitted, BrkRaw uses the first available reconstruction for that scan.
- The Python API does not implement a “convert all scans” mode; batch behavior is explicit in your loop.

---

## Multi-dimensional data options

### flatten_fg

Flatten frame-group dimensions to 4D when data is 5D or higher:

```python
nii = loader.convert(3, reco_id=1, flatten_fg=True)
```

### cycle_index / cycle_count

Read only a subset of cycles (last axis) when the scan has multi-cycle data:

```python
nii = loader.convert(3, reco_id=1, cycle_index=0, cycle_count=10)
```

---

## Batch patterns

Convert all scans in one dataset:

```python
for scan_id in loader.avail:
    nii = loader.convert(scan_id, reco_id=1)
    if nii is None:
        continue
    if isinstance(nii, tuple):
        for i, img in enumerate(nii, start=1):
            img.to_filename(f"scan{scan_id}_part{i}.nii.gz")
    else:
        nii.to_filename(f"scan{scan_id}.nii.gz")
```

Convert multiple datasets:

```python
from pathlib import Path
from brkraw.api import BrukerLoader

root = Path("/path/to/datasets")
for dataset in root.iterdir():
    if not dataset.is_dir():
        continue
    try:
        loader = BrukerLoader(dataset)
    except ValueError:
        continue
    for scan_id in loader.avail:
        _ = loader.convert(scan_id, reco_id=1)
```

---

## Affines, units, and headers

### space

```python
nii = loader.convert(3, reco_id=1, space="subject_ras")
```

Valid values:

- `"raw"`
- `"scanner"`
- `"subject_ras"`

### override_subject_type / override_subject_pose

```python
nii = loader.convert(
    3,
    reco_id=1,
    override_subject_type="Quadruped",
    override_subject_pose="Head_Supine",
)
```

### xyz_units / t_units

```python
nii = loader.convert(3, reco_id=1, xyz_units="mm", t_units="sec")
```

### override_header (from YAML)

`loader.convert()` expects `override_header` as an in-memory mapping. To load
from a YAML file:

```python
from brkraw.api import nifti_resolver

override_header = nifti_resolver.load_header_overrides("header.yaml")
nii = loader.convert(3, reco_id=1, override_header=override_header)
```

### Affine post-transforms (advanced)

You can post-transform affines using flip/rotate options when calling `get_affine()`.
These kwargs are also accepted by `convert()` (they are applied during affine resolution).

```python
aff = loader.get_affine(3, reco_id=1, flip_x=True)
aff = loader.get_affine(3, reco_id=1, rad_z=0.1)
```

---

## Hooks

Pass hook arguments by hook name:

```python
nii = loader.convert(
    3,
    reco_id=1,
    hook_args_by_name={
        "<hook-name>": {
            "key": "value",
        }
    },
)
```

Notes:

- Hook installation/registration is typically done via the CLI (`brkraw hook install ...`).
- Hook arguments are applied only when a converter hook is resolved for the scan (based on installed hooks and rules).
- For hook-aware execution, call the **loader** methods (`loader.convert`, `loader.get_dataobj`, `loader.get_affine`).
  Accessing scan objects is primarily for building and testing new hooks.

---

## Output naming and sidecars

In the CLI, output naming and sidecar writing are integrated into conversion.
In the Python API:

- output paths are built separately (see [layout](layout.md))
- sidecar metadata is generated separately (see [info](info.md) and [layout](layout.md))

Example: generate a sidecar payload (you write JSON yourself):

```python
from pathlib import Path
import json

meta = loader.get_metadata(3, reco_id=1)
Path("scan3.json").write_text(json.dumps(meta or {}, indent=2), encoding="utf-8")
```
