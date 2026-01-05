# Addons and CLI Plugins

This document describes BrkRaw's extensibility model: rules, specs, converter
hooks, and CLI plugins.

## Concepts

BrkRaw separates *selection logic* (rules) from *parameter mapping* (specs) and

*conversion overrides* (converter_hook). This lets you compose behavior

without modifying core code.

## Extensibility overview

BrkRaw exposes extension points in layers so you can plug in just the part you
need:

- **CLI plugins** (`brkraw.cli` entrypoint): add new CLI commands and workflows.

- **Rules**: selectors that decide which specs or hooks apply to a given scan.

- **Converter hooks** (`brkraw.converter_hook` entrypoint): override
  `get_dataobj`, `get_affine`, and/or `convert` to integrate custom
  reconstruction pipelines, with full access to FID and sequence parameters.

- **Specs**: remap parameter files into structured metadata for info tables or
  sidecar JSON (e.g., BIDS-style fields).

- **Transforms**: Python snippets used by specs to derive or normalize values.

- **Context maps** (runtime `context_map`): project-specific value mapping on
  top of spec outputs (e.g., subject/session/run mapping).

- **Output layouts**: use spec/transform/context-map outputs to generate
  standardized filenames and folder structures (via `layout_entries` or
  `layout_template`).

## Terminology

- **Rule**: a selector that matches scan parameters and chooses specs/hooks.

- **Converter hook**: a plugin that overrides one or more conversion methods.

- **Spec**: a mapping recipe from Bruker parameters to structured outputs.

- **Transform**: a Python function applied during spec resolution.

- **Context map**: a project-scoped mapping table applied after spec/transform
  resolution.

- **Output layout**: formatting rules for dataset paths and filenames.

### Rules

Rules select specs or converter hooks based on Paravision parameters. You
can check fields from `method`, `acqp`, `visu_pars`, and others. When a rule
matches, BrkRaw chooses the corresponding spec or converter override.

### Specs

Specs define how parameters are mapped into structured outputs:

- `info_spec` controls what `brkraw info` shows.

- `metadata_spec` controls how `get_metadata` builds sidecar JSON (for example,

  a BIDS-like schema).

Each spec must include a `__meta__` block with required fields:

- `name`, `version`, `description`, `category`

`category` should be `info_spec` or `metadata_spec` when the spec is selected
by rules. Specs may also include optional author/developer and citation fields.

### Converter hooks

Converter hooks provide optional override callables for:

- `get_dataobj`

- `get_affine`

- `convert`

This makes it possible to swap in sequence-specific conversion logic. For
example, a rule can detect a particular sequence and route conversion through a
custom reconstruction path that reads from FID data.

## Composition model

Rules can select:

- a spec (rule + spec), or

- a converter override (rule + converter_hook), or

- both.

This enables conditional conversion:

```plain
if method/acqp/visu parameters match X

  -> use spec A

  -> use converter hook B

```

## Managing addons

Rules, specs, and transforms live in the config folder. Pruner specs are kept
under `pruner_specs/`. Use the `addon` CLI to install, list, and remove them:

- `brkraw addon add path/to/spec.yaml`

- `brkraw addon list`

- `brkraw addon rm "spec.yaml" --force`

See `src/brkraw/default/` for bundled defaults, including:

- MRS `info_spec` for controlling `brkraw info`

- `metadata_spec` for BIDS-like sidecar metadata

- Pruner specs for de-identification workflows

See `docs/api/addon.md` for the addon API reference.

Rules can reference specs by name (recommended) or by path. When a name is
used, the rule category must match `__meta__.category`, and `version` can be
specified to pin the selection; otherwise the latest version is used.

## Converter hook roadmap

We plan to add a converter hook for UNC's SORDINO sequence to
support the custom reconstruction pipeline.

## CLI plugins

BrkRaw supports CLI extensions via entrypoints, so new commands can be shipped
without touching the core repository. Planned plugins include:

- BIDS tooling (legacy tools from earlier versions)

- Backup/export utilities

- GUI tools

These will be distributed as external plugins and registered via the
`brkraw.cli` entrypoint group.
