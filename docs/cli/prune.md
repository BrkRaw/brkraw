# prune

Create a "pruned" dataset zip for sharing or archiving, using a pruner spec.

The goal of `brkraw prune` is to make Paravision datasets easier to share by:

- keeping only the files you need (or dropping sensitive/unnecessary files)
- optionally stripping JCAMP comment lines (`$$ ...`)
- optionally editing or deleting specific JCAMP parameters (via `update_params`)
- producing a reproducible sidecar (`.prune.yaml`) describing what was done

This is especially useful when you want to share a dataset with collaborators
without exposing private metadata or irrelevant files.

---

## Basic usage

Prune a dataset using a spec file path:

```bash
brkraw prune /path/to/dataset --spec /path/to/prune_spec.yaml
```

Use an installed pruner spec by name:

```bash
brkraw prune /path/to/dataset --spec-name minimal_share
```

Write to a specific zip path:

```bash
brkraw prune /path/to/dataset --spec prune_spec.yaml --output out.zip
```

---

## What a pruner spec controls

A pruner spec is a YAML mapping that defines:

- which files to keep or drop (`files` + `mode`)
- optional directory-level filters (`dirs`)
- optional JCAMP edits (`update_params`)
- optional root folder handling inside the zip (`add_root`, `root_name`)
- optional comment stripping for JCAMP files (`strip_jcamp_comments`)

`files` is always required and must contain at least one selector.

Selectors are matched by either:

- full dataset-relative path (e.g. `pdata/1/visu_pars`)
- basename only (e.g. `visu_pars`)

---

## keep vs drop

### mode: keep

Only files matching `files` are included.

Example:

```yaml
mode: keep
files:
  - visu_pars
  - reco
  - method
  - acqp
```

### mode: drop

Files matching `files` are excluded, everything else is included.

Example:

```yaml
mode: drop
files:
  - subject
  - patient
  - private_notes.txt
```

Notes:

- The selection is evaluated after directory rules (if any).
- If no files remain after applying rules, the prune fails.

---

## Directory rules (dirs)

`dirs` allows filtering by directory names at specific path levels.

Each rule is a mapping:

- level: integer (1-based)
- dirs: list of directory names allowed or disallowed (depends on mode)

Example: keep only scans 3 and 5 (level 1 is usually scan folder level)

```yaml
dirs:
  - level: 1
    dirs: [3, 5]
```

Example: keep only reco folders `1` and `2` (level 3 is often pdata level)

```yaml
dirs:
  - level: 3
    dirs: [1, 2]
```

CLI overrides:

--scan-ids overrides a level=1 dirs rule
--reco-ids overrides a level=3 dirs rule

Examples:

```bash
brkraw prune /path/to/dataset --spec prune.yaml --scan-ids 3 5
brkraw prune /path/to/dataset --spec prune.yaml --reco-ids 1,2
```

Notes:

- The CLI override rules are applied as:
    - scan_ids: level=1
    - reco_ids: level=3

---

## JCAMP parameter edits (update_params)

`update_params` allows you to edit or delete JCAMP parameter keys in selected files.

Structure:

```yaml
update_params:
  <filename>:
    <PARAM_KEY>: <value-or-null>
```

Rules:

- The map key is a filename (basename only), not a full path.
- If a file with that basename is included, it will be rewritten in the output zip.
- Values are converted to strings internally (except null).
- If the value is null, the key is removed (or cleared depending on Parameters behavior).

Example:

```yaml
update_params:
  subject:
    SUBJECT_id: null
    SUBJECT_name: null
  method:
    Operator: null
```

Important:

- Updates are applied by parsing the file as JCAMP parameters.
- If parsing fails, prune fails with an error.
- Updates apply only to files that are included by keep/drop selection.

---

## Strip JCAMP comments

Some Paravision parameter files include comment lines starting with `$$`.
You can remove them from files that are included in the zip.

From CLI:

```bash
brkraw prune /path/to/dataset --spec prune.yaml --strip-jcamp-comments
```

From spec:

```yaml
strip_jcamp_comments: true
```

Behavior:

- If a file is being rewritten due to update_params, comment stripping is applied after edits.
- If a file is included and looks like JCAMP, it can be stripped even without update_params.

---

## Output zip naming

### Default behavior

If `--output` is not provided, BrkRaw tries to use `root_name` from the spec.
If the spec has no root_name, you must provide `--output`.

When a default output is generated, it is written to the current working directory.

### Root folder in the zip

The zip can include a top-level root directory (recommended for clean unpacking).

Spec fields:

- add_root: true or false (default: true)
- root_name: string (optional)

Notes:

- When `--output` is provided, the root folder name defaults to the output filename stem.
- You can override that with root_name in the spec (or by not providing --output).

---

## Template variables in spec

The CLI supports simple template variables, substituted into the spec before execution.

Use:

```bash
--set-var KEY=VALUE
```

Example:

```bash
brkraw prune /path/to/dataset --spec prune.yaml --set-var Project=CAMRI
```

In the spec, reference it using `$KEY`:

```yaml
root_name: "$Project_shared"
```

Notes:

- Substitution is recursive for all strings in the spec.
- Unknown variables are left unchanged.

---

## Spec validation

By default, prune specs are validated against the schema.

Disable validation:

```bash
brkraw prune /path/to/dataset --spec prune.yaml --no-validate
```

---

## Sidecar output (.prune.yaml)

After pruning, BrkRaw writes a sidecar next to the output zip:

```text
<output>.prune.yaml
```

It contains:

- timestamp (UTC)
- input path and output path
- the spec path and a summary of spec keys
- CLI overrides (mode, strip_jcamp_comments, scan_ids, reco_ids, set_vars)
- computed overrides (root_name_override, dirs_override, template_vars)

This sidecar is meant to make pruning reproducible and auditable.

---

## Example prune spec

This is a minimal example that keeps only a few core parameter files,
drops large raw data, and removes subject identifiers.

```yaml
__meta__:
  name: minimal_share
  description: Minimal shareable dataset (no raw data, anonymized params)

mode: keep
files:
  - method
  - acqp
  - reco
  - visu_pars
  - subject

dirs:
  - level: 1
    dirs: [3]
  - level: 3
    dirs: [1]

update_params:
  subject:
    SUBJECT_id: null
    SUBJECT_name: null

add_root: true
root_name: "shared_scan3"
strip_jcamp_comments: true
```

---

## Common pitfalls

- A prune spec must include `files` with at least one selector.
- `update_params` matches by basename only (not full path).
- `--scan-ids` and `--reco-ids` override directory rules at fixed levels (1 and 3).
- If filtering removes all files, pruning fails.
- If a JCAMP file cannot be parsed for updates, pruning fails.
