# Convert scans to NIfTI

`brkraw convert` is the core command for converting Bruker Paravision scans
into NIfTI files, with optional metadata sidecars and extensible conversion
logic via hooks.

This command is designed for interactive inspection, scriptable workflows,
and batch processing in real research environments.

## Basic usage

Convert a single scan and reco:

```bash
brkraw convert /path/to/study --scan-id 3 --reco-id 1
```

By default:

- Output is written to the current directory
- Files are compressed (.nii.gz)
- Affines are computed in subject_ras space
- Output filenames follow the configured layout rules

## Selecting scans and reconstructions

### --scan-id

Specify the scan ID to convert.

```bash
brkraw convert /path/to/study --scan-id 5
```

If omitted, all available scans are converted (batch behavior).

### --reco-id

Specify the reconstruction ID.

```bash
brkraw convert /path/to/study --scan-id 5 --reco-id 2
```

Notes:

- If omitted, all recos for the selected scans are converted
- Some converter hooks may not use reco IDs explicitly

## Output control

### --output

Control where converted files are written.

Write to a directory:

```bash
brkraw convert /path/to/study --scan-id 3 --output out/
```

Write to a specific file:

```bash
brkraw convert /path/to/study --scan-id 3 --output scan3.nii.gz
```

Rules:

- When converting multiple scans, --output must be a directory
- When --output is a file, --prefix cannot be used

### --prefix

Override the filename layout using a template.

```bash
brkraw convert /path/to/study --scan-id 3 --prefix "{Protocol}_{ScanID}"
```

Template fields are resolved from layout info and metadata specs.

### Output name collisions

BrkRaw avoids overwriting outputs when output names collide.

- If your template uses `{Counter}`, it starts at `1` and increments until the output name is unique.
- If your template does not use `{Counter}`, BrkRaw appends `_<N>` (for example `_2`, `_3`, ...) as needed.

### Compression

By default, output is written as .nii.gz.

Disable compression:

```bash
brkraw convert /path/to/study --scan-id 3 --no-compress
```

## Metadata sidecars

### --sidecar

Write a JSON sidecar file next to each NIfTI output.

```bash
brkraw convert /path/to/study --scan-id 3 --sidecar
```

Sidecar metadata is generated from:

- Built-in info specs
- Installed metadata specs
- Optional context maps

### --no-convert

Skip NIfTI conversion and only write sidecar metadata (requires `--sidecar`).

```bash
brkraw convert /path/to/study --scan-id 3 --sidecar --no-convert
```

## Affine handling

### --space

Select the affine space used for conversion.
Values are case-sensitive.

Valid values:

- raw
- scanner
- subject_ras

Example:

```bash
brkraw convert /path/to/study --scan-id 3 --space subject_ras
```

### --override-subject-type

Override the subject type used when computing subject-view affines
(space=subject_ras only).

Valid values (case-sensitive):

- Biped
- Quadruped
- Phantom
- Other
- OtherAnimal

Example:

```bash
brkraw convert /path/to/study --scan-id 3 --override-subject-type Quadruped
```

### --override-subject-pose

Override the subject pose used when computing subject-view affines
(space=subject_ras only).

Valid values (case-sensitive):

- Head_Supine
- Head_Prone
- Head_Left
- Head_Right
- Foot_Supine
- Foot_Prone
- Foot_Left
- Foot_Right

Example:

```bash
brkraw convert /path/to/study --scan-id 3 --override-subject-pose Head_Supine
```

### Axis flip

Flip the x-axis in the output affine:

```bash
brkraw convert /path/to/study --scan-id 3 --flip-x
```

### --flatten-fg

Flatten frame-group dimensions into a 4D time axis when data is 5D or higher.

```bash
brkraw convert /path/to/study --scan-id 3 --flatten-fg
```

Notes:

- 4D or smaller data is unchanged.
- Extra dimensions are collapsed into the 4th dimension in order.

## Units and headers

### Spatial and temporal units

```bash
brkraw convert /path/to/study --scan-id 3 --xyz-units mm --t-units sec
```

Values are validated strictly and are case-sensitive.

### Header overrides

Provide a YAML file to override NIfTI header fields:

```bash
brkraw convert /path/to/study --scan-id 3 --header header_override.yaml
```

## Context maps and selection

### --context-map

Apply metadata remapping and conditional selection logic.

```bash
brkraw convert /path/to/study --context-map bids_map.yaml --sidecar
```

Context maps can:

- Select or skip scans
- Modify metadata fields
- Override layout rules and slice-pack suffixes

## Converter hooks

### --hook-arg

Pass arguments to installed converter hooks.

```bash
brkraw convert /path/to/study --scan-id 3 --hook-arg mrs:reference=water
```

Format:

```text
HOOK_NAME:KEY=VALUE
```

Values are parsed as bool, int, float, or string.

### --hook-args-yaml

Load hook arguments from a YAML file (repeatable). CLI `--hook-arg` values override YAML.

```bash
brkraw convert /path/to/study --scan-id 3 --hook-args-yaml hook_args.yaml
```

Example YAML:

```yaml
hooks:
  mrs:
    reference: water
    peak_ppm: 3.02
```

You can also set `BRKRAW_CONVERT_HOOK_ARGS_YAML` (comma-separated paths).

## Batch conversion

### brkraw convert-batch

Convert all datasets under a root directory.

```bash
brkraw convert-batch /path/to/datasets --output out/
```

Notes:

- Each subdirectory or zip file is treated as a dataset
- Failures in one dataset do not stop the batch

## Environment defaults (advanced)

brkraw convert respects environment variables set via brkraw session set.

Example:

```bash
brkraw-set -p /path/to/study -s 3 -r 1
brkraw convert
```

See session.md for details.

## Common pitfalls

- All affine-related options are case-sensitive
- --output must be a directory when converting multiple scans
- Output names are deduped automatically; use `{Counter}` to control the numeric suffix position
- Invalid subject overrides are rejected early
- Missing metadata selectors may silently skip scans

## Looking ahead

BrkRaw focuses on robust conversion and extensibility.
Project-specific organization logic (scan-aware or modality-aware BIDS layouts)
is planned in a dedicated tool: brkraw-bids.
