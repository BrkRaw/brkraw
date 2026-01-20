# Contribution Guide

Thank you for your interest in contributing to BrkRaw. This guide explains how
the project is extended, and clarifies which kinds of changes belong in core
versus addons or plugins.

We welcome contributions across a wide range of areas, including:

- New sequence support (rules, specs, and converter hooks)
- Custom reconstruction pipelines (FID-based or other specialized paths)
- Image denoising or ML-powered workflows
- CLI plugins and tooling built on top of the BrkRaw API

Before opening an issue or pull request, please start with a GitHub Discussion
so we can align on scope and choose the appropriate extension path. For core
changes, we follow a clear progression:

Discussion proposal → Issue(s) → Pull request

---

## Development environment (VSCode recommended)

We track a shared `.vscode/` directory to provide consistent tasks and settings
across contributors.

1) Create a virtual environment and install development dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

2. In VSCode, select the workspace interpreter (`.venv/bin/python`).

3. Optional: run predefined tasks from the Command Palette:

- `Standard: Setup venv + deps`
- `Standard: MkDocs Serve`
- `Standard: Release Prep PR (2-step)`

---

## CLI extensions

BrkRaw supports CLI extensions through an entrypoint mechanism, allowing new
subcommands to be developed and distributed independently of the core
repository.

- Entrypoint group: `brkraw.cli`
- Intended for custom workflows or project-specific helpers

See `reference/addons-and-plugins.md` for an overview of the extension model.

---

## Extension points

Most customization can be implemented without modifying core code:

- Install rules, specs, and transforms using the `addon` CLI
- Define or update runtime `context_map` entries to map scanner context to
  specs, rules, and transforms
- Provide `converter_hook` overrides for specialized conversion logic
- Ship standalone CLI plugins via the `brkraw.cli` entrypoint

---

## Rule, spec, and transform workflow

Rules determine which specs and converter hooks apply to a given scan. Specs map
Bruker parameter files into structured outputs. Transforms are Python helpers
used during spec evaluation.

This composition model enables conditional workflows, such as applying
different metadata schemas per sequence, without editing core code.

Recommended references:

- `reference/rules.md`
- `reference/specs.md`

---

## Converter hooks (custom conversion)

Converter hooks override conversion helpers such as `get_dataobj`,
`get_affine`, and `convert`. They are registered via the
`brkraw.converter_hook` entrypoint and may be selected conditionally by rules.

This design allows sequence-specific reconstruction pipelines while preserving
BrkRaw's standard handling of metadata, sidecars, and output layouts.

Converter hooks are especially useful for custom MRI sequences with bespoke
reconstruction requirements. In most cases, they should be packaged as small,
independent plugins.

---

## Layout design and data structure

The layout system constructs output paths and filenames from metadata using one
of the following mechanisms:

- `layout_entries`: structured entries with `key`, `entry`, and `sep`
- `layout_template`: string templates with `{Key}` placeholders

Defaults may be defined in `config.yaml` or in `context_map.__meta__`, and can be
overridden at runtime via the API or CLI.

See `reference/layout.md` for details.

---

## Core development policy

Core changes are limited to maintaining compatibility with Paravision layouts
and metadata conventions. All other customization should be implemented as
addons (rules, specs, transforms, context maps) or external plugins.

If you believe a change must live in core, start with a GitHub Discussion and
explain why the behavior cannot be implemented through existing extension
mechanisms. Once agreed, open issue(s) for the scoped work and combine them into
a single pull request.

---

## Defaults we welcome contributions for

We actively welcome proposals for default rules and specs to ship with BrkRaw,
particularly for modality-specific workflows. If you work with specific Bruker
sequences, consider contributing:

- Improved `info_spec` mappings for `brkraw info` or `BrukerLoader.info`
- `metadata_spec` mappings aligned with BIDS or lab standards
- Rules that select specs based on `method`, `acqp`, or `visu_pars`
- Reusable `context_map` patterns for common lab workflows

Documentation contributions are also valuable, including:

- End-to-end use cases combining rules, specs, and context maps
- Modality-specific tutorials (for example DWI, fMRI, or MRS)
- Corrections or clarifications to existing documentation

Even small improvements, such as clearer parameter labels, are useful. Please
open a Discussion with sequence details and the parameter files you rely on.

---

## Packaging and distribution

We encourage authors to package addons and plugins as standalone repositories so
they can be installed and versioned independently. This simplifies sharing
tools across labs and projects.

---

## Release and publishing (GitHub Actions)

BrkRaw uses a 2-step PR-based release flow:

1. Run `Standard: Release Prep PR (2-step)` to create a release prep PR (version bump,
   contributors refresh, and release notes).
2. Review the PR, ensure CI passes, and apply the `release` label.
3. Merge the PR to `main`.
4. `Release On Merge` tags the merge commit.
5. `Create Release` runs for the tag and creates a GitHub Release.
6. When the Release is published, `Publish Package` runs automatically.

Notes:

- Pre-release versions (`a`, `b`, `rc`) create GitHub pre-releases and skip PyPI
  publishing.
- The publish workflow validates that the tag matches the package version.

---

## Community

If you build something useful, please start a GitHub Discussion. We plan to
periodically highlight community addons and plugins on the BrkRaw site.

---

## Contributors

See `docs/dev/contributors.md` for the current list of contributors.
