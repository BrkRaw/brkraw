# Rule Syntax Guide (specs.rules module)

This document describes the rule syntax used to select specs and hooks
from `~/.brkraw/rules/*.yaml`. Rule files are loaded in filename order and
evaluated top to bottom. If multiple rules match the same category, the last
matching rule wins (override).

## Rule File Layout

A rule file may contain any of the following top-level keys. You can mix them
in a single file.

- `info_spec`: rules that choose which scan metadata spec to use when calling

  info-related commands or methods (for example, metadata parsing in the scan
  resolver).

- `metadata_spec`: rules that choose which metadata spec to use when generating

  sidecar metadata, especially when a separate rule set is needed for metadata
  creation.

- `converter_hook`: rules that choose a converter hook. These are

  used by the loader when converting to NIfTI so that a custom reconstruction
  can be selected for scans matching the rule conditions.

Example:

```yaml
info_spec:

  - name: "mrs-info"

    description: "MRS method uses custom info spec"
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

    description: "MRS reconstruction plugin"
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

## Rule Fields

Each rule item supports:

- `name` (required): identifier for logging/debugging.

- `description` (optional): human-readable explanation.

- `when` (optional): variable bindings using remapper-style sources. Each

  variable may include `transform` to normalize values before matching.

- `if` (required when `when` is present): condition expression using the variables from `when`.

- `use` (required): target spec name or spec path, or hook name.

- `version` (optional): spec version to select when `use` is a spec name.

- Default rules can omit `when`/`if`, but must be the first entry in a category.

## Variable Binding (`when`)

`when` defines named variables using remapper-style sources. Each variable name
is available in the `if` expression using `$<name>`. If a variable binding uses
`transform`, the transform name is resolved from the spec referenced by `use`
via `__meta__.transforms_source`.

See `docs/contrib/spec-syntax.md` for details on remapper sources and transforms.

Example:

```yaml
when:
  method:
    sources:

      - file: acqp

        key: ACQ_XXX
    transform: normalize_method
```

This binds `$method` to the first available value from the sources list.

## Conditions (`if`)

The `if` field uses a simple structured expression. Supported operators:

- `always`: `true` or `false`

- `eq`: `["$var", "value"]`

- `ne`: `["$var", "value"]`

- `in`: `["$var", ["A", "B"]]`

- `regex`: `["$var", "^prefix"]`

- `startswith`: `["$var", "prefix"]`

- `contains`: `["$var", "substring"]`

- `gt`, `ge`, `lt`, `le`: numeric comparisons

- `any`: list of expressions (OR)

- `all`: list of expressions (AND)

- `not`: single expression (NOT)

Example:

```yaml
if:
  any:

    - eq: ["$method", "XXXX"]

    - in: ["$method", ["A", "B", "C"]]

```

## Targets (`use`)

- `info_spec`/`metadata_spec` can use a spec name or a YAML spec path under

  `~/.brkraw/specs/` (or another configured root).

- Transforms for `info_spec`/`metadata_spec` are defined in the spec file under

  `__meta__.transforms_source`.

- `converter_hook` uses the hook name registered under

  `brkraw.converter` (or another configured group).

When `use` is a spec name, rules will:

- match `__meta__.category` to the rule category (`info_spec` or `metadata_spec`)

- select `version` if provided, otherwise the latest version

## Override Behavior

All rule files under `~/.brkraw/rules/*.yaml` are loaded in filename order.
If multiple rules match the same category, the last matching rule wins.
