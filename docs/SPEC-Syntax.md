# SPEC Syntax Guide (specs.remapper module)

This module maps Bruker parameter files into a structured output dictionary.

## Rule Structure

Each top-level key in the spec defines one output field (supports dotted keys
for nesting):

```yaml
__meta__:
  name: "mrs"
  version: "1.0.0"
  description: "Metadata mapping for PRESS/STEAM scans."
  category: "info_spec"
  transforms_source: "mrs_transforms.py"

out.some_field:
  sources:

    - file: method

      key: PVM_SPackArrNSlices
```

`__meta__.transforms_source` is optional. When present, `load_spec` resolves the
path relative to the spec file (absolute paths are allowed). It can also be a
list of transform files; later files override earlier ones. For grouped specs
like `study.yaml` with multiple sections, put `__meta__` under each section.
`__meta__.include` is optional. When present, it can be a string or list of
relative/absolute spec paths to merge before the current spec. Keys in the
current spec override included keys unless `__meta__.include_mode` is set to
`strict`, which raises on conflicts.
`__meta__.context_map` is optional. When present, it points to a YAML mapping file
resolved relative to the spec file.

## Meta Fields

`__meta__` is required on every spec. Required fields:

- `name`: python-friendly identifier using lowercase snake_case with up to four tokens.

  Pattern: `^[a-z][a-z0-9]*(?:_[a-z0-9]+){0,3}$`.

- `version`: version string (free-form).

- `description`: human-readable summary.

- `category`: category string. For rule-selected specs, use `info_spec` or `metadata_spec`.

Optional fields:

- `transforms_source`: transform file path(s) as string or list of strings.

- `include`: spec include path(s).

- `include_mode`: `override` or `strict`.

- `authors` / `developers`: list of people with `name`, optional `email`, optional `affiliations` list.

- `doi`: DOI string.

- `citation`: citation text.

- `context_map`: mapping file path with per-key mapping rules.

## Mapping Rules

Specs can apply lookup tables without writing Python transforms. Provide
`__meta__.context_map` and define per-key mapping rules inside the context map.

```yaml
__meta__:
  name: "metadata_anat"
  version: "1.0.0"
  description: "..."
  category: "metadata_spec"
  context_map: "maps.yaml"

Subject.ID:
  sources:

    - file: subject

      key: SUBJECT_id
```

`maps.yaml`:

```yaml
Subject.ID:
  type: mapping
  values:
    1: "test1"
    2: "test2"
  default: "unknown"
  override: false
```

You can also use constants:

```yaml
Study.ID:
  type: const
  value: "1"
  override: true
```

Conditional rules with `when` can create new keys or override existing ones:

```yaml
Modality:

  - when:

      Subject.ID: "XXXX"
      Study.ID: "YYYY"
    value: "T1w"
    override: true

  - default: "unknown"

Run:

  - when:

      Subject.ID: "XXXX"
      ScanID: 13
    value: 1
    override: true
```

Condition operators:

```yaml
Protocol:

  - when:

      Method:
        in: ["EPI", "BOLD"]
    value: "bold"
    override: true

  - when:

      Method:
        regex: "^T1.*"
    value: "t1w"
    override: true

  - when:

      Subject.ID:
        not: "sub-000"
    value: "include"
```

Aliases:

- `ScanID` / `scan_id`

- `RecoID` / `reco_id`

Behavior:

- Mapping rules apply automatically when a context map entry matches an output key.

- `override: true` replaces existing values; set `override: false` to only fill
  missing values when the spec/transform already produced a value (default: true).

- `when` supports exact match, `in`, `regex`, and `not` conditions.

- If no match and `default` is provided in the map rule, `default` is used.

- If no match and no `default`, the original value is kept.

- Rules are evaluated top-to-bottom; the first matching rule wins.

## Map File Format

Map files map output keys to rule objects or rule lists:

```yaml
Subject.ID:
  type: mapping
  values:
    1: "test1"
    2: "test2"
  default: "unknown"
```

Guidelines:

- Top-level keys can match spec output keys or define new keys.

- Mapping rules use `values` plus optional `default`.

- Constant rules use `value`.

To validate a context map:

```python
from brkraw.specs.remapper import validate_context_map

validate_context_map("specs/maps.yaml")
```

Schema: `src/brkraw/schema/map.yaml`

Rules support:

- `sources`: resolve a value from one or more parameter sources.

- `inputs`: build a dict of named inputs, optionally transformed.

- `transform`: apply a transform (string or list of strings).

Exactly one of `sources` or `inputs` is required.
If `transform` is omitted, the resolved value (or the inputs dict) is returned as-is.

To validate the spec against the schema:

```python
from brkraw.specs.remapper import map_parameters

result = map_parameters(scan, spec, validate=True)
```

## Input Specs

When using `inputs`, each input has one of:

- `sources`: list of source selectors.

- `const`: literal value.

- `ref`: dotted path to a previously resolved output value.

You can also reference context variables using `$<name>`:

- `$scan_id` / `$reco_id` are provided by the loader context.

Optional modifiers:

- `transform`: apply transform(s) after resolving the input.

- `default`: fallback when sources are missing.

- `required`: if true, missing input raises an error.

Example:

```yaml
out.joined:
  inputs:
    a: $scan_id
    b:
      const: 3
  transform: join_fields
```

More examples:

```yaml
out.with_default:
  inputs:
    count:
      sources:

        - file: visu_pars

          key: VisuCoreFrameCount
          reco_id: 1
      default: 1
  transform: passthrough
```

```yaml
out.required_field:
  inputs:
    subject_id:
      sources:

        - file: subject

          key: SUBJECT_id
      required: true
  transform: as_string
```

```yaml
out.derived:
  inputs:
    base:
      sources:

        - file: method

          key: PVM_SPackArrNSlices
      transform: to_int
    prior:
      ref: out.joined
  transform: combine_base_and_prior
```

```python
def to_int(value):
    return int(value)

def combine_base_and_prior(base, prior):
    return f"{prior}:{base}"
```

## Sources

Each `sources` entry supports:

- `file`: one of `method`, `acqp`, `visu_pars`, `reco`, `subject`.

- `key`: parameter name inside that file.

- `reco_id`: used for `visu_pars`/`reco` to select a reco.

If multiple sources are listed, the first available value wins.

## Transforms

Transforms are functions referenced by name. When used with `inputs`:

- The first transform receives inputs as kwargs.

- If a list is provided, subsequent transforms receive the previous output.

Example:

```yaml
out.combined:
  inputs:
    a: { const: "foo" }
    b: { const: "bar" }
  transform: [join_fields, upper]
```

```python
def join_fields(a, b):
    return f"{a}_{b}"

def upper(value):
    return value.upper()
```

## Study Rules

When a Study-like object is passed as the source:

- Only `file: subject` is allowed.

- At least one `subject` source must be present.
