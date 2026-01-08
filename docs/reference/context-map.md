# Context Map Syntax

Context maps provide a runtime-only mapping layer that is applied **after**
spec and transform resolution. They are used to customize metadata, control
conversion selection, and define output layout behavior without modifying
installed specs or rules.

Context maps are supplied explicitly at runtime and are not installed as
addons.

---

## Purpose and scope

Context maps are intended for:

- project-specific subject, session, or run mapping
- conditional metadata overrides
- scan selection based on mapped values
- output layout and naming customization

They are **not** intended to replace specs or rules. Instead, they operate on
top of spec outputs.

Key properties:

- runtime only (not stored in the config root)
- applied after spec and transform evaluation
- scoped to a single invocation or script
- optional but powerful

---

## High-level model

The evaluation order is:

1. Rules select specs and converter hooks
2. Specs and transforms produce structured outputs
3. Context map rules are applied to those outputs
4. Output selection, metadata sidecars, and layout rendering use the final values

Context maps never affect rule matching. They operate on the resolved outputs.

---

## File format

A context map is a YAML mapping.

Top-level keys correspond to output keys produced by specs, or define new keys.

```yaml
<OutputKey>:
  <rule definition>
```

Each value may be either:

- a single rule object
- a list of rule objects (evaluated top to bottom)

---

## **meta** section

The optional `__meta__` section defines layout-related defaults.

```yaml
__meta__:
  layout_entries:
    - key: Study.ID
      entry: study
      sep: "/"
    - key: Subject.ID
      entry: sub
      sep: "/"
  layout_template: "study-{Study.ID}/sub-{Subject.ID}/{Protocol}"
  slicepack_suffix: "_sl{index}"
```

Notes:

- `__meta__` affects layout rendering only
- it does not affect mapping rules
- values here act as defaults and may be overridden elsewhere

---

## Rule object schema

Each rule object supports the following fields.

### selector

```yaml
selector: true
```

When `true`, the key must produce a mapped value for a scan to be eligible
for conversion.

Selector evaluation uses the merged info and metadata outputs, regardless
of the `target` field.

---

### target

```yaml
target: info_spec
```

Controls which spec output the mapping applies to.

Valid values:

- `info_spec` (default)
- `metadata_spec`

---

### type

```yaml
type: mapping
```

Valid values:

- `mapping`
- `const`

---

### mapping rules (type: mapping)

```yaml
type: mapping
values:
  1: "sub-001"
  2: "sub-002"
default: "unknown"
override: true
```

Behavior:

- input value is looked up in `values`
- if no match is found:

  - `default` is used if provided
  - otherwise the original value is preserved
- `override` controls whether existing values are replaced

---

### constant rules (type: const)

```yaml
type: const
value: "pilot"
override: true
```

Behavior:

- the constant value is assigned directly
- `override` controls whether existing values are replaced

---

### override

```yaml
override: false
```

Controls whether this rule may replace an existing value.

Default behavior:

- `true`: replace existing value
- `false`: fill only if the value is missing

---

### when (conditional rules)

```yaml
when:
  ScanID: 3
  Subject.ID: "TEST"
```

The `when` field restricts rule application based on already-resolved values.

Supported operators include:

- exact match
- `in`
- `regex`
- `not`

Rules are evaluated against the **original spec outputs**, not against values
modified by earlier context map rules.

---

## Rule lists and evaluation order

When a key maps to a list of rules:

```yaml
Modality:
  - when:
      Method:
        in: ["EPI", "BOLD"]
    value: "bold"
    override: true

  - default: "unknown"
```

Evaluation rules:

- rules are evaluated top to bottom
- the first matching rule is applied
- if no rule matches:

  - `default` is used if present
  - otherwise the original value is preserved

---

## Creating new keys

Context maps may define keys that are not produced by specs.

```yaml
Run:
  type: const
  value: 1
```

These keys become available for:

- selector logic
- metadata sidecars
- output layout rendering

---

## Scan selection with selectors

Keys marked with `selector: true` are used to filter conversions.

```yaml
Modality:
  selector: true
  type: mapping
  values:
    1: "T1w"
    2: "T2w"
```

Only scans that produce a value for this key are converted.

---

## Layout interaction

Context map outputs can be referenced by layout definitions.

```yaml
__meta__:
  layout_template: "sub-{Subject.ID}/ses-{Session}/scan-{ScanID}"
```

Layout resolution uses the final values after all context map rules
have been applied.

---

## Validation

Context maps can be validated programmatically.

```python
from brkraw.specs.remapper import validate_context_map

validate_context_map("maps.yaml")
```

Schema:

- `src/brkraw/schema/context_map.yaml`

Validation checks:

- rule structure
- allowed fields and types
- operator correctness

---

## Design notes

- context maps are runtime-only and project-scoped
- they do not affect rule selection
- they are applied after spec and transform evaluation
- they can filter scans via selectors
- they are the preferred way to customize layout and metadata per project

---

## Related documents

- [Extensibility model](extensibility.md)
- [Rule syntax reference](rules.md)
- [Spec syntax reference](specs.md)
- [Output layout and naming](layout.md)
- [Convert API reference](../api/convert.md)
