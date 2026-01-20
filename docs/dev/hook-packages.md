# Building converter hook packages

Converter hook packages are Python distributions that provide custom conversion
logic and (optionally) ship addon assets for case-dependent behavior.

This page covers authoring and packaging. For user-facing behavior and
terminology, see [Extensibility model](../reference/extensibility.md) and
[Addons and plugins](../reference/addons-and-plugins.md).

---

## Required entrypoint

Expose your converter hook via the `brkraw.converter_hook` entrypoint group in
`pyproject.toml`:

```toml
[project.entry-points."brkraw.converter_hook"]
mrs = "brkraw_mrs.hook:get_hook"
```

The returned hook object must conform to the converter hook schema defined in
`brkraw.specs.hook.validator`.

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

## Hook arguments (kwargs) and presets

BrkRaw supports passing hook arguments at runtime via:

- CLI: `brkraw convert --hook-arg HOOK:KEY=VALUE`
- CLI: `brkraw convert --hook-args-yaml hook_args.yaml`
- CLI template generation: `brkraw hook preset <hook-entrypoint>`

### How BrkRaw passes hook args

BrkRaw collects all hook args into a mapping:

```yaml
hooks:
  <hook-entrypoint>:
    key: value
```

At conversion time, BrkRaw looks up args by the selected hook entrypoint name
(for example `sordino`, `mrs`) and splits them by hook function signature:

- `get_dataobj` receives only kwargs it declares.
- `get_affine` receives only kwargs it declares.
- `convert` receives any remaining kwargs (i.e., hook-only conversion options).

If users provide extra keys that your hook does not accept, BrkRaw will drop
unsupported kwargs (and log the dropped keys at DEBUG) to avoid `TypeError`
crashes.

### Recommended pattern: accept `**kwargs` and validate

For hooks with many optional arguments, prefer:

- accept `**kwargs`
- normalize/validate into a typed options object (dataclass is recommended)

Example:

```python
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class Options:
    reference: str = "water"
    peak_ppm: float = 3.02

def _build_options(kwargs: Dict[str, Any]) -> Options:
    return Options(
        reference=str(kwargs.get("reference", "water")),
        peak_ppm=float(kwargs.get("peak_ppm", 3.02)),
    )

def get_dataobj(scan, reco_id=None, **kwargs):
    options = _build_options(kwargs)
    ...
```

This keeps the hook resilient to new keys, allows strict validation inside the
hook, and makes it easy to document defaults. BrkRaw Viewer also uses this
metadata to build converter-hook option forms. Providing `_build_options`
with a dataclass (or `HOOK_DEFAULTS`) improves the GUI experience and avoids
displaying internal parameters like `dataobj`/`affine`.

### Make `brkraw hook preset` useful

`brkraw hook preset <hook-entrypoint>` generates a YAML template by inspecting
your hook module.

To improve preset generation for kwargs-based hooks, expose one of:

- `HOOK_PRESET` / `HOOK_ARGS` / `HOOK_DEFAULTS`: mapping of default values
- `_build_options({})` that returns a dataclass (or an object with `__dict__`)

Example:

```python
HOOK_DEFAULTS = {
    "reference": "water",
    "peak_ppm": 3.02,
}
```

If none of these are available and your hook only takes `**kwargs`, BrkRaw
cannot infer supported keys and the preset will be empty. The BrkRaw Viewer
Convert tab relies on the same preset inference to render hook option inputs.

### Document supported keys clearly

Hook docs shipped via `brkraw_hook.yaml` (`docs:` or `readme:`) should include:

- supported hook args (name, type, default)
- what each argument affects
- example CLI usage (`--hook-arg` / `--hook-args-yaml`)

---

## Reference implementations

- Hook template repository: https://github.com/brkraw/brkraw-hook.git
