# convert

Convert ParaVision scans to NIfTI files, optionally with JSON sidecars.

```bash
brkraw convert /path/to/study                    # every scan and reco
brkraw convert /path/to/study -s 3 -r 1 -o out/  # one scan, one reco
brkraw convert /path/to/study -s 3 4 5 -o out/   # three scans (also -s 3,4,5)
brkraw convert /path/to/studies --batch -o out/  # every study in a folder
```

If the path is omitted, `BRKRAW_PATH` is used (set with `brkraw session`),
or on a scanner console the study open in ParaVision.

!!! note "Changed in 0.6.0"
    `brkraw convert-batch` became `brkraw convert --batch`. Context maps use
    the v3 format and are found next to the dataset by name. `--axis` and
    `--frames` select frames; `--cycle-index` / `--cycle-count` still work
    but are deprecated. See [Migrating to 0.6](../getting-started/migrating.md).

## Selection

| Option | Meaning |
| --- | --- |
| `-s`, `--scan-id` | Scan ID(s) to convert: `-s 3`, `-s 3 4 5` or `-s 3,4,5`. Without it, every scan is converted. With two or more, `--output` must be a folder. |
| `-r`, `--reco-id` | Reco ID to convert. Without it, every reco of each scan is converted. With `-s`, every named scan must have this reco, else nothing is written; without `-s`, scans that lack it are skipped and a warning names them (no scan with it: nothing is written). |

A scan ID that the dataset does not have stops the run before anything is
written.
| `--batch` | Convert every dataset in the folder `path` (sub-folders and `.zip` files directly under it). Not with `-s`, `-r` or `-M`. |

With `--batch`, one failed dataset does not stop the others; the run fails
only when no dataset was converted. Each dataset uses its own same-name
context map, if any.

## Output

| Option | Meaning |
| --- | --- |
| `-o`, `--output` | A folder, or a `.nii` / `.nii.gz` file name for one scan. Without `-s`, it must be a folder. Folders are created. |
| `--prefix` | File name template with `{Key}` tags of the config layout (may contain `/`). Not with a file `-o`. When given, a context map's `layout_template` is not used. |
| `--no-compress` | Write `.nii` instead of `.nii.gz`. |
| `-M`, `--context-map` | Context map file to use instead of the same-name file next to the dataset. |
| `--no-context-map` | Use no context map, not even the same-name file. |

### How files are named

- **With a context map that has `layout_template`:** the template names every
  output. All paths are planned first; if two outputs get the same path, or a
  path (or its sidecar with `-c`) already exists, nothing is written and the
  scans are named. `on_collision: suffix` adds `_2`, `_3` … instead. See
  [Context maps](../extensions/context-map.md).
- **Otherwise:** the config layout names the files (see
  [Layout and naming](../extensions/layout.md)). Names that repeat get `_2`,
  `_3` …, or the next `{Counter}` value when the layout uses `{Counter}`.
  Several slice packs get the config's slice pack suffix.

Invalid characters in names are replaced.

## Metadata

