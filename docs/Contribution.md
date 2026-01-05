# Contribution Guide

This section is for developers who want to extend or customize BrkRaw without
modifying the core codebase.

## CLI extensions

BrkRaw exposes a CLI plugin entrypoint so you can add new subcommands in a
separate package.

- Entrypoint group: `brkraw.cli`
- Use this to ship custom workflows or project-specific helpers.

See `docs/Addons-and-Plugins.md` for the extension model overview.

## Rule/Spec/Transform workflow logic

Rules select which specs and converter hooks apply to a scan. Specs map Bruker
parameters into structured outputs. Transforms are Python helpers used during
spec evaluation.

Recommended reading:

- `docs/RULE-Syntax.md`
- `docs/SPEC-Syntax.md`

This pattern lets you implement conditional workflows (e.g., different metadata
schemas per sequence) without editing core code.

## Converter hooks (custom conversion)

Converter hooks override conversion helpers such as `get_dataobj`, `get_affine`,
and `convert`. They are registered via the `brkraw.converter_hook` entrypoint
and can be combined with rules, so specific sequences route through your custom
logic while BrkRaw still handles sidecars and layout naming.

This is especially useful for custom MRI sequences with bespoke reconstruction
pipelines: build a small plugin package and keep all existing BrkRaw features.

## Layout design (data structure)

The layout module builds output paths from metadata using either:

- `layout_entries` (structured entries with `key`, `entry`, and `sep`)
- `layout_template` (string template with `{Key}` tags)

You can define defaults in `config.yaml` or in `context_map.__meta__`, and
override at runtime via the API/CLI. See `docs/api/API-Layout.md`.

## Contributors

See `docs/Contributors.md` for the current list.
