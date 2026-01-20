# Data access (Scan/Reco helpers)

This page describes how to access scan/reco objects and read dataset files and
image data from the Python API.

BrkRaw is **read-only** with respect to the input dataset: it reads files from a
directory/zip/PvDatasets container and returns in-memory objects.

---

## Get a scan (and list what’s available)

```python
import brkraw as brk

loader = brk.load("/path/to/study")
print(sorted(loader.avail.keys()))   # scan ids

scan = loader.get_scan(3)
print(sorted(scan.avail.keys()))     # reco ids under this scan

reco = scan.get_reco(1)
```

Notes:

- `loader.avail` is a mapping of `{scan_id: Scan}`.
- `scan.avail` is a mapping of `{reco_id: Reco}`.

---

## Scan helpers

When you load a dataset, BrkRaw attaches convenience helpers onto each scan
object so you can access common conversion/inspection pieces directly.

Typical helpers on a scan:

- `scan.get_dataobj(reco_id=None)` → reconstructed NumPy array(s)
- `scan.get_affine(reco_id=None, space="subject_ras", ...)` → affine matrix/matrices
- `scan.get_nifti1image(reco_id=None, ...)` → `nibabel.nifti1.Nifti1Image`
- `scan.convert(reco_id=None, ...)` → output object(s) supporting `to_filename`
- `scan.get_metadata(reco_id=None, ...)` → metadata mapping for sidecars/specs
- `scan.search_params(key, file=..., reco_id=...)` → parameter search results

The loader also exposes convenience wrappers for common operations:

```python
nii = loader.convert(scan_id=3, reco_id=1)
aff = loader.get_affine(scan_id=3, reco_id=1, space="subject_ras")
data = loader.get_dataobj(scan_id=3, reco_id=1)
```

---

## File access (parameter files and raw entries)

Scan and reco objects are “dataset-backed” nodes that can open files relative to
their location in the dataset tree.

### Parameter files (auto-parsed)

Common parameter files are opened and parsed automatically as `Parameters`
objects when possible:

```python
scan = loader.get_scan(3)
reco = scan.get_reco(1)

method = scan.method          # Parameters
acqp = scan.acqp              # Parameters
visu = reco.visu_pars         # Parameters
reco_params = reco.reco       # Parameters

print(method["Method"])
```

### Reading binary / text entries

Non-parameter files are exposed as in-memory file-like buffers:

- text-like content → `io.StringIO`
- binary-like content → `io.BytesIO`

Example: access the reconstructed `2dseq` bytes (typically large):

```python
reco = loader.get_scan(3).get_reco(1)
buf = reco["2dseq"]           # BytesIO
raw = buf.read()
```

### Explicit vs attribute access

Files can be accessed using:

- attribute access (`scan.method`, `reco.visu_pars`)
- dictionary-style access (`scan["method"]`, `reco["2dseq"]`)

If a dataset contains file names that are not valid Python identifiers, prefer
the dictionary-style form.

### Listing entries under a node

```python
scan = loader.get_scan(3)
print(scan.listdir())         # names under the scan folder

reco = scan.get_reco(1)
print(reco.listdir())         # names under the reco folder (e.g. 2dseq, visu_pars)
```

---

## Get data and affine separately

For pipelines that need lower-level access than `convert()`, you can retrieve
image arrays and affines directly.

```python
scan = loader.get_scan(3)

data = scan.get_dataobj(reco_id=1)
affine = scan.get_affine(reco_id=1, space="subject_ras")
```

Notes:

- Some scans produce multiple “slice packs”; in that case these APIs may return
  a tuple of arrays/matrices (one per pack).
- `space` controls the affine coordinate system (`raw`, `scanner`, `subject_ras`).
- `scan.get_affine(...)` also accepts optional post-transforms via extra kwargs:
  `flip_x/flip_y/flip_z` and `rad_x/rad_y/rad_z` (radians), applied right before returning.

---

## FID / rawdata access (when available)

Some scan types expose FID/rawdata access:

```python
fid = loader.get_fid(scan_id=3)
```

If the scan has no FID reader, this returns `None`.
