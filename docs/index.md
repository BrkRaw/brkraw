# Preclinical MRI dataset toolkit

BrkRaw is a toolkit for loading Bruker Paravision studies, inspecting metadata,
mapping parameters with rules/specs, and exporting NIfTI with optional sidecar
metadata. It ships with a CLI and a Python API, and is designed to be extended
through add-on rules, specs, and plugins.

## Highlights

- Load Paravision datasets from directories or zip archives.
- Inspect study and scan metadata with rich CLI tables.
- Map parameters via remapper specs and rule-based selection.
- Convert scans to NIfTI with configurable filename templates.
- Extend behavior via rules, specs, and converter hooks.

## Quick links

- Getting started: Getting-Started.md
- CLI usage: cli/CLI-info_and_params.md
- Python API: Python-API.md
- Rules and specs: RULE-Syntax.md and SPEC-Syntax.md
- Addons and plugins: Addons-and-Plugins.md
