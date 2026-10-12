# Layout (Python API)

Build output names with the **config layout** from Python. The CLI
(`brkraw convert`) also handles repeated names, invalid characters and slice
pack suffixes; `render_layout()` only returns the name. The two layouts
(config and context map) are compared in
[Layout and naming](../extensions/layout.md).

```python
from brkraw.api import layout
```

## `render_layout`

```python
import brkraw as brk
from brkraw.api import layout

loader = brk.load("/path/to/study")
name = layout.render_layout(
    loader,
    3,                                   # scan ID
    reco_id=1,
    layout_entries=[
        {"key": "Study.ID", "entry": "study", "sep": "/"},
        {"key": "Subject.ID", "entry": "sub", "sep": "/"},
        {"key": "Protocol", "hide": True},
    ],
)
```

- With both `layout_entries` and `layout_template`, the template wins.
- Fixed keys `{ScanID}`, `{RecoID}` and `{Counter}` (`counter=`) are always
  available.
- `extra={"bids": {...}}` adds values the tags can read, for example context
  map namespaces.
- `override_info_spec=` / `override_metadata_spec=` use other specs (for
  testing); metadata values are read only with `override_metadata_spec`.
- Entry fields: `key`, `entry`, `hide`, `sep`, `use_entry`, and
  `value_pattern` (allowed characters, default `[A-Za-z0-9._-]`),
  `value_replace` (replacement, default empty), `max_length`.
- Missing values are skipped; when nothing remains the name is
  `scan-<ScanID>`.

Writing the files yourself:

```python
from pathlib import Path

nii = loader.convert(3, reco_id=1)
Path(name).parent.mkdir(parents=True, exist_ok=True)
images = nii if isinstance(nii, tuple) else (nii,)
suffixes = layout.render_slicepack_suffixes(
    layout.load_layout_info(loader, 3, reco_id=1), count=len(images), template="_slpack{index}"
) if len(images) > 1 else [""]
for img, suffix in zip(images, suffixes):
    img.to_filename(f"{name}{suffix}.nii.gz")
```

## Information the tags read

```python
info, metadata = layout.load_layout_info_parts(loader, 3, reco_id=1)
```

`info` is the original study and scan information (`Subject`, `Study`,
`Method`, `MethodBase`, `Protocol`, …). `metadata` is filled only with
`override_metadata_spec`. `load_layout_info()` returns both merged.

## Context map names

A context map with its own `layout_template` is rendered by
`brkraw.api.context_map` during `brkraw convert`; see
[Context maps](../extensions/context-map.md).