| Option | Meaning |
| --- | --- |
| `-c`, `--sidecar` | Write a JSON sidecar next to each NIfTI file (metadata spec plus the context map's `sidecar` fields). |
| `--no-convert` | Write sidecars only (needs `-c`). |

## Orientation

| Option | Meaning |
| --- | --- |
| `-S`, `--space` | Affine space: `raw`, `scanner` or `subject_ras` (default). |
| `-T`, `--override-subject-type` | Subject type for the subject-view affine (`subject_ras` only). |
| `-P`, `--override-subject-pose` | Subject pose for the subject-view affine (`subject_ras` only). |

## Data

| Option | Meaning |
| --- | --- |
| `-F`, `--flatten-fg` | Flatten frame axes into one 4th axis when the data has 5 or more axes. |
| `--axis` | Frame axis for `--frames`: a name shown by `brkraw info` under "Frame axes" (`echo`, `cycle`, …) or an axis number (3 or more). Can be left out when the data has one frame axis. |
| `--frames` | Frames to keep, numpy style: `2` (one frame, the axis is removed), `2,0` (a list, the axis is kept), `1:3` (a slice `start:stop[:step]`, the axis is kept). |
| `-I`, `--cycle-index`, `-N`, `--cycle-count` | Deprecated, removed in 0.7.0: a block of cycles on the last axis. Use `--axis cycle --frames START:STOP`; brkraw warns and shows the equivalent. Not together with `--axis` / `--frames`. |

```bash
brkraw convert /path/to/study -s 5 -o rest.nii.gz --axis cycle --frames 5:   # drop 5 dummy volumes
brkraw convert /path/to/study -s 8 -o echo1.nii.gz --axis echo --frames 0
```

Frame axis names follow the ParaVision frame groups (`FG_ECHO` → `echo`,
`FG_CYCLE` → `cycle` …); the table is in
[Context maps](../extensions/context-map.md#frame-axis-names). Slice packs are
split first, then frames are selected in each pack.

### Intensity scaling

brkraw applies the ParaVision slope and offset (`VisuCoreDataSlope`,
`VisuCoreDataOffs`); slope and offset are handled separately.

- When all values are exactly the same, the value goes into the NIfTI header
  and the data keeps its stored integer type.
- When the values differ per slice pack or per frame, brkraw applies each
  value to its own frames and writes floating-point data (larger files).
- The number of values is compared first with the number of slice packs,
  then with the frame axes multiplied from the last one (one value per frame
  when it matches all of them). When nothing matches, brkraw warns and writes
  the data without scaling.
- brkraw also warns when the frames of one slice pack do not share one
  orientation, or when a slope or offset is stored with more than one
  dimension that does not match the frame axes.

## Hooks

| Option | Meaning |
| --- | --- |
| `-H`, `--hook-arg` | `HOOK:KEY=VALUE`, repeatable. `true`/`false`, integers and floats are converted; everything else is text. |
| `--hook-args-yaml` | YAML file with hook arguments (repeatable). `-H` values win. |

```yaml
hooks:
  <hook-name>:
    key: value
```

A hook may stop a scan before it starts because it would need more memory than
its limit (for example SORDINO, `max_memory_gb`). In a terminal, `convert` then
shows the reason and asks `Proceed anyway with max_memory_gb=... for scan N? [y/N]`;
`y` converts that scan once more with the proposed value. Without a terminal
the scan fails with the message, as any other conversion error; give the value
with `-H sordino:max_memory_gb=...` to run it.

## NIfTI header

| Option | Meaning |
| --- | --- |
| `--xyz-units` | Spatial units in the header (default `mm`). |
| `--t-units` | Time units in the header (default `sec`). |
| `--header` | YAML file with header values to set. |

## Config folder

`--root DIR` uses another config folder (default: `BRKRAW_CONFIG_HOME`, else
`~/.brkraw`).

## Environment defaults

Options can also come from environment variables, usually set with
`brkraw session set`: `BRKRAW_PATH`, `BRKRAW_SCAN_ID`, `BRKRAW_RECO_ID`,
`BRKRAW_CONVERT_OUTPUT`, `BRKRAW_CONVERT_PREFIX`, `BRKRAW_CONVERT_SIDECAR`,
`BRKRAW_CONVERT_SPACE`, `BRKRAW_CONVERT_COMPRESS`, `BRKRAW_CONVERT_FLATTEN_FG`,
`BRKRAW_CONVERT_OVERRIDE_SUBJECT_TYPE`, `BRKRAW_CONVERT_OVERRIDE_SUBJECT_POSE`,
`BRKRAW_CONVERT_XYZ_UNITS`, `BRKRAW_CONVERT_T_UNITS`, `BRKRAW_CONVERT_HEADER`,
`BRKRAW_CONVERT_HOOK_ARGS_YAML`, `BRKRAW_HOOK_ARGS_YAML`.
`BRKRAW_CONVERT_CYCLE_INDEX` / `BRKRAW_CONVERT_CYCLE_COUNT` are read like the
deprecated options. `BRKRAW_CONVERT_CONTEXT_MAP` is no longer read (0.6.0).
