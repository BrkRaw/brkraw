# convert / convert-batch

Convert Bruker Paravision scans into NIfTI files, optionally writing JSON sidecars and applying hooks.

---

## brkraw convert

### Basic usage

Convert a single scan/reco:

```bash
brkraw convert /path/to/study --scan-id 3 --reco-id 1
```

If `path` is omitted, `BRKRAW_PATH` is used.

---

## Scan and reco selection

### --scan-id

Convert a single scan.

If omitted, BrkRaw converts all available scans.

### --reco-id

Convert a single reconstruction within the scan.

If omitted, BrkRaw converts all available reconstructions for each scan.

---

## Output control

### -o, --output

Where to write outputs:

- Directory: write files under that directory.
- File path (`.nii` / `.nii.gz`): treated as a base name in the file's parent directory.
  For multi-slicepack outputs, BrkRaw appends slicepack suffixes.

Examples:

```bash
brkraw convert /path/to/study --scan-id 3 -o out/
brkraw convert /path/to/study --scan-id 3 -o scan3.nii.gz
```

Notes:

- When `--scan-id` is omitted (convert all scans), `--output` must be a directory.
- If `--output` is a file path, `--prefix` cannot be used.
- Output directories are created automatically.

### --prefix

Override the base output name using a template.

The template supports `{Key}` tags from layout info (and can include `/` to build subfolders).

```bash
brkraw convert /path/to/study --scan-id 3 --prefix "{Protocol}_{ScanID}"
```

### Name de-duplication

BrkRaw avoids overwriting existing outputs.

- If your layout or `--prefix` contains `{Counter}`, it will try `Counter=1..` until names are unique.
- If you do not use `{Counter}`, BrkRaw appends `_<N>` (for example `_2`, `_3`, ...) when needed.

BrkRaw also sanitizes invalid characters in rendered names.

### --no-compress

Write `.nii` instead of `.nii.gz` (default: compressed).

```bash
brkraw convert /path/to/study --scan-id 3 --no-compress
```

---

## Sidecar metadata

### --sidecar

Write a JSON sidecar next to each NIfTI output.

```bash
brkraw convert /path/to/study --scan-id 3 --sidecar
```

### --no-convert

Skip NIfTI conversion and only write sidecar metadata (requires `--sidecar`).

```bash
brkraw convert /path/to/study --scan-id 3 --sidecar --no-convert
```

---

## Context maps

### --context-map

Apply a context map YAML for selection and mapping.

```bash
brkraw convert /path/to/study --scan-id 3 --context-map map.yaml --sidecar
```

Notes:

- Context map selectors may skip specific scan/reco pairs.
- Context maps can influence layout metadata (layout template/entries and slicepack suffix) for that run.

---

## Hooks

### --hook-arg

Pass a single hook argument (repeatable):

```bash
brkraw convert /path/to/study --scan-id 3 --hook-arg "<hook-name>:key=value"
```

Format:

```text
HOOK:KEY=VALUE
```

Value coercion:

- `true` / `false` are parsed as booleans.
- integers and floats are parsed when possible.
- otherwise values are treated as strings.

### --hook-args-yaml

Load hook arguments from a YAML file (repeatable). CLI `--hook-arg` values override YAML.

```bash
brkraw convert /path/to/study --scan-id 3 --hook-args-yaml hook_args.yaml
```

Example YAML:

```yaml
hooks:
  <hook-name>:
    key: value
```

Environment variables:

- `BRKRAW_CONVERT_HOOK_ARGS_YAML` (comma-separated paths)
- `BRKRAW_HOOK_ARGS_YAML` (comma-separated paths)

---

## Affines, units, and headers

### --space

Select affine space:

- `raw`
- `scanner`
- `subject_ras` (default)

```bash
brkraw convert /path/to/study --scan-id 3 --space subject_ras
```

### --override-subject-type / --override-subject-pose

Override subject metadata used for subject-view affines (`space=subject_ras` only).

```bash
brkraw convert /path/to/study --scan-id 3 --override-subject-type Quadruped
brkraw convert /path/to/study --scan-id 3 --override-subject-pose Head_Supine
```

### --xyz-units / --t-units

Set NIfTI header units (defaults: `mm`, `sec`).

```bash
brkraw convert /path/to/study --scan-id 3 --xyz-units mm --t-units sec
```

### --header

Provide a YAML file containing NIfTI header overrides.

```bash
brkraw convert /path/to/study --scan-id 3 --header header.yaml
```

---

## Multi-dimensional data

### --flatten-fg

Flatten frame-group dimensions to 4D when data is 5D or higher.

```bash
brkraw convert /path/to/study --scan-id 3 --flatten-fg
```

### --cycle-index / --cycle-count

Read only a subset of cycles from multi-cycle data (last axis).

```bash
brkraw convert /path/to/study --scan-id 3 --cycle-index 0 --cycle-count 10
```

If `--cycle-count` is set but `--cycle-index` is omitted, BrkRaw defaults `cycle-index` to `0`.

---

## brkraw convert-batch

Convert all datasets under a root folder.

```bash
brkraw convert-batch /path/to/datasets -o out/
```

Dataset discovery:

- subdirectories under the root folder
- zip files directly under the root folder

Notes:

- `--output` must be a directory for `convert-batch`.
- failures in one dataset do not stop the whole batch, but a full run with zero successes is treated as an error.

---

## Environment defaults

Many flags can be provided through environment variables (commonly set via `brkraw session set`).

Common ones:

- `BRKRAW_PATH`
- `BRKRAW_SCAN_ID`
- `BRKRAW_RECO_ID`
- `BRKRAW_CONVERT_OUTPUT`
- `BRKRAW_CONVERT_PREFIX`
- `BRKRAW_CONVERT_SIDECAR`
- `BRKRAW_CONVERT_CONTEXT_MAP`
- `BRKRAW_CONVERT_SPACE`
- `BRKRAW_CONVERT_COMPRESS`
- `BRKRAW_CONVERT_FLATTEN_FG`
- `BRKRAW_CONVERT_CYCLE_INDEX`
- `BRKRAW_CONVERT_CYCLE_COUNT`
- `BRKRAW_CONVERT_OVERRIDE_SUBJECT_TYPE`
- `BRKRAW_CONVERT_OVERRIDE_SUBJECT_POSE`
- `BRKRAW_CONVERT_XYZ_UNITS`
- `BRKRAW_CONVERT_T_UNITS`
- `BRKRAW_CONVERT_HEADER`
