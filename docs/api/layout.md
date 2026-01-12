# API: Layout

Helpers for building filenames from info/metadata specs.

Module: `brkraw.core.layout`

## render_layout

```python
from brkraw.core import layout as layout_core

name = layout_core.render_layout(
    loader,
    scan_id=3,
    layout_entries=[
        {"key": "Study.ID", "entry": "study", "sep": "/"},
        {"key": "Subject.ID", "entry": "sub", "sep": "/"},
        {"key": "Protocol", "hide": True},
    ],
    context_map="maps.yaml",
)
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

- `entry`: prefix label used to emit `entry-value` (optional when `hide` is true).

- `hide`: when true, only the value is appended.

- `use_entry`: reuse a previously defined `entry` value.

- `sep`: separator to insert after this field (default `_`, use `/` for folders).

- `value_pattern`: regex that defines allowed characters (default `[A-Za-z0-9._-]`).

- `value_replace`: replacement for disallowed characters (default `""`).

- `max_length`: truncate values longer than this length.

Notes:

- Values come from merged `info_spec` + `metadata_spec` results.

- Missing values are skipped.

- When no parts remain, the fallback is `scan-<ScanID>`.

- `context_map` applies runtime mapping rules to the spec output.
- Metadata still wins on conflicts when keys overlap.
- When `context_map.__meta__` defines `layout_entries` or `layout_template`, those
  can be passed explicitly to `render_layout` to override config defaults.

## Layout info parts

```python
info, metadata = layout_core.load_layout_info_parts(
    loader,
    scan_id=3,
    context_map="maps.yaml",
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
    template="_{SliceOrient}",
)
```

Notes:

- `{index}` is always 1-based.

- `{SliceOrient}` resolves from the default info spec when present.
