# addon

Manage addon files installed under the BrkRaw config root (by default `~/.brkraw`).

In BrkRaw, an “addon” is a file-based extension such as:

- Specs (for example `info_spec`, `metadata_spec`, `converter_hook`)
- Rules (bind specs to selection logic)
- Pruner specs (used by `brkraw prune`)
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

List installed specs, rules, pruner specs, and transforms.

```bash
brkraw addon list
```

Notes:

- Unknown or incomplete metadata is displayed in gray.
- Specs are grouped by category.

---

## addon add

Install an addon YAML file (spec, rule, or pruner spec).

```bash
brkraw addon add FILE.yaml
```

Behavior:

- The YAML is validated (schema-level validation depends on addon type).
- The file is copied into the correct subdirectory under the config root.
- If the YAML declares transform dependencies, BrkRaw installs those transform
  files as well.

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

- `--kind {spec,pruner,rule,transform}`: limit removal to a specific kind.
- `--force`: remove even if dependency checks detect references from other files.

