# Building converter hook packages

Converter hook packages are Python distributions that provide custom conversion
logic and (optionally) ship addon assets for case-dependent behavior.

This page covers authoring and packaging. For user-facing behavior and
terminology, see [Extensibility model](../extensions/extensibility.md) and
[Addons and plugins](../extensions/addons-and-plugins.md).

---

## Required entrypoint

Expose your converter hook via the `brkraw.converter_hook` entrypoint group in
`pyproject.toml`:

```toml
[project.entry-points."brkraw.converter_hook"]
<hook-entrypoint> = "<hook_package>.hook:get_hook"
```

The returned hook object must conform to the converter hook schema defined in
`brkraw.specs.hook.validator`.

---

## Hook manifest

To support `brkraw hook install`, your hook package should ship a
`brkraw_hook.yaml` (or `brkraw_hook.yml`) manifest file. This manifest lists
addon assets that BrkRaw will copy into the user's config directories.

If your hook package does not ship a manifest, it can still provide conversion
code via the `brkraw.converter_hook` entrypoint, but it will not be able to
install rules/specs/transforms via the hook installer.

Example `brkraw_hook.yaml`:

```yaml
docs: README.md
specs:
  - specs/info.yaml
  - specs/metadata.yaml
rules:
  - rules/<hook-entrypoint>.yaml
transforms:
  - transforms/<hook-entrypoint>.py
```

Tip: `<hook-entrypoint>` is the name registered in the `brkraw.converter_hook`
entrypoint group. It is the identifier used by `brkraw hook preset` and by the
`--hook-arg HOOK:KEY=VALUE` syntax.

### Manifest rules

- Paths are resolved relative to the manifest file location.
- `specs` and `rules` must be YAML files.
- `transforms` are copied into `transforms/<hook_name>/` (namespaced).
- Spec installs still honor `__meta__.transforms_source`.
  Referenced transforms are installed automatically and specs are rewritten to
  point to the installed copies.
- All assets are installed under a namespace derived from the hook package name
  to avoid filename collisions.
- Rules may reference specs by name or filename; when filenames match manifest
  specs, the installer rewrites them to the namespaced paths.
- `docs` (or `readme`) should point to a packaged markdown/text file used by
  `brkraw hook docs`.

Optional:

- `pruner_specs`: you can ship pruner specs with a hook when you want to bundle
  a “share/de-identify” pruning preset alongside the conversion pipeline.
- `context_maps`: shared context maps, bases that users include by name (for
  example a BIDS base map shipped by `brkraw-bids`). They are installed under
  `context_maps/<namespace>/`, need `__meta__.name` and `version`, and are
  removed with the hook. Users include them with `include: [name]` or
  `include: [{use: name, version: "1.0.0"}]`.

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
brkraw-<hook-package>/
  pyproject.toml
  src/
    <hook_package>/
      __init__.py
      hook.py
      brkraw_hook.yaml
      specs/
        info.yaml
        metadata.yaml
      rules/
        <hook-entrypoint>.yaml
      transforms/
        <hook-entrypoint>.py
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

The CLI also accepts a shorter form where the top-level mapping is the hook map:

```yaml
<hook-entrypoint>:
  key: value
```

At conversion time, BrkRaw looks up args by the selected hook entrypoint name
(for example `<hook-entrypoint>`) and splits them by hook function signature:

- `get_dataobj` receives only kwargs it declares.
- `get_affine` receives only kwargs it declares.
- `convert` receives any remaining kwargs (i.e., hook-only conversion options).

If users provide extra keys that your hook does not accept, BrkRaw will drop
unsupported kwargs (and log the dropped keys at DEBUG) to avoid `TypeError`
crashes.

### NIfTI output options in `convert`

`xyz_units`, `t_units` (`brkraw convert --xyz-units/--t-units`) and
`override_header` (`--header`) describe the output file, not how the data or
the affine are read. They are not hook args:

- `convert` gets them when it takes a parameter of that name or `**kwargs`,
  whether or not `get_dataobj`/`get_affine` take `**kwargs`. The CLI always
  passes both units (default `mm`, `sec`); `override_header` is passed only
  when it is given.
