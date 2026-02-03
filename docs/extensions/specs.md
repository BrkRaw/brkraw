# Spec Syntax Reference

Specs define how Bruker Paravision parameter files are mapped into structured
outputs. They are pure mapping recipes: no conditional selection, no runtime
state, no project-specific logic.

Specs are selected by rules and evaluated by the remapper engine.

---

## Purpose

Specs are used to:

- define fields shown by `brkraw info`
- generate structured metadata dictionaries
- populate sidecar JSON files (for example BIDS-style metadata)
- provide normalized values for layout and naming

Specs do **not**:

- decide *when* they apply (rules do that)
- modify values conditionally per project (context maps do that)
- control output filenames directly

---

## Info specs (inspection-focused)

Info specs shape what `brkraw info` shows. When paired with a rule, they can
make the output modality-aware.

Example info spec (assume `bids_bold_info` is installed):

```yaml
__meta__:
  name: "bids_bold_info"
  version: "1.0.0"
  category: "info_spec"
  transforms_source: "<spec-name>_transforms.py"

Modality:
  sources:
    - file: method
      key: Method
  transform: to_bids_modality

TaskName:
  sources:
    - file: method
      key: PVM_FMRI_Name
```

Before rule (default info spec):

```text
Protocol: EPI
Method: EPI
```

After rule selects `bids_bold_info`:

```text
Modality: bold
TaskName: rest
```

---

## Metadata specs (sidecar-focused)

Metadata specs control JSON sidecars for conversion. Keep them small and
structured, then let layout handle filenames.

Example metadata spec (assume `bids_bold_metadata` is installed):

```yaml
__meta__:
  name: "bids_bold_metadata"
  version: "1.0.0"
  category: "metadata_spec"
  transforms_source: "<spec-name>_transforms.py"

RepetitionTime:
  sources:
    - file: method
      key: PVM_RepetitionTime
  transform: ms_to_s

PhaseEncodingDirection:
  sources:
    - file: method
      key: PVM_EPI_PhaseEncDir
  transform: to_bids_phase_dir
```

Resulting sidecar fragment:

```json
{
  "RepetitionTime": 2.0,
  "PhaseEncodingDirection": "j-"
}
```

---

## Spec file structure

A spec is a YAML mapping with two kinds of top-level entries:

1. `__meta__`: required metadata describing the spec
2. output keys: mapping definitions

Example:

```yaml
__meta__:
  name: "<spec-name>"
  version: "1.0.0"
  description: "Metadata mapping for a specific acquisition family"
  category: "info_spec"
  transforms_source: "<spec-name>_transforms.py"

Subject.ID:
  sources:
    - file: subject
      key: SUBJECT_id
```

---

## **meta** block

Every spec **must** define `__meta__`.

### Required fields

```yaml
__meta__:
  name: "<spec-name>"
  version: "1.0.0"
  description: "Metadata mapping for a specific scan family"
  category: "info_spec"
```

- `name`
    - lowercase snake_case
    - up to four tokens
    - pattern: `^[a-z][a-z0-9]*(?:_[a-z0-9]+){0,3}$`
- `version`
    - free-form string
    - compared lexically unless pinned by rules
- `description`
    - human-readable summary
- `category`
    - required when selected by rules
    - must be one of:
        - `info_spec`
        - `metadata_spec`

---

### Optional meta fields

```yaml
__meta__:
  transforms_source: "transforms.py"
  include: "base.yaml"
  include_mode: "override"
  authors:
    - name: "Jane Doe"
      email: "jane@example.com"
  doi: "10.1234/example"
  citation: "Doe et al., NeuroImage 2024"
```

Supported optional fields:

- `transforms_source`
    - string or list of strings
    - relative to the spec file unless absolute
    - later files override earlier ones
- `include`
    - string or list of spec paths
    - merged before the current spec
- `include_mode`
    - `override` (default): current spec wins
    - `strict`: conflict raises an error
- `authors`, `developers`
- `doi`
- `citation`

---

## Output keys

Each non-`__meta__` top-level key defines one output field.

Keys may be dotted to create nested structures:

```yaml
Study.ID:
  sources:
    - file: subject
      key: SUBJECT_id
```

