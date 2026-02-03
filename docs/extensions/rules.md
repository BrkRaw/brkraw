# Rule Syntax Reference

Rules select which specs and converter hooks apply to a scan. They are evaluated
against Bruker Paravision parameter values and **only select behavior** (they do
not modify metadata).

---

## Evaluation

- Rule files are loaded from the config root, in **filename order**
- Within a file, entries are evaluated **top → bottom**
- Rules are grouped by category: `info_spec`, `metadata_spec`, `converter_hook`
- If multiple entries match a category, the **last matching entry wins**

---

## File shape (YAML)

A rules file is a YAML mapping. Any of these top-level keys may appear:

- `info_spec`: selects which info spec powers `brkraw info`
- `metadata_spec`: selects which metadata spec drives sidecars
- `converter_hook`: selects which conversion hook runs

Each key maps to a list of rule entries:

```yaml
metadata_spec:
  - name: "epi-metadata"
    when:
      Method:
        sources:
          - file: method
            key: Method
    if:
      regex: ["$Method", "^EPI"]
    use: "bids_bold_metadata"
```

Interpretation:

- When the Paravision parameter `method:Method` is mapped to the variable
  `$Method`, if `$Method` matches `^EPI`, select the metadata spec
  `bids_bold_metadata`.

---

## Rule entry fields

Minimal schema:

```yaml
- name: "<id>"
  description: "<optional text>"
  when: { <var>: <binding>, ... }   # optional
  if: <condition>                   # required if `when` exists
  use: "<spec-or-hook>"             # required
  version: "<optional version>"     # optional (specs only)
```

- `name` (required): identifier for logging/debugging
- `description` (optional): human-readable note
- `use` (required): target to select
    - for `info_spec` / `metadata_spec`: spec name (recommended) or a spec path
      under the config root
    - for `converter_hook`: a hook name registered under `brkraw.converter_hook`
- `version` (optional, specs only): pin a spec version; if omitted, the latest
  version is selected
- `when` (optional): variable bindings (see next section)
- `if` (required when `when` exists): match condition (operators below)

---

## Variables (`when`)

`when` binds variables from Paravision parameter files using the same “remapper”
binding shape as specs (i.e., `sources` and optional `transform`). The name
`when` is intended to read as “when these variables (bindings) are available,
evaluate the condition”.

```yaml
when:
  Method:
    sources:
      - file: method
        key: Method
```

Interpretation:

- When the parameter key `Method` is read from the `method` file, bind its value
  to `$Method` for use in `if`.

- Each key under `when` defines a variable name.
- Variables are referenced in conditions as `$<name>` (e.g., `$Method`).
- If you use `transform`, it is resolved from the spec selected by `use` via
  `__meta__.transforms_source` (see [Spec syntax reference](specs.md)).

For the full binding syntax, reuse the spec “Sources/Transforms” rules in
[Spec syntax reference](specs.md).

---

## Conditions (`if`)

`if` is a single operator mapping. Operands can be literals or variables like
`"$Method"`.

### Boolean

```yaml
if: { always: true }
```

Interpretation:

- If evaluated, always match (no variable needed).

### Equality / ordering

```yaml
if: { eq: ["$Method", "EPI"] }
if: { ne: ["$Method", "RARE"] }
if: { gt: ["$SomeNumber", 0] }
if: { ge: ["$SomeNumber", 0] }
if: { lt: ["$SomeNumber", 10] }
if: { le: ["$SomeNumber", 10] }
```

Interpretation:

- If `$Method` equals `EPI`, match.
- If `$Method` is not `RARE`, match.
- If `$SomeNumber` is greater/greater-or-equal/less/less-or-equal than the given
  value, match.

### Membership

```yaml
if: { in: ["$Method", ["EPI", "BOLD", "FMRI"]] }
```

Interpretation:

- If `$Method` is one of `EPI`, `BOLD`, `FMRI`, match.

### Strings

```yaml
if: { regex: ["$Method", "^EPI"] }
if: { startswith: ["$Method", "EPI"] }
if: { contains: ["$Method", "EPI"] }
```

Interpretation:

- If `$Method` matches a regex / starts with / contains the given string, match.

### Composition

```yaml
if:
  any:
    - eq: ["$Method", "EPI"]
    - regex: ["$Method", "^RARE"]

if:
  all:
    - eq: ["$A", 1]
    - ne: ["$B", 2]

if:
  not:
    eq: ["$Method", "EPI"]
```

Interpretation:

- `any`: match if any sub-condition matches (OR).
- `all`: match only if every sub-condition matches (AND).
- `not`: match if the nested condition does not match.

---

## Defaults / fallback

An entry without `when`/`if` always matches:

```yaml
info_spec:
  - name: "default-info"
    use: "default"
```

Interpretation:

- If no explicit `when`/`if` is provided, the entry always matches and selects
  `default` for `info_spec` (unless later rules override it).

Recommendation: put a default entry **first**, and more specific overrides
after it (because the last matching entry wins).

---

## Category constraints (specs)

Rules selecting specs must match the spec’s `__meta__.category`:

- `info_spec` rules → specs with `__meta__.category: info_spec`
- `metadata_spec` rules → specs with `__meta__.category: metadata_spec`

---

## Related

- [Extensibility model](extensibility.md)
- [Spec syntax reference](specs.md)
- [Context map syntax](context-map.md)
- [Addon management](../api/addon.md)
- [Converter hooks](../api/hook.md)
