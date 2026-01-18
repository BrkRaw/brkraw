# Rule Syntax Reference

Rules select which specs and converter hooks apply to a scan. They are evaluated
against Bruker Paravision parameters and are the primary mechanism for
conditional behavior in BrkRaw.

Rule files are loaded from the config root and evaluated in filename order.

---

## Purpose

Rules are used to:

- select an `info_spec` for inspection output
- select a `metadata_spec` for sidecar metadata generation
- select a `converter_hook` for custom conversion pipelines

Rules do **not** modify metadata directly. They only choose which specs or hooks
are active.

---

## BIDS-focused example (short)

Assume you have a BIDS-oriented info spec, metadata spec, and converter hook
installed. A single rule file can wire them together for a specific method.

```yaml
info_spec:
  - name: "bids-bold-info"
    when:
      Method:
        sources:
          - file: method
            key: Method
    if:
      eq: ["$Method", "EPI"]
    use: "bids_bold_info"

metadata_spec:
  - name: "bids-bold-metadata"
    when:
      Method:
        sources:
          - file: method
            key: Method
    if:
      eq: ["$Method", "EPI"]
    use: "bids_bold_metadata"

converter_hook:
  - name: "bids-bold-hook"
    when:
      Method:
        sources:
          - file: method
            key: Method
    if:
      eq: ["$Method", "EPI"]
    use: "bids_bold_hook"
```

Result (conceptually):

- `brkraw info` becomes modality-specific for EPI scans (info spec).
- metadata sidecars are shaped for BIDS fields (metadata spec).
- conversion behavior is customized for that modality (converter hook).

---

## Evaluation model

Rules are evaluated in this order:

1. Rule files are loaded in filename order.
2. Within each file, rules are evaluated top to bottom.
3. Rules are grouped by category (`info_spec`, `metadata_spec`, `converter_hook`).
4. If multiple rules match the same category, the **last matching rule wins**.

This override behavior allows later rules to specialize or replace defaults.

---

## Rule file structure

A rule file is a YAML mapping. It may contain any of the following top-level keys:

- `info_spec`
- `metadata_spec`
- `converter_hook`

Each key maps to a list of rule entries.

Example:

```yaml
info_spec:
  - name: "mrs-info"
    description: "MRS scans use custom info spec"
    when:
      method:
        sources:
          - file: acqp
            key: ACQ_XXX
    if:
      eq: ["$method", "MRS"]
    use: "mrs"
    version: "1.0.0"

converter_hook:
  - name: "mrs-reco"
    description: "Custom MRS reconstruction"
    when:
      method:
        sources:
          - file: acqp
            key: ACQ_XXX
    if:
      any:
        - eq: ["$method", "MRS"]
        - in: ["$method", ["MRS2", "MRS3"]]
    use: "mrs-reco"
```

---

## Rule entry fields

Each rule entry supports the following fields.

### name (required)

```yaml
name: "mrs-info"
```

Identifier used for logging and debugging.

---

### description (optional)

```yaml
description: "MRS scans use custom info spec"
```

Human-readable explanation.

---

### when (optional)

```yaml
when:
  method:
    sources:
      - file: acqp
        key: ACQ_XXX
```

Defines variable bindings using remapper-style sources.

- Each key under `when` defines a variable.
- Variable values are resolved from Paravision parameter files.
- Variables are referenced in conditions as `$<name>`.

If `when` is present, `if` is required.

---

### if (required when `when` is present)

```yaml
if:
  eq: ["$method", "MRS"]
```

Defines the condition under which the rule matches.

Supported operators:

- `always`: `true` or `false`
- `eq`, `ne`
- `in`
- `regex`
- `startswith`
- `contains`
- `gt`, `ge`, `lt`, `le`
- `any` (OR)
- `all` (AND)
- `not` (NOT)

Example:

```yaml
if:
  any:
    - eq: ["$method", "EPI"]
    - in: ["$method", ["BOLD", "FMRI"]]
```

---

### use (required)

```yaml
use: "mrs"
```

Target selected when the rule matches.

- For `info_spec` and `metadata_spec`, this may be:
  - a spec name (recommended)
  - a spec path under the config root
- For `converter_hook`, this must be a hook name registered under
  `brkraw.converter_hook`

---

### version (optional)

```yaml
version: "1.0.0"
```

Used when `use` refers to a spec by name.

Behavior:

- if provided, the exact version is selected
- if omitted, the latest available version is selected

---

## Default rules

A rule entry may omit `when` and `if`.

```yaml
info_spec:
  - name: "default-info"
    use: "default"
```

Default rules:

- always match
- must appear **first** in their category
- serve as a fallback when no other rules match

---

## Variable binding details

Variables defined in `when`:

- are resolved before condition evaluation
- may use transforms defined in the selected spec
- are available only within the rule entry

Example with transform:

```yaml
when:
  method:
    sources:
      - file: acqp
        key: ACQ_XXX
    transform: normalize_method
```

Transforms are resolved from the spec referenced by `use` via
`__meta__.transforms_source`.

---

## Category constraints

Rules selecting specs must match spec metadata:

- `info_spec` rules require specs with `__meta__.category: info_spec`
- `metadata_spec` rules require specs with `__meta__.category: metadata_spec`

Mismatches raise validation errors during rule installation.

---

## Common patterns

### Sequence-specific metadata

```yaml
metadata_spec:
  - name: "epi-meta"
    when:
      Method:
        regex: "^EPI"
    use: "epi_metadata"
```

### Custom reconstruction routing

```yaml
converter_hook:
  - name: "fid-reco"
    when:
      Method:
        eq: "FID_SEQ"
    use: "fid-reconstruction"
```

---

## Design notes

- rules only select behavior; they do not modify values
- override behavior is explicit and deterministic
- rule order matters
- rules are the primary integration point between scanner parameters
  and extensibility logic

---

## Related documents

- [Extensibility model](extensibility.md)
- [Spec syntax reference](specs.md)
- [Context map syntax](context-map.md)
- [Addon management](../api/addon.md)
- [Converter hooks](../api/hook.md)
