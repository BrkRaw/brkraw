# Context maps

A context map is a small YAML file that sits next to a dataset and says how
that dataset should be named and described on output: which scans to convert,
how to split multi-frame scans, what to add to sidecars, and where each file
goes. It never changes the information brkraw reads from the dataset.

!!! note "Changed in 0.6.0"
    Context maps were rewritten in 0.6.0 (format v3). Files written for 0.5.x
    (`type: mapping`, `cases`, `selector`, `target`, `override`, `__split__`,
    `__meta__.layout_entries`) no longer load; brkraw stops with a message that
    names the old word. See [Migrating to 0.6](../getting-started/migrating.md).

## Layers

brkraw works in three layers:

1. **Original information** (read only): what the info specs read from the
   dataset, for example `Subject.ID`, `Study.ID`, `Method`, `MethodBase`,
   `Protocol`, `ScanID`, `RecoID`.
2. **Context map**: defines new values in namespaces you name (for example
   `bids`). It reads the original information and never overwrites it.
3. **Layout**: builds the output path. Either the config layout (see
   [Layout and naming](layout.md)) or the context map's own
   `layout_template`.

The config layout and the context map layout are **independent**. They use
different tags and different rules, and brkraw does not mix them. When the
context map has a `layout_template`, that template names the files for that
run and the config layout is not used.

## Finding the file

`brkraw convert` looks for a file with the dataset's name next to the dataset:

| Dataset | Context map |
| --- | --- |
| folder `20240101_mouse01` | `20240101_mouse01.yaml` (or `.yml`) |
| file `20240101_mouse01.zip` | `20240101_mouse01.yaml` (the last extension is dropped) |

- Both `.yaml` and `.yml` present is an error.
- A file found by name is used only when its `__meta__.category` is
  `context_map`; otherwise brkraw warns and ignores it.
