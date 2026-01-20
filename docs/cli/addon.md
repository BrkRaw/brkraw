# brkraw addon

The `brkraw addon` command manages BrkRaw's extensibility layer.
It is used to install, inspect, edit, and remove **specs**, **rules**,
 **pruner specs**, and **transforms** that control how metadata is
 interpreted and how conversions are performed.

This command is central to BrkRaw's design goal:
**all extensions are shared through a common, user-visible mechanism**,
 so newly installed hooks or specs work naturally with existing workflows.

---

## What is an addon in BrkRaw?

In BrkRaw, an "addon" refers to one of the following YAML- or script-based
 components installed under the config root:

- Info specs (`info_spec`)
- Metadata specs (`metadata_spec`)
- Converter hooks (`converter_hook`)
- Rules (binding specs to workflows)
- Pruner specs (dataset reduction for sharing)
- Transforms (Python helpers referenced by specs)

All addons live under the BrkRaw config directory (by default `~/.brkraw`).

---

## List installed addons

Shows all installed specs, rules, pruner specs, and transforms in
 a categorized table.

```bash
brkraw addon list
```

What this shows:

- Specs: name, version, category, description
- Rules: category and binding targets
- Pruner specs: available pruning templates
- Transforms: Python files referenced by specs

Unknown or incomplete metadata is displayed in gray to help identify
 legacy or prototype files.

---

## Install an addon

Install a spec, rule, or pruner spec from a YAML file.

```bash
brkraw addon add FILE.yaml
```

Behavior:

- The file type is auto-detected (spec, rule, or pruner spec)
- Validation is performed before installation
- Referenced transforms are automatically installed if declared
- Files are copied into the appropriate config subdirectory

This is how third-party extensions (for example, `brkraw-mrs`)
 integrate with the core CLI.

---

## Edit an installed addon

Open an installed addon in your preferred text editor.

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

Notes:

- `TARGET` can be a filename or a logical name
- The editor is resolved from:
  - `config.yaml: editor`
  - `$VISUAL`
  - `$EDITOR`

This allows tight iteration on specs and rules without leaving the CLI.

---

## Remove an addon

Remove an installed addon file.

```bash
brkraw addon rm FILE.yaml
```

Optional flags:

```bash
brkraw addon rm FILE.yaml --kind spec
brkraw addon rm FILE.yaml --force
```

Behavior:

- Dependency checks are performed by default
- If other rules or specs reference the target, a warning is shown
- Use `--force` to remove anyway

This protects users from accidentally breaking active workflows.

---

## Dependency awareness

The addon system tracks dependencies between components:

- Rules referencing specs
- Specs including other specs
- Specs referencing transform scripts

When removing addons, BrkRaw warns about downstream dependencies so users
 can make informed decisions.

---

## Typical workflows

### Install default addons

```bash
brkraw init --install-default
```

Installs bundled specs, rules, and pruner specs shipped with BrkRaw.

### Add a custom spec and tweak it

```bash
brkraw addon add my_spec.yaml
brkraw addon edit my_spec.yaml
```

### Inspect what is currently active

```bash
brkraw addon list
```

---

## Design notes

- Addons are **file-based and transparent**
- No hidden registry or binary state
- Everything is inspectable, editable, and versionable
- This design allows BrkRaw core and external projects to evolve independently

Future tools such as `brkraw-bids` will build on the same addon mechanism for
project-specific and modality-aware organization logic.
