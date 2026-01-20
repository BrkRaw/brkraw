# Output Layout and Naming

The layout system defines how converted outputs are named and organized on
disk. It consumes structured metadata produced by specs and optionally
remapped by context maps.

Layout logic is purely about **paths and filenames**. It does not inspect raw
Bruker parameters and does not perform metadata mapping itself.

---

## Purpose

Layouts are used to:

- generate standardized directory structures
- construct filenames from metadata fields
- hide or expose metadata keys in paths
- support project-specific naming conventions (for example BIDS-like layouts)

Layouts do **not**:

- select scans (rules do that)
- compute metadata values (specs do that)
- remap values conditionally (context maps do that)

---

## Data flow overview

```text
Bruker parameters
    ↓
specs (info_spec / metadata_spec)
    ↓
context map (optional, runtime)
    ↓
layout (entries or template)
    ↓
output paths and filenames
```

---

## Where layout configuration lives

Layout configuration can be defined in three places, evaluated in this order:

1. Runtime context map (`context_map.__meta__`)
2. Global config (`config.yaml`)
3. Built-in defaults

The first definition found wins.

---

## Layout configuration options

Two layout mechanisms are supported:

- `layout_entries` (structured, recommended)
- `layout_template` (string template)

You may use either or both, but `layout_template` takes precedence if defined.

---

## layout_entries

`layout_entries` defines a structured path builder.

Example:

```yaml
__meta__:
  layout_entries:
    - key: Study.ID
      entry: study
      sep: "/"
    - key: Subject.ID
      entry: sub
      sep: "/"
    - key: Session
      entry: ses
      sep: "/"
    - key: Modality
      hide: true
```

Each entry supports:

- `key`
    - metadata field name
    - dotted keys are supported
- `entry`
    - path label (for example `sub`, `ses`, `run`)
    - omitted entries are skipped
- `sep`
    - separator appended after the entry
    - usually `/` or `_`
- `hide`
    - if true, the key is not rendered
    - still available for template or downstream logic

---

### Resulting path example

Given metadata:

```json
{
  "Study": {"ID": "001"},
  "Subject": {"ID": "003"},
  "Session": "baseline",
  "Modality": "T1w"
}
```

Result (Modality `hide: true` only omits the entry label, not the value):

```text
study-001/sub-003/ses-baseline/T1w
```

Example (missing values are skipped; common when a spec does not emit `Modality`):

```json
{
  "Study": {"ID": "001"},
  "Subject": {"ID": "003"},
  "Session": "baseline"
}
```

Result:

```text
study-001/sub-003/ses-baseline/
```

---

## layout_template

`layout_template` defines a full path as a format string.

Example:

```yaml
__meta__:
  layout_template: "study-{Study.ID}/sub-{Subject.ID}/ses-{Session}/{Modality}"
```

Rules:

- `{Key}` placeholders are replaced with metadata values
- missing keys raise an error unless a default exists upstream
- template overrides `layout_entries` entirely

Use templates when:

- strict compatibility is required
- external standards mandate exact paths

---

## Fixed keys

Some placeholders are always available, even if they are not present in mapped
metadata. These are referred to as *fixed keys*.

- `{ScanID}` / `{scan_id}` / `{scanid}`: current scan id.
- `{RecoID}` / `{reco_id}` / `{recoid}`: current reconstruction id (may be empty when not applicable).
- `{Counter}` / `{counter}`: run-local counter used for de-duplication.

These fixed keys work in both:

- `layout_template` placeholders
- `layout_entries` via `key: ScanID` / `key: RecoID` / `key: Counter`

---

## slicepack suffix

For multi-slicepack acquisitions, an optional suffix may be applied.

```yaml
__meta__:
  slicepack_suffix: "_sl{index}"
```

- `{index}` is 1-based
- appended to filenames, not directories
- applied only when slicepacks are present

---

## Interaction with context maps

Context maps may define layout metadata:

```yaml
__meta__:
  layout_entries: ...
  layout_template: ...
```

Important rules:

- context-map layout applies **only for that run**
- it does not persist or modify global config
- layout metadata does not affect mapping rules

---

## Filename construction

Layouts define directory structure. Filenames are built from:

- scan ID
- reco ID
- modality or protocol fields
- slicepack suffix (if applicable)

Exact filename patterns are controlled by:

- layout configuration
- converter behavior
- selected converter hook (if any)

---

## Error handling

Layout evaluation fails if:

- a required key is missing
- a template placeholder cannot be resolved
- metadata contains invalid path characters

Errors are raised before any files are written.

---

## Best practices

- Prefer `layout_entries` for readability and composability
- Use `layout_template` only when exact paths are required
- Keep specs free of layout logic
- Use context maps for project-specific naming
- Avoid embedding scan IDs directly into specs

---

## Related documents

- [Spec syntax](specs.md)
- [Context map syntax](context-map.md)
- [Rule syntax](rules.md)
- [Extensibility model](extensibility.md)