Produces:

```python
{"Study": {"ID": "1"}}
```

---

## Sources

The simplest mapping uses `sources`.

```yaml
FieldName:
  sources:
    - file: method
      key: PVM_SPackArrNSlices
```

Each source entry supports:

- `file`: one of:
    - `method`
    - `acqp`
    - `visu_pars`
    - `reco`
    - `subject`
- `key`: parameter name inside that file
- `reco_id`: optional, for `visu_pars` or `reco`

If multiple sources are listed, the **first available value wins**.

---

## Inputs (derived fields)

Use `inputs` when a field depends on multiple values.

```yaml
out.joined:
  inputs:
    a:
      sources:
        - file: method
          key: PVM_SPackArrNSlices
    b:
      const: 3
  transform: join_fields
```

Rules:

- exactly one of `sources`, `inputs`, `const`, or `ref` is required
- `inputs` may reference:
    - `sources`
    - `const`
    - `ref` (previously resolved output)
    - `$scan_id`, `$reco_id`

You can also define constant or reference rules directly at the top level:

```yaml
FieldName:
  const: 1

FieldCopy:
  ref: "FieldName"
```

---

## Transforms

Transforms are Python functions referenced by name.

```yaml
FieldName:
  sources:
    - file: acqp
      key: ACQ_XXX
  transform: normalize_method
```

Behavior:

- a single transform receives the resolved value
- a list applies transforms sequentially
- with `inputs`, the first transform receives keyword arguments
- an empty transform list is invalid

Transforms must be available in the transform registry:

- for file-based specs, this registry is loaded from `__meta__.transforms_source`
- for programmatic use, pass `transforms={...}` into `map_parameters(...)`

!!! important "Transforms Require transforms_source"
    If you use `transform:` anywhere in a spec file, you must ensure BrkRaw can
    load those functions.
    - When loading from YAML with `load_spec(...)`, set `__meta__.transforms_source`
      so `load_spec(...)` returns a non-empty `transforms` registry.
    - When building specs programmatically, pass `transforms={...}` to `map_parameters(...)`.
    If you reference transforms but provide no registry, mapping will fail at
    runtime (missing transform function).

### Inline inputs inside sources (advanced)

`sources:` items may include an inline `inputs:` block (optionally with a `transform:`).
This is useful when you want a computed fallback in a `sources` chain.

```yaml
FieldName:
  sources:
    - inputs:
        a:
          sources:
            - file: method
              key: PVM_SPackArrNSlices
        b:
          const: 3
      transform: join_fields
    - file: method
      key: PVM_SPackArrNSlices
```

---

## Defaults and requirements

Input entries (inside `inputs:`) may define:

```yaml
default: 1
```

- `default`: fallback if no input value is found

Input entries (inside `inputs:`) may also define:

```yaml
required: true
```

- `required`: missing input raises an error (instead of returning `None`)

Output rules do not have a `required` flag; use `sources` ordering or an inline
`inputs` source entry for fallbacks.

---

## Study-level behavior

When a Study-like object is used as the source:

- only `file: subject` is allowed
- at least one subject source must be present

---

## What specs intentionally do not handle

Specs do **not** define:

- conditional overrides per project
- subject or session remapping
- scan selection logic
- output layout rules

Those belong to:

- **rules** (selection)
- **context maps** (runtime remapping)
- **layout configuration** (naming)

---

## Relationship to context maps

Specs produce **canonical outputs**.

Context maps:

- are supplied at runtime
- operate *after* spec evaluation
- may override or extend spec outputs
- may introduce selectors for conversion

See [Context map syntax](context-map.md) for mapping rules and schema.

---

## Validation

To validate a spec file (including transform sources), prefer loading it through
the spec loader:

```python
from brkraw.specs.remapper import load_spec, map_parameters

spec, transforms = load_spec("spec.yaml", validate=True)
result = map_parameters(scan, spec, transforms=transforms)
```

Validation checks:

- schema compliance
- transform source paths (when validating a spec file)
- source correctness

---

## Related documents

- [Rule syntax](rules.md)
- [Context map syntax](context-map.md)
- [Extensibility model](extensibility.md)
- [Output layout and naming](layout.md)