- `-M FILE` / `--context-map FILE` uses that file instead (one dataset only;
  `convert --batch` uses each dataset's own same-name file).
- `--no-context-map` turns the lookup off.
- The Python API uses the same rule (`brkraw.api.context_map`).

## File structure

```yaml
__meta__:
  category: context_map          # required for a file found by name
  layout_template: "sub-{bids.sub}/ses-{bids.ses}/{bids.datatype}/sub-{bids.sub}_ses-{bids.ses}[_run-{bids.run}]_{bids.suffix}"
  on_collision: error            # or: suffix

bids:                            # a namespace: field -> value spec
  sub: "01"
  ses: {from: Session.ID}
  datatype: {from: MethodBase, map: {EPI: func, RARE: anat, FieldMap: fmap}}

convert: ...                     # which scans to convert
split: ...                       # parts of one scan
sidecar: ...                     # fields added to the JSON sidecar
```

| Top-level key | Meaning |
| --- | --- |
| `__meta__` | `category`, `layout_template`, `on_collision`, `include`, and `name` / `version` / `description` (for installed maps) |
| any other name | a **namespace**: `field: value spec`. Letters, digits and `_`, starting with a letter; not an original name (`Subject`, `Study`, `Session`, `ScanID`, `RecoID`, `Method`, `MethodBase`, `Protocol`) |
| `convert` | value spec; `false` skips the scan, anything else converts it |
| `split` | value spec giving a list of parts, one output each |
| `sidecar` | `field: value spec` added to the sidecar; an empty value removes the field |

Reserved names: `convert`, `split`, `sidecar`, `utils`. `utils` is filled by
brkraw and cannot be defined in a file.

A key with a dot at the top level (for example `Subject.ID:`) is an error
because it would change an original value. Put the value in a namespace
instead (`bids: {sub: ...}`).

## Value specs

Every field takes one of four forms.

| Form | Example | Result |
| --- | --- | --- |
| direct value | `sub: "01"` | the value (`null` is empty). A list or mapping as a value is written `{value: [...]}` |
| `from` | `ses: {from: Session.ID}` | the original value; empty when missing |
| `from` + `map` + `default` | `datatype: {from: MethodBase, map: {EPI: func}, default: misc}` | the table value; `default` when the value is not in the table or missing; empty without `default`. A list is mapped item by item |
| `when` | `task: {when: {MethodBase: EPI}, value: rest}` | the value only when every condition holds; empty otherwise |

`when` can be added to any form. A **list** of value specs gives the first
item whose `when` holds (an item without `when` always holds):

```yaml
bids:
  run:
    - {when: {ScanID: 5}, value: 1}
    - {when: {ScanID: 6}, value: 2}
```

### Conditions

| Condition | Example |
| --- | --- |
| equal | `{MethodBase: EPI}` |
| one of | `{ScanID: {in: [5, 6, 7]}}` |
| regular expression | `{Protocol: {regex: "^rest"}}` |
| not | `{MethodBase: {not: RARE}}`, `{ScanID: {not: {in: [1, 2]}}}` |

A condition on a key that is missing never holds. `ScanID` and `RecoID`
always exist.

### What each part can read

- Namespace fields read **original information only**.
- `convert`, `split`, `sidecar` and `layout_template` read original
  information **and** namespaces (`TaskName: {from: bids.task}`); `convert`,
  `split` and `sidecar` also read the sidecar metadata fields, with or
  without `-c`.
- A namespace field that reads another namespace is an error, so the order
  of fields never matters.

### Original values: use the real value

Values are compared exactly as brkraw reads them. The method, for example, is
`Bruker:EPI`, not `EPI`. For matching on the method name, use `MethodBase`,
which brkraw gives without the vendor prefix (`Bruker:EPI` → `EPI`,
`User:zte_anat` → `zte_anat`); `Method` keeps the original value. Check the
values of your data with `brkraw info`.

### YAML notes

- Quote IDs that look like numbers: `sub: "01"` (unquoted `01` is the number 1).
- Unquoted `1:30` is read as text (brkraw turns off YAML's base-60 numbers),
  but quote frame ranges anyway: `frames: "1:30"`.

## Converting some scans only

```yaml
convert:
  - {when: {MethodBase: {in: [Localizer, TriPilot]}}, value: false}
```

Scans for which `convert` gives `false` are skipped; every other scan is
converted.

## Splitting a scan

`split` gives a list of parts. Each part selects frames on one frame axis and
may set namespace fields and sidecar fields for that output:

```yaml
split:
  when: {MethodBase: FieldMap}
  value:
    - {axis: echo, frames: 0, bids: {suffix: magnitude1}}
    - {axis: echo, frames: 1, bids: {suffix: phasediff}, sidecar: {EchoNumber: 2}}
```

- **`axis`** is a frame axis name in lowercase, as `brkraw info` shows it
  under "Frame axes" (see the table below), or a data axis number (3 or
  more). It can be left out when the scan has one frame axis. Every part of
  one scan uses the same axis.
- **`frames`** follows numpy indexing:
    - an integer `0` keeps one frame and removes the axis (`a[..., 0]`);
    - a list `[0, 2]` keeps those frames in that order and keeps the axis;
    - a quoted `"start:stop[:step]"` is a Python slice and keeps the axis
      (`"5:"` drops the first five frames).
- Indexes start at 0; negative indexes count from the end.
- Errors: an unknown or uppercase axis name, `slice` (use
  `utils.slicepack` instead), an index outside the axis, a selection with no
  frame, step 0, the same frame twice in one part, `cycle_index` /
  `cycle_count` (0.5 syntax).
- Frames in more than one part, or in no part, are allowed and written to
  the log as notes.
- Order: slice packs first, then the parts inside each pack, then
  `--flatten-fg`.

### Frame axis names

| In `split` and `--axis` | ParaVision frame group (`VisuFGOrderDesc`) |
| --- | --- |
| `echo` | `FG_ECHO` |
| `cycle` | `FG_CYCLE` |
| `diffusion` | `FG_DIFFUSION` |
| `dti` | `FG_DTI` |
| `movie` | `FG_MOVIE` |
| `cardiac_movie` | `FG_CARDIAC_MOVIE` |
| `coil` | `FG_COIL` |
| `complex` | `FG_COMPLEX` |
| — | `FG_SLICE` (a spatial axis, not a split axis; slice packs use `utils.slicepack`) |

Any other frame group `FG_X` is named `x` (lowercase, without `FG_`).

## Sidecar fields

```yaml
sidecar:
  TaskName: {from: bids.task}
  InstitutionName: null            # empty: removes the field
```

Fields are added to the sidecar that `-c` / `--sidecar` writes (after the
metadata spec). A split part's `sidecar:` fields apply to that part only.

## Output paths: `layout_template`

The template uses namespace fields and `utils` values only:

```yaml
__meta__:
  layout_template: "sub-{bids.sub}/ses-{bids.ses}/{bids.datatype}/sub-{bids.sub}_ses-{bids.ses}[_task-{bids.task}][_run-{bids.run}]_{bids.suffix}"
```

- `{ns.field}` is replaced by the value.
- `[ ... ]` is an optional group: it disappears when a tag inside it is
  empty. Write `\[` and `\]` for literal brackets.
- An empty tag outside `[ ]` is dropped with a warning.
- Original values are not template tags; copy them into a namespace first
  (`scan: {from: ScanID}`).

### `utils` values

| Tag | Value | Empty when |
| --- | --- | --- |
| `utils.counter` | 1, 2, 3 … the first number whose output path is free | the template does not use it |
| `utils.slicepack` | slice pack number, from 1 | the scan has one slice pack |
| `utils.split` | split part number, from 1, in list order | the scan is not split |

`utils` exists only in `layout_template`; a namespace field, `convert`,
`split` or `sidecar` that reads `utils.*` is an error.

### Name collisions

brkraw plans every output path before writing anything.

- Two outputs of the run with the same path, or a path that already exists
  (the NIfTI file, or its sidecar with `-c`), is an **error** by default:
  nothing is written and the message names the scans.
- `on_collision: suffix` adds `_2`, `_3` … instead.
- brkraw never adds a slice pack or split suffix by itself. A multi-pack or
  split scan collides unless the template uses `utils.slicepack` /
  `utils.split` (or the parts set different field values); the error message
  names the tag to add, for example `[_sp{utils.slicepack}]`.

## Without `layout_template`

A context map without `layout_template` still applies `convert`, `split` and
`sidecar`. The config layout names the files and can read the namespaces
(for example `{bids.sub}` in the config's `layout_template`); it keeps its own
collision rule (`_2`, `_3` …).

## Sharing a base map: `include`

```yaml
__meta__:
  category: context_map
  include: [lab_base.yaml]   # a path next to this file, a name, or {use: name, version: "1.0.0"}
bids:
  sub: "03"
```

- Included files load in list order; the file itself comes last.
- Merging is per field: the newer file's items go in front of the base's, so
  the newer file wins and the base still covers what the newer file does not
  match. Fields the newer file does not mention are kept from the base.
- `__meta__` merges key by key (the newer value wins). `include`, `name`,
  `version`, `description` and `category` are not inherited.
- A circular include, or a missing name or version, is an error.

### Installing a base map

A dataset's own map stays next to the dataset. A **base map** shared by many
datasets can be installed and then included by name:

```bash
brkraw addon add lab_base.yaml     # needs __meta__.category: context_map, name and version
brkraw addon list                  # "Context Maps" table
brkraw addon rm lab_base.yaml
```

- Installed maps go into the config folder's `context_maps/`
  (`brkraw config path context_maps`). The file is validated before it is
  installed.
- Hook packages (for example `brkraw-bids`) can ship base maps with the
  manifest key `context_maps`; `brkraw hook install` puts them under
  `context_maps/<package namespace>/`.

How an `include` item is found:

1. Text that looks like a path (contains `/`, starts with `.`, or ends with
   `.yaml` / `.yml`) is a file relative to the including file.
2. Any other text is a `__meta__.name`, looked up in `context_maps/` (maps
   added with `brkraw addon add` and maps installed by hook packages); the
   highest `version` wins.
3. `{use: name, version: "1.0.0"}` picks that exact version.

Two installed files with the same name and version are an error (pin the
version or remove one).

## Python API

```python
from brkraw.api import context_map

cmap = context_map.load_context_map("20240101_mouse01.yaml")      # load and validate
context_map.validate_context_map("20240101_mouse01.yaml")         # raises on errors
path = context_map.find_context_map("/path/to/20240101_mouse01")  # same-name lookup
```

`context_map.plan_scan(info, cmap, scan_id=..., reco_id=..., metadata=...)`
returns the namespaces, `convert`, `split` and sidecar for one scan; the
original `info` is not changed.

## Related documents

- [BIDS integration](../getting-started/bids.md): a complete example
- [Layout and naming](layout.md): the config layout
- [convert](../cli/convert.md): `-M`, `--no-context-map`, `--axis`, `--frames`
- [Migrating to 0.6](../getting-started/migrating.md)
