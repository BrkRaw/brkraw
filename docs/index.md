# Preclinical MRI dataset toolkit

BrkRaw is a toolkit for loading Bruker Paravision studies, inspecting metadata,
mapping parameters with rules/specs, and exporting NIfTI with optional sidecar
metadata. It ships with a CLI and a Python API, and is designed to be extended
through add-on rules, specs, and plugins.

## Highlights

- Load Paravision datasets from directories or zip archives.
- Inspect study and scan metadata with rich CLI tables.
- Map parameters via remapper specs and rule-based selection.
- Convert scans to NIfTI with configurable layout entries/templates.
- Extend behavior via rules, specs, and converter hooks.

## Quick links

- Getting started: getting-started.md
- CLI usage: cli/info-and-params.md
- Python API: python-api.md
- API workflows: api/cli-workflows.md
- Rules and specs: rule-syntax.md and spec-syntax.md
- Addons and plugins: addons-and-plugins.md
- Contribution: contribution.md
