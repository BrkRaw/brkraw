# Contribution Guide

Thanks for your interest in contributing to BrkRaw. This guide covers how we
extend the project and what kinds of changes belong in core vs addons/plugins.

We welcome contributions across:

- New sequence support (custom rules/specs/converter entrypoints)
- Reconstruction pipelines (FID-based or other custom paths)
- Image denoising or ML-powered workflows
- CLI plugins and tooling built on top of the BrkRaw API

Before opening an issue or PR, start with a GitHub Discussion so we can align on
scope and the right extension path.

## Dev environment (VSCode recommended)

We track `.vscode/` to share a common task setup across contributors.

1) Create a virtual environment and install dev dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

2) In VSCode, select the workspace interpreter (`.venv/bin/python`).

3) Optional: run tasks from the Command Palette:

- `Setup: venv + deps`
- `MkDocs: Serve`
- `Release: Prep (bump + notes)`

## CLI extensions

BrkRaw exposes a CLI plugin entrypoint so you can add new subcommands in a
separate package.

- Entrypoint group: `brkraw.cli`
- Use this to ship custom workflows or project-specific helpers.

See `docs/contrib/addons-and-plugins.md` for the extension model overview.

## Extension points

You can extend BrkRaw without modifying core code:

- Add rules/specs/transforms via the `addon` CLI.
- Define or update `context_map` entries to map scanner context to rules,
  specs, and transforms.
- Provide `converter_hook` overrides for specialized conversion logic.
- Ship CLI plugins through `brkraw.cli` entrypoints.

## Rule/Spec/Transform workflow logic

Rules select which specs and converter hooks apply to a scan. Specs map Bruker
parameters into structured outputs. Transforms are Python helpers used during
spec evaluation.

Recommended reading:

- `docs/contrib/rule-syntax.md`
- `docs/contrib/spec-syntax.md`

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
override at runtime via the API/CLI. See `docs/api/layout.md`.

## Core development policy

Core changes are limited to keeping BrkRaw compatible with the latest
Paravision layouts and metadata conventions. All other customization should be
implemented as addons (rules/specs/transforms/context_map) or plugins.

If you think a change must live in core, start with a GitHub Discussion and
explain why it cannot be handled through addons or plugins.

## Defaults we want help with

We are looking for suggestions on default rules/specs to ship out of the box.
If you work with specific Bruker sequences, please propose:

- `info_spec` improvements for `brkraw info` / `BrukerLoader.info`.
- `metadata_spec` mappings for sidecar metadata (BIDS or lab standards).
- Rules that select the right spec based on `method`, `acqp`, or `visu_pars`.

Even small improvements (for example, better labels or parameter keys) are
useful. Open a Discussion with your sequence details and the parameter files
you rely on.

## Packaging and distribution

We encourage authors to package addons and plugins as standalone repositories
so they can be installed independently. This makes it easier to distribute new
tools to other labs and users.

## Community

If you build something useful, please open a PR or start a discussion. We plan
to periodically highlight community plugins on the BrkRaw main site.

## Contributors

See `docs/contrib/contributors.md` for the current list.
