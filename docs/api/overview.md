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
[Data access](data-access.md).

## Entry point

All workflows start by loading a dataset:

```python
import brkraw as brk
loader = brk.load("/path/to/study")
```

The returned object acts as a dataset loader and the primary handle for
inspection and conversion.

Loading a dataset is non-destructive and does not modify the source files.

## Curated API Surface (`brkraw.api`)

For scripts and notebooks, BrkRaw also provides a curated, lazily-imported API
surface under `brkraw.api`. This is a convenient way to access “manager”
modules (addons/hooks) and resolver modules without importing deep internal
paths.

Example:

```python
from brkraw.api import BrukerLoader
from brkraw.api import addon_manager, hook_manager

loader = BrukerLoader("/path/to/study")
hooks = hook_manager.list_hooks()
addons = addon_manager.list_installed()
```

Context maps, the config layout and prune are also exposed:

```python
from brkraw.api import context_map, layout, pruner

cmap = context_map.load_context_map("/path/to/20240101_mouse01.yaml")
name = layout.render_layout(loader, 3, layout_template="sub-{Subject.ID}/scan-{ScanID}")
files = pruner.select_files("/path/to/study")
```

!!! note "Changed in 0.6.0"
    `brkraw.api.addon` (context map functions) was renamed
    `brkraw.api.context_map`; the old name is gone. `brkraw.api.layout` is
    new. `addon_manager` (installing spec and rule files) is unchanged.

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

- Output naming and metadata generation are controlled by the config
  (`config.yaml`) and, per dataset, by a context map next to the dataset
  (see [Context maps](../extensions/context-map.md)).
- `loader.convert()` without `reco_id` converts the first reco; the CLI
  without `-r` converts every reco.
- `loader.get_dataobj(scan_id, reco_id, axis=..., frames=...)` selects frames
  like `brkraw convert --axis/--frames`; `cycle_index` / `cycle_count` still
  work with a `DeprecationWarning` (removed in 0.7.0).
- Extensions are managed as addons (data files) and hooks (Python packages
  that install namespaced addon assets).
