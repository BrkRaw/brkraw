# Layout and naming

The layout decides where converted files go and what they are called. brkraw
has **two independent layouts**:

| | Config layout | Context map layout |
| --- | --- | --- |
| Where | `output:` in `config.yaml` (your config folder) | `__meta__.layout_template` in a context map next to the dataset |
| Applies to | every dataset converted with that config | the dataset of that context map |
| Tags | original information: `{Subject.ID}`, `{Study.ID}`, `{Protocol}`, `{ScanID}`, `{RecoID}`, `{Counter}` …, and context map namespaces (`{bids.sub}`) | context map namespaces (`{bids.sub}`) and `utils` values (`{utils.counter}`, `{utils.slicepack}`, `{utils.split}`) |
| Optional parts | empty values are skipped (`layout_entries`) | `[ ... ]` groups disappear when a tag is empty |
| Same name twice | `_2`, `_3` … (or the next `{Counter}`) | error, nothing written (or `on_collision: suffix`) |
| Slice packs | `slicepack_suffix` appended | only through `{utils.slicepack}` in the template |

When a context map has a `layout_template`, it names the files for that run
and the config layout is not used. Otherwise (no context map, or a context map
without `layout_template`) the config layout is used. `--prefix` always uses
the config layout's tags. The two syntaxes are not mixed: config tags do not
work in a context map template and `utils` tags do not work in the config.

This page describes the config layout. The context map layout is described in
[Context maps](context-map.md#output-paths-layout_template).

!!! note "Changed in 0.6.0"
    A context map can no longer set `layout_entries` or `slicepack_suffix`;
    it has its own `layout_template` with `utils` values. The config layout
    is unchanged. See [Migrating to 0.6](../getting-started/migrating.md).

## Where the config layout lives

```yaml
# config.yaml (brkraw config path config)
output:
  layout_entries:
    - {key: Subject.ID, entry: sub}
    - {key: Study.ID, entry: study}
    - {key: ScanID, entry: scan}
    - {key: Protocol, hide: true}
  layout_template: null
  slicepack_suffix: "_slpack{index}"
```

These are the defaults: a scan is written as
`sub-<Subject.ID>_study-<Study.ID>_scan-<ScanID>_<Protocol>.nii.gz`. Change
values with `brkraw config set` or `brkraw config edit`
(see [config](../cli/config.md)).

## `layout_entries`

A list of parts, joined in order:

| Field | Meaning |
| --- | --- |
| `key` | information key; dotted keys (`Subject.ID`) and context map namespaces (`bids.run`) work |
| `entry` | label written before the value (`sub` gives `sub-01`); derived from `key` when left out and `hide` is false |
| `hide` | `true` writes only the value, without the label |
| `sep` | separator before the next part (default `_`); `/` makes a folder |
| `use_entry` | reuse the value of an earlier `entry` |

A part whose value is empty is skipped.

```yaml
output:
  layout_entries:
    - {key: Study.ID, entry: study, sep: "/"}
    - {key: Subject.ID, entry: sub, sep: "/"}
    - {key: ScanID, entry: scan}
    - {key: Protocol, hide: true}
```

gives `study-001/sub-003/scan-5_EPI_rest` (folders from `sep: "/"`).

## `layout_template`

A full path as one text with `{Key}` tags. When set, it replaces
`layout_entries`.

```yaml
output:
  layout_template: "{Subject.ID}/{Study.ID}/scan-{ScanID}_{Protocol}"
```

Missing keys become empty text.

## Fixed keys

Always available in `layout_entries` (`key: ScanID`) and `layout_template`:

- `{ScanID}` (also `{scan_id}`, `{scanid}`): the scan ID
- `{RecoID}` (also `{reco_id}`, `{recoid}`): the reco ID (may be empty)
- `{Counter}` (also `{counter}`): 1, 2, 3 … the first number whose name is free

## Slice packs

A scan with several slice packs gets one file per pack, named with
`slicepack_suffix` (`{index}` from 1):

```yaml
output:
  slicepack_suffix: "_slpack{index}"
```

## Reading context map values

With a context map that has no `layout_template`, the config layout can use
its namespaces:

```yaml
output:
  layout_template: "sub-{bids.sub}/scan-{ScanID}"
```

## Names on disk

- Invalid characters in names are replaced; folders from `/` are created.
- Repeated names get `_2`, `_3` … unless `{Counter}` is used.

## Related documents

- [Context maps](context-map.md)
- [convert](../cli/convert.md)
- [config](../cli/config.md)
- [Layout (Python API)](../api/layout.md)
