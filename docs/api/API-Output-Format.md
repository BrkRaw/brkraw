# API: output_format

Helpers for building filenames from info specs.

Module: `brkraw.core.output_format`

## render_output_format

```python
from brkraw.core import output_format as output_format_core

name = output_format_core.render_output_format(
    loader,
    scan_id=3,
    output_format_fields=[
        {"key": "Study.ID", "entry": "study", "sep": "/"},
        {"key": "Subject.ID", "entry": "sub", "sep": "/"},
        {"key": "Protocol", "hide": True},
    ],
    output_format_spec="metadata_common",
    context_map="maps.yaml",
)
```

Fields:

- `key`: dotted key resolved from the output format spec (for example `Subject.ID`).

- `entry`: prefix label used to emit `entry-value` (optional when `hide` is true).

- `hide`: when true, only the value is appended.

- `use_entry`: reuse a previously defined `entry` value.

- `sep`: separator to insert after this field (default `_`, use `/` for folders).

- `value_pattern`: regex that defines allowed characters (default `[A-Za-z0-9._-]`).

- `value_replace`: replacement for disallowed characters (default `""`).

- `max_length`: truncate values longer than this length.

Notes:

- Values come from the output format spec (or built-in study/scan info).

- Missing values are skipped.

- When no parts remain, the fallback is `scan-<ScanID>`.

- `context_map` overrides the spec `__meta__.context_map` at runtime.

## Slice pack suffixes

```python
info = output_format_core.load_output_format_info(
    loader,
    scan_id=3,
    output_format_spec="metadata_common",
)
suffixes = output_format_core.render_slicepack_suffixes(
    info,
    count=3,
    template="_{SliceOrient}",
)
```

Notes:

- `{index}` is always 1-based.

- `{SliceOrient}` resolves from the default info spec when present.
