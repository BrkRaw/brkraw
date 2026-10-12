# Migrating to 0.6

What changes when you move from brkraw 0.5.x to 0.6.0, and what to do.
0.6.0 changes names and syntax directly: old names do not keep working as
aliases (the one exception is the cycle options below).

## Checklist

| If you use | Do this |
| --- | --- |
| a context map (0.5.x syntax) | rewrite it in the v3 format ([below](#context-maps)) |
| `brkraw convert-batch` | `brkraw convert --batch` |
| `brkraw config init` | `brkraw init` |
| `brkraw prune --spec-name NAME` | `brkraw prune --spec NAME` |
| `brkraw prune --scan-ids` / `--reco-ids` | `-s` / `--scan-id`, `-r` / `--reco-id` |
| `brkraw prune --mode keep/drop` | `--files` / `--exclude-files` (or `mode:` in the spec) |
| the built-in spec `deid4share` | `anonymize` (`brkraw prune --anonymize`) |
| `brkraw convert --cycle-index/--cycle-count` | `--axis cycle --frames START:STOP` (the old options still work until 0.7.0, with a warning) |
| Python `get_dataobj(..., cycle_index=, cycle_count=)` | `get_dataobj(..., axis="cycle", frames="START:STOP")` (old arguments warn until 0.7.0) |
| `from brkraw.api import addon` (context maps) | `from brkraw.api import context_map` |
| `BRKRAW_CONVERT_CONTEXT_MAP` / `session set --convert-option CONTEXT_MAP=…` | put the map next to the dataset with the same name, or use `-M FILE` |
| NIfTI files made with 0.5.7 | see [Outputs that change](#outputs-that-change-from-057) before comparing or combining |

## Context maps

The context map format was rewritten (v3). A 0.5.x file stops with a message
naming the old word.

| 0.5.x | 0.6.0 |
| --- | --- |
| `Subject.ID: {type: mapping, values: {...}}` (changed the original value) | originals are read only; define `bids: {sub: {from: Subject.ID, map: {...}}}` in a namespace |
| `cases:` | a list of value specs; the first whose `when` holds wins |
| `selector:` | `convert: [{when: {...}, value: false}]` |
| `__split__` with `cycle_index` / `cycle_count` | `split:` with `{axis, frames}` (numpy rules) |
| `__meta__.layout_entries` | `__meta__.layout_template` with namespace tags and `utils` |
| `__meta__.slicepack_suffix` | `[_sp{utils.slicepack}]` in the template |
| `--context-map` for every run | same-name file next to the dataset is found automatically (`__meta__.category: context_map`) |
| names repeated → `_2` | names repeated → error, nothing written (or `on_collision: suffix`) |

- Match methods with `MethodBase` (`EPI`); `Method` keeps the original value
  (`Bruker:EPI`).
- `brkraw info` shows each reco's frame axes ("Frame axes: echo(2), cycle(3)"),
  the names used by `split` and `--axis`.
- The full syntax is in [Context maps](../extensions/context-map.md); a
  complete example is in [BIDS integration](bids.md).

## prune

- `brkraw prune DATA` without a spec now copies the chosen scans **unchanged**
  into `pruned_<study>.zip` (it used to stop and ask for a spec). Nothing is
  anonymized by default.
- `--anonymize` applies the example spec `anonymize` and writes
  `pruned_anon_<subject-id>_<study-id>.zip`. A custom spec with
  `anonymize: true` is named and recorded the same way.
- A `$name` placeholder left unfilled now stops the run; `--set-var` without
  `=` is an error.
- `-o` changes only the file name, not the top folder inside the zip.
- An existing output is not replaced without `--overwrite`.
- The `.prune.yaml` record holds names only (no full paths; no input name
  when anonymizing).
- New: `--files`, `--exclude-files`, `--institution`, `--dry-run`, spec keys
  `jcamp_headers` and `anonymize`.
- The spec format has its own page: [Pruner specs](../extensions/pruner-specs.md).

## Command line

- `--root DIR` is available on every brkraw command (as `BRKRAW_CONFIG_HOME`).
- Without a path, commands use the study set with `brkraw session`, or on a
  scanner console the study open in ParaVision (asking which one in a
  terminal when several are open).
- `brkraw init --yes` writes `config.yaml` with defaults and changes no shell
  file; add the shell helpers with `--shell-rc FILE` (0.6.0b1 appended them
  to `~/.zshrc` or `~/.bashrc` by itself).
- `brkraw convert -s` takes several scans: `-s 3 4 5` or `-s 3,4,5` (then
  `--output` is a folder). With `-r`, every named scan must have that reco,
  else nothing is written. `BRKRAW_SCAN_ID="3,4"` from `brkraw session` now
  converts both scans (before: only the first).
- `brkraw params` prints its result to standard output (before: through the
  log, so `logging.level: WARNING` hid it). It searches one scan: a
  `BRKRAW_SCAN_ID` with several ids is an error.

## Outputs that change from 0.5.7

If you compare files written by 0.6.0 with files written by 0.5.7, these
differences are fixes, not regressions. Convert again with 0.6.0 before
comparing or combining.

### Subject orientation (affine)

The subject orientation of all 16 poses is rebuilt from one list of steps.

- Default output (`space="subject_ras"`): 8 poses change — Biped Head_Left,
  Head_Right; Quadruped Head_Supine, Foot_Supine, Head_Left, Head_Right,
  Foot_Left, Foot_Right.
- Scanner space: 4 poses change (Foot_Left and Foot_Right for Biped and
  Quadruped).
- With a pose or subject-type override: 12 poses change.

### Intensity scaling (slope and offset)

ParaVision stores one slope (`VisuCoreDataSlope`) and offset
(`VisuCoreDataOffs`) value per frame (one 2D slice or one 3D volume). A NIfTI
header holds only one.

- **0.5.7** put the first value in the header for the whole image.
- **0.6.0** keeps one header value when all values are exactly the same (the
  output is identical to 0.5.7, integer data). When the values differ, it
  applies each value to its own frames and writes floating-point data with
  header slope 1 (the files are larger).
- **0.6.0a1** stopped with "VisuCoreDataSlope has N values" on every reco with
  more than one frame per slice (multi-echo, DTI, repeated scans, multi-frame
  3D). 0.6.0b1 fixes this; 0.6.0a1 should not be used for such data.
- In brkraw's test data (61 datasets, 582 recos), 11 recos change from 0.5.7,
  all with slopes that differ per frame: 10 DTI images (reco 2; the slopes
  differ by factors from 10³ to about 10⁹) and one functional (fMRI) time
  series whose slope differs per repetition (up to about 3 %).
  With 0.5.7 those images were scaled with the first frame's value only.
  All other recos give the same values as 0.5.7.
- The layout rule and its warnings are described under
  [Intensity scaling](../cli/convert.md#intensity-scaling).

## Shared context maps

- A base map shared by many datasets is installed with `brkraw addon add`
  into the config folder's new `context_maps/` folder and included by name;
  hook packages can ship base maps too (manifest key `context_maps`). A
  dataset's own map stays next to the dataset. See
  [Context maps](../extensions/context-map.md#installing-a-base-map).

## New warnings

- brkraw warns when the frames of one slice pack do not share one
  orientation, or when a slope or offset is stored with more than one
  dimension that does not match the frame axes. The data is converted as
  before; check such scans.