- `get_dataobj` and `get_affine` get them only when they name them as
  parameters, never through `**kwargs`.

A hook with its own `convert` writes them into its header; for example:

```python
def convert(scan, dataobj, affine, *, xyz_units="mm", t_units="sec",
            override_header=None, **kwargs):
    nii = Nifti1Image(dataobj, affine)
    nii.header.set_xyzt_units(xyz_units, t_units)
    for key, value in (override_header or {}).items():
        nii.header[key] = value
    return nii
```

Up to 0.6.1rc1 the three options went to `get_dataobj`/`get_affine` when
those took `**kwargs` (also BrkRaw's own, so a hook with only `convert` never
got them), and `override_header` never reached a hook.

### The reco and intensity scaling in `convert`

`convert(scan, dataobj, affine, **kwargs)` gets the data as read: BrkRaw does
not apply the per-frame slope/offset rule for a hook with its own `convert`
(see [Intensity scaling](../cli/convert.md#intensity-scaling)). Two helpers
(0.6.0rc2) let the hook produce the same values as BrkRaw's default path:

- `reco_id` is passed to `convert` when it takes a `reco_id` parameter or
  `**kwargs`. Use it instead of guessing the reco from the data or affine.
- `brkraw.api.scale_frames(scan, reco_id, dataobjs)` returns
  `(dataobjs, scaling_applied)`. Pass the data objects as a tuple (one per
  slice pack). When the slopes or offsets differ per frame, the data come
  back scaled (float) and `scaling_applied` is True; otherwise they are
  unchanged and the header carries the value. Give the flag to
  `scan.get_nifti1image(..., scaling_applied=...)`.

```python
from brkraw import api

def convert(scan, dataobj, affine, **kwargs):
    reco_id = kwargs["reco_id"]
    data = dataobj if isinstance(dataobj, tuple) else (dataobj,)
    affines = affine if isinstance(affine, tuple) else (affine,)
    data, applied = api.scale_frames(scan, reco_id, data)
    return scan.get_nifti1image(reco_id=reco_id, dataobjs=data, affines=affines,
                                scaling_applied=applied)
```

With `brkraw convert --axis/--frames`, `convert` also gets `axis` and
`frames` (when it takes them or `**kwargs`) and the data are already the
selected frames; pass the same values to `scale_frames(..., axis=, frames=)`.
The legacy `cycle_index`/`cycle_count` are passed the same way; give them to
`scale_frames` too. With `-F` (`flatten_fg`) the data reach `convert` with the
frame axes already flattened; `scale_frames` accepts them as they are. One
exception: when every spatial axis has size 1 and two or more frame axes have
different slopes or offsets, the flatten order cannot be told from the data,
and `scale_frames` raises `ValueError` instead of guessing; convert such data
without `-F`.

### Stopping for memory, and the CLI retry (0.6.1)

A hook that estimates, before it starts, that a scan needs more memory than it
allows may refuse with a `MemoryError` (or a subclass). If the error has an
attribute `retry_kwargs`, a dict of hook arguments that would let it run (for
example `{"max_memory_gb": 7.5}`), `brkraw convert` in a terminal shows the
message and asks `Proceed anyway with max_memory_gb=7.5 for scan N? [y/N]`.
On `y`/`yes` it converts that scan once more with those arguments added to the
hook's arguments (they override the user's value of the same key); any other
answer, a second stop, a missing `retry_kwargs` or no terminal (scripts, CI)
leaves the error as it was: the scan fails and the run goes on as before.
Only the hook's own arguments can be proposed this way; keep them to limits
the user could also give with `--hook-arg`.

```python
class MyResourceError(MemoryError):
    def __init__(self, message, retry_kwargs=None):
        super().__init__(message)
        self.retry_kwargs = retry_kwargs

def get_dataobj(scan, reco_id=None, *, max_memory_gb=None, **kwargs):
    need_gb = estimate_gb(scan, **kwargs)
    if need_gb > (max_memory_gb or default_limit_gb()):
        raise MyResourceError(f"needs about {need_gb:.1f} GB", {"max_memory_gb": round(need_gb + 0.05, 1)})
    ...
```

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
