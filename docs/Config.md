# Config Reference

BrkRaw stores user configuration under the config root. By default this is
`~/.brkraw`, or you can override it with `BRKRAW_CONFIG_HOME`.

The main file is `config.yaml`. It is created by `brkraw init` unless you pass
`--no-config`.

## File layout

```bash
~/.brkraw/
  config.yaml
  rules/
  specs/
  pruner_specs/
  transforms/
  maps/
```

## `config.yaml` keys

The default file is created from the template below (values may be omitted in
your local file).

```yaml
config_version: 0
editor: null
logging:
  level: INFO
  print_width: 120
output:
  format_fields:

    - key: Subject.ID

      entry: sub
      hide: false

    - key: Study.ID

      entry: study
      hide: false

    - key: ScanID

      entry: scan
      hide: false

    - key: Protocol

      hide: true
  format_spec: null
  float_decimals: 6
rules_dir: rules
specs_dir: specs
pruner_specs_dir: pruner_specs
transforms_dir: transforms
maps_dir: maps
```

`config_version` is managed by BrkRaw and should not be edited manually.

### `editor`

Optional editor command used by `brkraw config edit` and `brkraw addon edit`.
When unset, BrkRaw falls back to `$VISUAL` or `$EDITOR`.

### `logging.level`

Logging level for CLI output. Common values: `INFO`, `DEBUG`, `WARNING`.

### `logging.print_width`

Column width used by CLI tables (for example `brkraw info`).

### `output.float_decimals`

Default rounding for floating-point values shown in info tables and derived
outputs (including affine formatting).

### `output.slicepack_suffix`

Suffix template used when a scan produces multiple slice packs. Use `{index}`
for the 1-based slice pack number. You can also reference fields resolved by
the output format spec (e.g., `{SliceOrient}`), which allows per-slicepack labels
when the value is an array. Default: `_slpack{index}`.

Notes:

- The default output format spec is `src/brkraw/apps/loader/info/study.yaml`.

- `{SliceOrient}` resolves from `PVM_SPackArrSliceOrient`, which maps to

  `axial`, `sagittal`, or `coronal`.

- If the referenced value is missing or out of range, BrkRaw falls back to the

  1-based index (e.g., `_1`, `_2`, `_3`).

- To force numeric suffixes, keep the default or use `_slicepack{index}`.

### `output.format_fields`

Filename parts used by `brkraw tonii` when an explicit output name is not
provided. Each entry is appended in order if a value is present.

Fields:

- `key`: dotted key resolved from the output format spec (for example `Subject.ID`).

- `entry`: prefix label used to emit `entry-value` (optional when `hide` is true).

- `hide`: when true, only the value is appended (no prefix).

- `use_entry`: reuse a previously defined `entry` value (omit `key` when using this).

- `sep`: separator to insert after this field (default `_`, use `/` for folders).

- `value_pattern`: regex that defines allowed characters (default `[A-Za-z0-9._-]`).

- `value_replace`: replacement for disallowed characters (default `""`).

- `max_length`: truncate values longer than this length.

Values are resolved via the output format spec (see below) and sanitized to
`A-Z`, `a-z`, `0-9`, `.`, `_`, `-`. Missing values are skipped.
Parts are joined with `_` in the order listed.
If any `sep` values are provided, they control how the next field is joined.

Entry names must match `^[A-Za-z][A-Za-z0-9_-]*$`. Values are skipped if the
sanitized result is empty.

Example with reuse + normalization:

```yaml
output:
  format_fields:

    - key: Subject.ID

      entry: sub
      sep: "/"
      value_pattern: "[A-Za-z0-9]"
      max_length: 8

    - key: Session.ID

      entry: ses
      sep: "/"

    - use_entry: sub

    - use_entry: ses

    - key: Protocol

      hide: true
```

### `output.format_spec`

Optional info spec reference (name or path) used to generate values for
`output.format_fields`. When omitted, BrkRaw uses the built-in study/scan info
specs.

### `rules_dir`, `specs_dir`, `pruner_specs_dir`, `transforms_dir`, `maps_dir`

Relative paths under the config root where rule/spec/transform/context map files are
installed. Most users should keep the defaults.

## Managing config from CLI

Use `brkraw config` to inspect or clear the config directory. See
`docs/cli/CLI-config.md` for details.
