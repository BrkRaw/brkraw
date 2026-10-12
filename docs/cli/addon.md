# addon

Manage addon files installed under the BrkRaw config root (by default `~/.brkraw`).

In BrkRaw, an “addon” is a file-based extension such as:

- Specs (for example `info_spec`, `metadata_spec`, `converter_hook`)
- Rules (bind specs to selection logic)
- Pruner specs (used by `brkraw prune`)
- Shared context maps (bases that a dataset's context map includes by name)
- Transform scripts (Python functions referenced by specs)

Hook packages can also ship addon assets, but the hook **package** is managed
via `brkraw hook`. The addon command manages the underlying files once they
exist in the config root.

---

## Common options

### --root

Override config root directory (default: `BRKRAW_CONFIG_HOME` or `~/.brkraw`).

```bash
brkraw addon --root /path/to/config list
```

---

## addon list

List installed specs, rules, pruner specs, context maps and transforms.

```bash
brkraw addon list
```

Notes:

- Unknown or incomplete metadata is displayed in gray.
- Specs are grouped by category.

---

## addon add

Install an addon YAML file (spec, rule, pruner spec or shared context map).

```bash
brkraw addon add FILE.yaml
```

Behavior:

- The YAML is validated (schema-level validation depends on addon type).
- The file is copied into the correct subdirectory under the config root.
- If the YAML declares transform dependencies, BrkRaw installs those transform
  files as well.
- A context map (`__meta__.category: context_map`) is installed into the
  config folder's `context_maps/` and needs `__meta__.name` and `version`, so
  that other maps can include it by name. A dataset's own map is not
  installed: keep it next to the dataset. See
  [Context maps](../extensions/context-map.md#sharing-a-base-map-include).

---

## addon edit

Open an installed addon in your preferred editor.

```bash
brkraw addon edit TARGET
```

Optional hints:

```bash
brkraw addon edit TARGET --kind spec
brkraw addon edit TARGET --kind rule
brkraw addon edit TARGET --kind pruner
brkraw addon edit TARGET --kind context_map
brkraw addon edit TARGET --kind transform
```

If `TARGET` is ambiguous (for example multiple specs share a name), you can
provide a category hint:

```bash
brkraw addon edit TARGET --kind spec --category info_spec
```

Editor resolution order:

- `config.yaml: editor`
- `$VISUAL`
- `$EDITOR`

---

## addon rm

Remove an installed addon file by filename.

```bash
brkraw addon rm FILE.yaml
```

Options:

- `--kind {spec,pruner,context_map,rule,transform}`: limit removal to a specific kind.
- `--force`: remove even if dependency checks detect references from other files.

