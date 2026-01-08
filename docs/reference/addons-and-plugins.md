# Addons and Plugins

This document describes how BrkRaw can be extended without modifying core code.
It focuses on *what* can be extended and *how the pieces fit together*, not on
specific CLI or API calls.

For command-level usage, see the corresponding CLI and API reference pages.

---

## Overview

BrkRaw is designed around a thin, stable core and a rich extension model.
Most customization should be implemented as addons or plugins.

There are three main extension mechanisms:

- addons (data files installed into a config root)
- converter hook packages (Python packages for custom conversion)
- CLI plugins (Python packages adding new CLI commands)

Each mechanism serves a different purpose and scope.

---

## Addons

Addons are files installed into the user's BrkRaw configuration root.
They are loaded dynamically at runtime and do not require Python packaging.

Use addons for case-dependent customization of BrkRaw behavior (for example,
choosing different mappings or conversion overrides depending on scan
parameters), without adding new features to the core.

Addon types include:

- specs
- rules
- pruner specs
- transforms

Addons are managed via the `addon` CLI and API.

### Specs

Specs map Bruker Paravision parameter files into structured outputs.

There are two main spec categories:

- `info_spec`
    - controls what is shown by inspection tools such as `brkraw info`
- `metadata_spec`
    - controls metadata generation for sidecar JSON files

Specs are YAML files and must include a `__meta__` block describing their
name, version, category, and other metadata.

Specs may reference Python transforms and may include other specs.

### Rules

Rules select which specs or converter hooks apply to a scan.

Rules are evaluated against Paravision parameters and can:

- choose an `info_spec`
- choose a `metadata_spec`
- choose a `converter_hook`

Rules are YAML files evaluated in filename order. When multiple rules match
the same category, the last matching rule wins.

### Transforms

Transforms are Python functions used by specs to derive or normalize values.

Transforms are referenced by name inside specs and are resolved via
`__meta__.transforms_source`.

They are installed as plain Python files and are not required to be part of
a Python package.

### Pruner specs

Pruner specs define how datasets are filtered and rewritten when creating
a pruned dataset zip.

They control:

- file keep or drop logic
- directory-level filtering
- JCAMP parameter edits
- comment stripping
- output zip structure

Pruner specs are YAML files and are stored separately from specs and rules.

---

## Converter hook packages

Converter hook packages are Python distributions that provide custom conversion
logic.

A converter hook package:

- exposes one or more hooks via the `brkraw.converter_hook` entry point group
- optionally ships addon assets via a hook manifest

Converter hooks can override one or more of:

- data loading
- affine computation
- conversion logic

This is intended for custom or nonstandard reconstruction pipelines, such as
FID-based reconstruction or sequence-specific workflows.

Hook packages may also install namespaced addons (specs, rules, transforms,
pruner specs) using a manifest file.

For implementation details and a maintained template, see
[brkraw-hook](https://github.com/brkraw/brkraw-hook).

---

## CLI plugins

CLI plugins are Python packages that add new subcommands to the `brkraw` CLI.

They are registered via the `brkraw.cli` entry point group and allow new
workflows to be distributed independently of the core project.

CLI plugins are appropriate for:

- project-specific workflows
- batch or automation tools
- GUI frontends
- legacy tools layered on top of the BrkRaw API

CLI plugins should treat BrkRaw as a library and avoid modifying internal state
directly.

---

## Naming and reference rules

Addons and plugins follow these principles:

- addons are referenced by logical name whenever possible
- version pinning is optional but supported
- latest version is selected by default when resolving names
- namespaces are used to avoid filename collisions

Rules that reference specs by name must match the spec `__meta__.category`.
When a version is not specified, the latest available version is used.

---

## Defaults and bundled addons

BrkRaw ships with a small set of default addons, including:

- basic `info_spec` definitions
- example `metadata_spec` mappings
- pruner specs for common de-identification workflows

These defaults are intended as examples and starting points, not as
comprehensive solutions.

---

## Related documents

- [Extensibility model](extensibility.md)
- [Rule syntax reference](rules.md)
- [Spec syntax reference](specs.md)
- [Context map syntax](context-map.md)
- [Addon API reference](../api/addon.md)
- [Hook API reference](../api/hook.md)
