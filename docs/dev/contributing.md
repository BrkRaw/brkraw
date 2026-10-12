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

1) Create a virtual environment and install development dependencies.

With [uv](https://docs.astral.sh/uv/) (recommended; uses the tracked
`uv.lock` and `.python-version`):

```bash
uv sync --locked --extra dev
uv run --locked --extra dev pytest
```

Keep `--extra dev` on `uv run` too; without it uv syncs the environment back
to the runtime dependencies only and removes the development tools.

Or with pip:

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

## Tests and manual checks on real data

`tests/` is the automatic suite that CI runs on every push. It uses synthetic
data only (the PvDataset builder in `tests/helpers.py`) and never reads a real
study, so it passes the same way on every machine.

Checks that need real, approved anonymized ParaVision studies are not tests.
They are kept in `scripts/validate/` and are run by hand, for example before a
release or when you change prune, convert, context maps, scaling or study info.
CI does not run them, and a plain `pytest` does not collect them (the file name
starts with `check_`, and `pytest` collects `test_*.py`).

The approved zips (ParaVision 5.1, 6.0.1 and 360.3.x) are kept outside Git in a
folder next to your checkout, `<checkout>/../agent-fixtures`, with a README
that lists each zip, its SHA-256 and whether it is approved. Only approved zips
with a matching SHA-256 are used, and they are copied to a temporary folder;
nothing is written in the folder. To use another folder, set
`BRKRAW_AGENT_FIXTURES=/path/to/agent-fixtures`. If the folder is missing the
run stops with a message (it does not skip).

```bash
pytest -v scripts/validate/check_agent_fixtures.py
```

`check_agent_fixtures.py` holds the checks that were moved out of `tests/`:
the byte-identical default prune of the 5.1 zips, a same-name context map
converting every scan of the 5.1, 6.0.1 and 360.3.x zips, scans with one equal
slope per frame keeping raw data, context map values read from real scan info
leaving it unchanged, and the self-test of the fixture finder. Each of these
has a synthetic counterpart in `tests/`.

---

## CLI extensions

BrkRaw supports CLI extensions through an entrypoint mechanism, allowing new
subcommands to be developed and distributed independently of the core
repository.

- Entrypoint group: `brkraw.cli`
- Intended for custom workflows or project-specific helpers

See `extensions/addons-and-plugins.md` for an overview of the extension model.

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

- `extensions/rules.md`
- `extensions/specs.md`

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

brkraw has two independent layouts:

- the config layout in `config.yaml` (`output.layout_entries` with `key`,
  `entry`, `sep`, or `output.layout_template` with `{Key}` tags);
- a context map's own `__meta__.layout_template`, which uses namespace tags and
  `utils` values and is used instead of the config layout for that dataset.

See [Layout and naming](../extensions/layout.md) and
[Context maps](../extensions/context-map.md).

---

## Core development policy

Core changes are limited to maintaining compatibility with ParaVision layouts
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
