# Building converter hook packages

Converter hook packages are Python distributions that provide custom conversion
logic and (optionally) ship addon assets for case-dependent behavior.

This page covers authoring and packaging. For user-facing behavior and
terminology, see `docs/reference/extensibility.md` and
`docs/reference/addons-and-plugins.md`.

---

## Required entrypoint

Expose your converter hook via the `brkraw.converter_hook` entrypoint group in
`pyproject.toml`:

```toml
[project.entry-points."brkraw.converter_hook"]
mrs = "brkraw_mrs.hook:get_hook"
```

The returned hook object must conform to the converter hook schema defined in
`brkraw.specs.converter.validator`.

---

## Hook manifest

Each hook package must ship a `brkraw_hook.yaml` (or `brkraw_hook.yml`) file.
This manifest lists addon assets that `brkraw hook install` will copy into the
user's BrkRaw config directories.

Example `brkraw_hook.yaml`:

```yaml
docs: README.md
specs:
  - specs/info.yaml
  - specs/metadata.yaml
rules:
  - rules/mrs.yaml
transforms:
  - transforms/mrs_transforms.py
pruner_specs:
  - pruner_specs/deid.yaml
```

### Manifest rules

- Paths are resolved relative to the manifest file location.
- `specs` and `rules` must be YAML files.
- `transforms` are copied into `transforms/<hook_name>/`.
- `pruner_specs` are installed into `pruner_specs/<hook_name>/`.
- Spec installs still honor `__meta__.transforms_source`.
  Referenced transforms are installed automatically and specs are rewritten to
  point to the installed copies.
- All assets are installed under a namespace derived from the hook package name
  to avoid filename collisions.
- Rules may reference specs by name or filename; when filenames match manifest
  specs, the installer rewrites them to the namespaced paths.
- `docs` (or `readme`) should point to a packaged markdown/text file used by
  `brkraw hook docs`.

---

## Package metadata

`brkraw hook list` displays metadata from the installed Python distribution:

- name
- version
- author (or author email / maintainer)
- description (summary)

Populate these fields in `pyproject.toml` so they are visible in the CLI hook
listing.

---

## Recommended layout

```text
brkraw-mrs/
  pyproject.toml
  src/
    brkraw_mrs/
      __init__.py
      hook.py
      brkraw_hook.yaml
      specs/
        info.yaml
        metadata.yaml
      rules/
        mrs.yaml
      transforms/
        mrs_transforms.py
```

Ensure `brkraw_hook.yaml` and any documentation files are included as package
data so they are available after installation.

---

## Reference implementations

- Hook template repository: https://github.com/brkraw/brkraw-hook.git

