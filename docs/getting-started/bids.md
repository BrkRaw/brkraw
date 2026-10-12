# BIDS integration

brkraw can write a BIDS-style folder tree directly from a ParaVision study:
you put a context map next to the dataset, and `brkraw convert` names every
output from it. The context map holds your project's choices (subject and
session labels, which method is `anat` or `func`, run numbers, how to split a
field map); brkraw does not guess them.

!!! note "Changed in 0.6.0"
    BIDS output through context maps is new in 0.6.0 (context map format v3).
    The 0.5.x guidance on this page ("not for general users yet") no longer
    applies. See [Migrating to 0.6](migrating.md).

What brkraw does and does not do:

- It writes the paths and file names you define, NIfTI files, and JSON
  sidecars (`-c`) from the metadata spec plus the fields your context map adds.
- It does not validate the result against the BIDS specification and does
  not write `dataset_description.json`, `participants.tsv` or events files.
  Run the [BIDS validator](https://bids-standard.github.io/bids-validator/)
  on the result.

## Example

A study folder `20240101_mouse01` with a RARE scan (3), two resting-state EPI
runs (5 and 6) and a field map with two echoes (8). Save this as
`20240101_mouse01.yaml` next to the study folder:

<!-- example: bids-context-map -->
```yaml
__meta__:
  category: context_map
  layout_template: "sub-{bids.sub}/ses-{bids.ses}/{bids.datatype}/sub-{bids.sub}_ses-{bids.ses}[_task-{bids.task}][_run-{bids.run}]_{bids.suffix}"

bids:
  sub: "01"
  ses: baseline
  datatype: {from: MethodBase, map: {EPI: func, RARE: anat, FieldMap: fmap}}
  suffix: {from: MethodBase, map: {EPI: bold, RARE: T2w, FieldMap: fieldmap}}
  task: {when: {MethodBase: EPI}, value: rest}
  run:
    - {when: {ScanID: 5}, value: 1}
    - {when: {ScanID: 6}, value: 2}

convert:
  - {when: {MethodBase: {in: [Localizer, TriPilot]}}, value: false}

split:
  when: {MethodBase: FieldMap}
  value:
    - {axis: echo, frames: 0, bids: {suffix: magnitude1}}
    - {axis: echo, frames: 1, bids: {suffix: phasediff}, sidecar: {EchoNumber: 2}}

sidecar:
  TaskName: {from: bids.task}
```

Then convert:

```bash
brkraw convert /path/to/20240101_mouse01 -o /path/to/bids -c
```

Result (NIfTI files; each has a `.json` sidecar next to it):

<!-- example: bids-paths -->
```text
sub-01/ses-baseline/anat/sub-01_ses-baseline_T2w.nii.gz
sub-01/ses-baseline/fmap/sub-01_ses-baseline_magnitude1.nii.gz
sub-01/ses-baseline/fmap/sub-01_ses-baseline_phasediff.nii.gz
sub-01/ses-baseline/func/sub-01_ses-baseline_task-rest_run-1_bold.nii.gz
sub-01/ses-baseline/func/sub-01_ses-baseline_task-rest_run-2_bold.nii.gz
```

This example is checked by brkraw's test suite on a synthetic study.

How it works:

- `MethodBase` is the method name without the vendor prefix: the scan's
  `Method` is `Bruker:EPI`, its `MethodBase` is `EPI`. Use `brkraw info` to
  see the values of your data.
- `[_task-{bids.task}]` and `[_run-{bids.run}]` disappear for scans where
  the value is empty (the RARE and the field map scans).
- The field map scan is split on its echo axis into two outputs; each part
  sets its own `suffix`, and the second part adds `EchoNumber` to its sidecar.
- `TaskName` is added to the sidecar of the EPI scans only (it is empty for
  the others, so no field is added).
- If two scans end up with the same path, nothing is written and brkraw names
  the scans (add a `run` value, or `on_collision: suffix`).

## Typical choices

| Need | Context map |
| --- | --- |
| Subject label from the dataset | `sub: {from: Subject.ID}` |
| Session from the study | `ses: {from: Session.ID}` (the study ID unless the data gives a session) |
| Skip localizers | `convert: [{when: {MethodBase: {in: [Localizer, TriPilot]}}, value: false}]` |
| Drop dummy volumes | `split: {when: {MethodBase: EPI}, value: [{axis: cycle, frames: "5:"}]}` |
| One file per slice pack | add `[_sp{utils.slicepack}]` or `[_acq-sp{utils.slicepack}]` to the template |
| Same settings for many datasets | a base map shared with `include` (see [Context maps](../extensions/context-map.md#sharing-a-base-map-include)) |

## Sidecar metadata

The metadata spec installed with `brkraw init --install-default` writes
sidecar fields from the DICOM metadata definitions in the ParaVision manual,
not the full BIDS sidecar specification. Add or remove fields per project
with the context map's `sidecar` section. Modality-specific BIDS metadata
(for example diffusion or perfusion fields) is expected from extension
packages and hooks.

## Related documents

- [Context maps](../extensions/context-map.md): full syntax
- [convert](../cli/convert.md): options
- [Layout and naming](../extensions/layout.md): the config layout, used when
  there is no context map
