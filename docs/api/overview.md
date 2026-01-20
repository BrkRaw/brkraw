# Python API overview

The brkraw Python API provides programmatic access to the same core
functionality as the CLI, using explicit function calls and objects
instead of shell commands.

The API is organized around a small set of core tasks:

- Load a dataset and bind a configuration context
- Inspect datasets and acquisition parameters
- Convert scans and generate outputs
- Manage mapping logic and extensions

This section documents the main API entry points and how they fit together.

For lower-level access (scan objects, file access, data/affine retrieval), see
`docs/api/data-access.md`.

## Entry point

All workflows start by loading a dataset:

```python
import brkraw as brk
loader = brk.load("/path/to/study")
```

The returned object acts as a dataset loader and the primary handle for
inspection and conversion.

Loading a dataset is non-destructive and does not modify the source files.

## Recommended workflow

1. Load a dataset:

```python
loader = brk.load("/path/to/study")
```

2. Inspect the dataset:

```python
info = loader.info(scope="full", as_dict=True)
```

3. Convert a scan:

```python
nii = loader.convert(
    scan_id=3,
    reco_id=1,
)
```

4. Reuse the same loader instance when converting multiple scans:

```python
for scan_id in loader.avail.keys():
    nii = loader.convert(
        scan_id=scan_id,
        reco_id=1,
    )
```

Reusing the loader avoids repeated dataset discovery and validation,
while keeping scan selection explicit at each call.

## Notes

- Output naming and metadata generation are controlled by configuration
  files (`config.yaml`) and optionally by a `context_map` YAML passed at
  runtime.
- Extensions are managed as addons (data files) and hooks (Python packages
  that install namespaced addon assets).
