# Extensibility Model

BrkRaw is designed to be modular and extensible. The core stays small and
stable, while project-specific logic lives in addons and plugins.

BrkRaw separates concerns into three layers:

- selection logic (rules)
- parameter mapping (specs + transforms)
- conversion overrides (converter hooks)

This lets you compose behavior without modifying core code.

---

## Extension points

BrkRaw exposes extension points in layers so you can plug in only what you need:

- CLI plugins (`brkraw.cli` entry point group)
    - Add new CLI commands and workflows as separate Python packages.

- Rules
    - Select specs and converter hooks based on Paravision parameters.

- Converter hooks (`brkraw.converter_hook` entry point group)
    - Override conversion behavior (data loading, affine, conversion) for
    sequence-specific pipelines.

- Specs
    - Map Paravision parameter files into structured outputs for inspection
    and metadata generation.

- Transforms
    - Python helpers used by specs to derive or normalize values.

- Context maps (runtime `context_map`)
    - Project-scoped remapping on top of spec outputs (for example subject/session/run
    mapping and scan selection).

- Output layouts
    - Render output paths and filenames using spec and context-map outputs.

---

## Terminology

- Rule
    - A selector that matches scan parameters and chooses specs and/or hooks.

- Spec
    - A mapping recipe from Bruker parameters to structured outputs.

- Transform
    - A Python function applied during spec evaluation.

- Converter hook
    - A plugin that overrides one or more conversion methods.

- Context map
    - A runtime mapping table applied after spec and transform resolution.

- Output layout
    - Formatting rules for output paths and filenames.

---

## Composition model

Rules can select:

- a spec (rule + spec)
- a converter override (rule + converter hook)
- both

This enables conditional behavior:

```text
if method/acqp/visu parameters match X
  -> use spec A
  -> use converter hook B
```

Typical usage patterns:

- Specs only
    - Use rules to select different metadata schemas per sequence.

- Converter hooks only
    - Route conversion through a specialized reconstruction pipeline for a
    specific sequence.

- Specs + converter hooks
    - Use a custom conversion pipeline while still generating consistent metadata
    and output naming.

---

## Addons vs hook packages vs CLI plugins

BrkRaw uses three distribution mechanisms. They are related but distinct.

### Addons (files installed into a config root)

Addons are YAML and Python files installed into the user's brkraw config root:

- specs (YAML)
- rules (YAML)
- pruner specs (YAML)
- transforms (Python)

Addons are managed by:

- CLI: `brkraw addon`
- API: `brkraw.apps.addon`

Addons are the preferred way to customize mapping behavior without shipping
a Python package.

### Hook packages (Python packages for conversion hooks)

Hook packages are Python distributions that:

- expose converter hooks via the `brkraw.converter_hook` entry point group
- optionally ship a manifest to install namespaced addon assets

Hook packages are managed by:

- CLI: `brkraw hook`
- API: `brkraw.apps.hook`

Hook packages are the preferred way to distribute sequence-specific conversion
pipelines.

### CLI plugins (Python packages for new commands)

CLI plugins are Python distributions that:

- expose new CLI commands via the `brkraw.cli` entry point group

They are used to add new workflows without changing the core CLI.

In practice, hook packages and CLI plugins are BrkRaw's *plugin* system (they
ship code and register entry points), while addons are configuration assets
that customize behavior in a case-dependent way.

---

## What goes into core vs extensions

As a rule of thumb:

- Core stays focused on Paravision compatibility and stable infrastructure.
- Project-specific behavior should live in addons and plugins.

For contributor-facing guidance (how to decide and when to propose core
changes), see `docs/dev/core-vs-addon.md`.

---

## Related documents

- [Addons and plugins](addons-and-plugins.md)
- [Rule syntax](rules.md)
- [Spec syntax](specs.md)
- [Context map syntax](context-map.md)
- [Output layout and naming](layout.md)
- [Contribution guide](../dev/contributing.md)
