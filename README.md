# BrkRaw: A Comprehensive and Extensible Converter for Bruker Paravision Datasets

BrkRaw is a toolkit for loading Bruker Paravision studies, inspecting metadata,
mapping parameters with rules/specs, and exporting NIfTI with optional sidecar
metadata.

## Release status

BrkRaw is in alpha (v0.5.0a). The codebase was rebuilt from scratch with a focus
on modernizing the architecture, minimizing external dependencies, and keeping
pace with newer Python versions. Legacy features like the GUI and BIDS helper
tools are not shipped in the main repository; these extras will return as
independently installable CLI plugins. The core CLI and Python API are
available now.

## Installation

Install from GitHub:

```bash
pip install git+https://github.com/BrkRaw/brkraw.git
```

For development:

```bash
pip install -e .
```

See `docs/Getting-Started.md` for setup and first-run steps.

## Overview

Core capabilities:

- Load Paravision datasets from directories or zip archives.

- Inspect study/scan metadata with rich CLI tables.

- Map parameters via remapper specs and rule-based selection.

- Convert scans to NIfTI with configurable filename templates.

- Manage installed specs, rules, and transforms.

## Extensibility

BrkRaw is designed for extension without modifying the core repository:

- Rules select specs or converter overrides based on Paravision parameters.

- Specs map parameter files into structured metadata.

- Converter hooks override data/affine/NIfTI generation for specialized

  sequences.

- CLI plugins can add commands via entrypoints.

See `docs/Addons-and-Plugins.md` for a full overview and examples in
`assets/examples/`.

## CLI documentation

- `docs/Getting-Started.md`: install and first-run steps

- `docs/cli/CLI-info_and_params.md`: `brkraw info` and `brkraw params`

- `docs/cli/CLI-set_unset_and_env.md`: `brkraw session` helpers

- `docs/cli/CLI-convert.md`: `brkraw convert` and `brkraw convert-batch`

- `docs/cli/CLI-addon.md`: addon management

- `docs/cli/CLI-config.md`: config management

- `docs/Config.md`: `config.yaml` reference

- `docs/Addons-and-Plugins.md`: rules, specs, converters, and CLI plugins

- `docs/Python-API.md`: Python API usage examples

- `docs/api/API-Workflows.md`: CLI-equivalent API workflows

- `docs/Contribution.md`: developer extension guide

## API documentation

- `docs/api/API-Addon.md`: addon API

- `docs/api/API-Layout.md`: layout API

- `docs/api/API-Pruner.md`: pruner API

## Rules and specs

- `docs/RULE-Syntax.md` describes the rule syntax for selecting specs and plugins.

- `docs/SPEC-Syntax.md` describes the spec format and remapper behavior.

## Contributing

We welcome new sequence support, reconstruction pipelines, denoising/ML
applications, and CLI plugins. See `CONTRIBUTING.md` for details.
