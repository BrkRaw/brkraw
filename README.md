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

See `docs/getting-started.md` for setup and first-run steps.

## Overview

Core capabilities:

- Load Paravision datasets from directories or zip archives.

- Inspect study/scan metadata with rich CLI tables.

- Map parameters via remapper specs and rule-based selection.

- Convert scans to NIfTI with configurable layout entries/templates.

- Manage installed specs, rules, and transforms.

## Extensibility

BrkRaw is designed for extension without modifying the core repository:

- Rules select specs or converter overrides based on Paravision parameters.

- Specs map parameter files into structured metadata.

- Converter hooks override data/affine/NIfTI generation for specialized

  sequences.

- CLI plugins can add commands via entrypoints.

See `docs/addons-and-plugins.md` for a full overview and examples in
`assets/examples/`.

## CLI documentation

- `docs/getting-started.md`: install and first-run steps

- `docs/cli/info-and-params.md`: `brkraw info` and `brkraw params`

- `docs/cli/session.md`: `brkraw session` helpers

- `docs/cli/convert.md`: `brkraw convert` and `brkraw convert-batch`

- `docs/cli/addon.md`: addon management

- `docs/cli/config.md`: config management

- `docs/configuration.md`: `config.yaml` reference

- `docs/addons-and-plugins.md`: rules, specs, converters, and CLI plugins

- `docs/python-api.md`: Python API usage examples

- `docs/api/cli-workflows.md`: CLI-equivalent API workflows

- `docs/contribution.md`: developer extension guide

- `docs/contributors.md`: contributor list

## API documentation

- `docs/api/addon.md`: addon API

- `docs/api/layout.md`: layout API

- `docs/api/pruner.md`: pruner API

## Rules and specs

- `docs/rule-syntax.md` describes the rule syntax for selecting specs and plugins.

- `docs/spec-syntax.md` describes the spec format and remapper behavior.

## Contributing

We welcome new sequence support, reconstruction pipelines, denoising/ML
applications, and CLI plugins. See `CONTRIBUTING.md` for details.
