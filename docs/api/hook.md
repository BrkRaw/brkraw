# hook (Python API)

Manage converter hook packages installed in the Python environment.

Hook packages extend conversion behavior via entry points in the
`brkraw.converter_hook` group. A hook package may also ship addon assets
(specs, rules, pruner specs, transforms) via a `brkraw_hook.yaml` manifest.

The hook API supports discovery, installation of packaged assets into the
configuration root, and uninstallation with dependency checks.

---

## Equivalent CLI command

`brkraw hook`

---

## Entry points

```python
from brkraw.api import hook_manager as hook
```

Note: `brkraw.api.hook_manager` manages hook packages and their installed addon
assets. `brkraw.api.hook` refers to the hook *spec* module (entrypoint
resolution/validation).

Public functions:

- `hook.list_hooks(root=None) -> List[Dict[str, Any]]`
- `hook.install_all(root=None, upgrade=False, force=False) -> Dict[str, List[str]]`
- `hook.install_hook(target, root=None, upgrade=False, force=False) -> str`
- `hook.read_hook_docs(target, root=None) -> Tuple[str, str]`
- `hook.uninstall_hook(target, root=None, force=False) -> Tuple[str, Dict[str, List[str]], bool]`

---

## Where Hooks Apply (Loader vs Scan)

In BrkRaw, converter hooks are applied at the **loader level**.

- Hooks are resolved and attached by `BrukerLoader` when you call loader APIs such as:
    - `loader.convert(...)`
    - `loader.get_dataobj(...)`
    - `loader.get_affine(...)`
- A hook works by overriding a scan’s conversion helpers (for example `get_dataobj`,
  `get_affine`, `convert`). The loader is responsible for resolving the hook and
  wiring those overrides onto the scan before use.

Scan objects are still important, but mainly for **hook development**:

- You typically use scan/reco access (`loader.get_scan(...)`, `scan.get_reco(...)`,
  reading parameters/files) to implement and test a new hook’s logic.
- Calling scan methods directly is not the primary “hook application” interface;
  use the loader for hook-aware execution so hook resolution and hook arguments
  are handled consistently.

---

## What is a hook

A converter hook is a Python package that:

   1. Exposes one or more entry points under the `brkraw.converter_hook` group.
2. Optionally ships a manifest file named `brkraw_hook.yaml` or `brkraw_hook.yml`.
3. The manifest may list addon assets to install into the configuration root:
   - specs
   - pruner_specs
   - rules
   - transforms

During installation, assets are installed under a hook-specific namespace.

---

## List available hooks (CLI: `brkraw hook list`)

List hooks discovered from installed Python packages:

```python
from brkraw.api import hook_manager as hook

items = hook.list_hooks()
for h in items:
    print(h["name"], h["version"], h["installed"], h["install_status"])
```

Each hook entry includes:

- `name`: hook distribution name
- `version`: package version (or `<Unknown>`)
- `entrypoints`: entry point names exposed by the hook
- `installed`: whether the hook has been installed into the config root
- `installed_version`: version recorded in the hook registry (if installed)
- `install_status`: one of `No`, `Yes`, `Partially`

`install_status` reflects whether the registry exists and whether the
recorded installed files still exist under the configuration root.

---

## Install hook assets into a config root

Hook installation installs manifest assets into the configuration root and
records results in `hooks.yaml`.

Installation does not install the Python package itself. The package must
already be available in the environment (for example via pip/conda).

### Install a single hook (CLI: `brkraw hook install`)

```python
from brkraw.api import hook_manager as hook

status = hook.install_hook("my-hook-package")
print(status)  # "installed" or "skipped"
```

The `target` may be:

- a hook distribution name, or
- an entry point name exposed by that hook

If multiple hooks match the target, installation fails with `ValueError`.
If no hook matches, installation fails with `LookupError`.

### Install all hooks (CLI: `brkraw hook install --all`)

```python
from brkraw.api import hook_manager as hook

result = hook.install_all()
print(result["installed"])
print(result["skipped"])
```

### Upgrade behavior

If a hook is already installed:

- `upgrade=False` and `force=False` skips installation
- `upgrade=True` reinstalls only if the package version is newer
- `force=True` reinstalls regardless of version

```python
hook.install_hook("my-hook-package", upgrade=True)
hook.install_hook("my-hook-package", force=True)
```

Version comparison uses PEP 440 rules when available, otherwise falls back to
a numeric string comparison.

---

## Namespacing rules for installed assets

Manifest assets are installed under a hook-specific namespace derived from
the hook name (non-alphanumeric characters are replaced with `_`).

Installed paths are recorded in a registry file:

- `<config_root>/hooks.yaml`

Rules inside hook manifests may reference specs by basename. During install,
rule `use` fields are rewritten so they point to the namespaced installed
spec paths when applicable.

---

## Uninstall hook assets (CLI: `brkraw hook uninstall`)

Uninstall removes the assets previously installed by the hook, based on the
registry record.

```python
from brkraw.api import hook_manager as hook

name, removed, module_missing = hook.uninstall_hook("my-hook-package")
print(name)
print(removed["specs"])
print(removed["rules"])
print("Python module missing:", module_missing)
```

Behavior:

- if the hook is not installed (no registry entry), uninstallation fails with `LookupError`
- removed files are unlinked if present
- missing files are ignored (no error)
- the return value includes `module_missing`, which is `True` when the hook's
  entrypoint cannot be found in the current Python environment (package may have
  already been uninstalled).

### Dependency checks and force removal

Before removing each file, the hook uninstaller checks whether the file is
referenced by other installed assets (for example, specs referenced by rules).

If dependencies are found:

- `force=False` raises `RuntimeError`
- `force=True` removes anyway

```python
hook.uninstall_hook("my-hook-package", force=True)
```

---

## Design notes

- Hook discovery reads entry points from the Python environment.
- Hook installation installs addon assets into the selected configuration root.
- Hook registry (`hooks.yaml`) is the source of truth for uninstall.
- Uninstall is conservative by default and blocks when dependencies are detected
  unless forced.
