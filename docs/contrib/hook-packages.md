# Converter Hook Packages

This document describes how to structure a converter hook package so it works
with `brkraw hook install`.


## Required entrypoint

Expose your converter hook via the `brkraw.converter_hook` entrypoint group:

```toml
[project.entry-points."brkraw.converter_hook"]
sordino = "brkraw_sordino.hook:get_hook"
```

The hook object must match the converter hook schema (see
`brkraw.specs.converter.validator`).


## Hook manifest

Ship a `brkraw_hook.yaml` (or `brkraw_hook.yml`) file in your package and make
sure it is included as package data. The manifest lists addon assets that
`brkraw hook install` should copy into the user's config directories.

Example `brkraw_hook.yaml`:

```yaml
docs: README.md
specs:
  - specs/info.yaml
  - specs/metadata.yaml
rules:
  - rules/sordino.yaml
transforms:
  - transforms/sordino_transforms.py
pruner_specs:
  - pruner_specs/deid.yaml
```

Rules:

- Paths are resolved relative to the manifest file location.
- `specs` and `rules` must be YAML files.
- `transforms` are copied as-is into the user's `transforms/<hook_name>/` directory.
- `pruner_specs` are installed into the user's `pruner_specs/<hook_name>/` directory.
- Spec installs still honor `__meta__.transforms_source`; referenced transforms
  are installed and the spec is rewritten to point at the installed copies.
- Assets are installed under a namespace named after the hook package to avoid
  filename collisions.
- Rules can reference specs by name or by filename; when filenames match manifest
  specs, the installer rewrites them to the namespaced path.
- `docs` (or `readme`) should point at a packaged markdown/text file for
  `brkraw hook docs`.


## Package metadata

`brkraw hook list` displays package metadata from the installed distribution:

- name
- version
- author (or author email / maintainer as available)
- description (summary)

Fill these fields in your `pyproject.toml` so the CLI can show them in the
hook list table.


## Recommended layout

```text
brkraw-sordino/
  pyproject.toml
  src/
    brkraw_sordino/
      __init__.py
      hook.py
      brkraw_hook.yaml
      specs/
        info.yaml
        metadata.yaml
      rules/
        sordino.yaml
      transforms/
        sordino_transforms.py
```

Ensure `brkraw_hook.yaml` is included in your package data so it is available
after installation. Include the docs file in package data as well.
