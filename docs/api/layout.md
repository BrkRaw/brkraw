# Layout (Python API)

Helpers for building filenames from info/metadata specs.

Module: `brkraw.core.layout`

---

## Equivalent CLI behavior

The CLI (`brkraw convert`) uses the layout system to build output paths and
handles de-duplication, sanitization, and multi-slicepack suffixes.

In the Python API, `render_layout()` only builds a path string. You then pass
that path to `to_filename()` yourself.

---

## render_layout

```python
from brkraw.core import layout as layout_core

out_path = layout_core.render_layout(
    loader,
    scan_id=3,
    layout_entries=[
        {"key": "Study.ID", "entry": "study", "sep": "/"},
        {"key": "Subject.ID", "entry": "sub", "sep": "/"},
        {"key": "Protocol", "hide": True},
    ],
)
```

Use it when writing files:

```python
from pathlib import Path

nii = loader.convert(3, reco_id=1)
if nii is None:
    raise RuntimeError("Conversion returned no output.")

Path(out_path).parent.mkdir(parents=True, exist_ok=True)
if isinstance(nii, tuple):
    for i, img in enumerate(nii, start=1):
        img.to_filename(f"{out_path}_part{i}.nii.gz")
else:
    nii.to_filename(f"{out_path}.nii.gz")
```

If both `layout_entries` and `layout_template` are provided, the template wins.

```python
name = layout_core.render_layout(
    loader,
    scan_id=3,
    layout_entries=[{"key": "Subject.ID", "entry": "sub", "sep": "/"}],
    layout_template="sub-{Subject.ID}/scan-{ScanID}",
)
```

Example outputs (same inputs):

```text
layout_entries only  -> sub-001
layout_template only -> sub-001/scan-3
both provided        -> sub-001/scan-3
```

### Fixed keys

These placeholders are always available, regardless of mapped metadata:

- `{ScanID}` / `{scan_id}` / `{scanid}`
- `{RecoID}` / `{reco_id}` / `{recoid}` (may be `None`)
- `{Counter}` / `{counter}` (used for de-duplication)

You can override specs for testing via API-only kwargs:

```python
name = layout_core.render_layout(
    loader,
    scan_id=3,
    layout_entries=[{"key": "Protocol", "hide": True}],
    override_info_spec="info_override.yaml",
    override_metadata_spec="metadata_override.yaml",
)
```

Fields:

- `key`: dotted key resolved from the layout info (for example `Subject.ID`).

- `entry`: prefix label used to emit `entry-value` (optional; default entry is derived from `key` when `hide` is false).

- `hide`: when true, only the value is appended.

- `use_entry`: reuse a previously defined `entry` value.

- `sep`: separator to insert between fields (default `_`, use `/` for folders).

- `value_pattern`: regex that defines allowed characters (default `[A-Za-z0-9._-]`).

- `value_replace`: replacement for disallowed characters (default `""`).

- `max_length`: truncate values longer than this length.

Notes:

- Values come from merged `info_spec` + `metadata_spec` results.

- Missing values are skipped.
- For `layout_template`, missing placeholders render as empty strings.

- When no parts remain, the fallback is `scan-<ScanID>`.

- `use_entry` only works when the referenced entry was recorded (for example, it is not recorded when `hide: true` and `entry` is omitted).

- `context_map` is optional. When provided, it applies runtime remapping rules to spec output.
- Metadata still wins on conflicts when keys overlap.

## Layout info parts

```python
info, metadata = layout_core.load_layout_info_parts(
    loader,
    scan_id=3,
)
```

Notes:

- `info` is the mapped `info_spec` output.
- `metadata` is the mapped `metadata_spec` output.

## Slice pack suffixes

```python
info = layout_core.load_layout_info(
    loader,
    scan_id=3,
)
suffixes = layout_core.render_slicepack_suffixes(
    info,
    count=3,
    template="_slpack{index}",
)
```

Notes:

- `{index}` is always 1-based.
