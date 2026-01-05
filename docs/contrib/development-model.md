# Core vs Addon Development

BrkRaw development is split into two paths:

- **Core updates**: keep compatibility with the latest Paravision layouts and
  metadata conventions.
- **Addons/Plugins**: implement rules/specs/transforms/context_map updates,
  or custom CLI tooling, without touching core.

## When core changes are acceptable

Core changes are limited to Paravision compatibility. If you think a core
change is required, start with a GitHub Discussion and explain why the behavior
cannot be implemented as an addon or plugin.

## Using the shared VSCode setup

Core changes should use the shared VSCode configuration to keep workflows
consistent across contributors.

1) Create a virtual environment and install dev dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

2) In VSCode, select the workspace interpreter (`.venv/bin/python`).

3) Optional tasks (Command Palette):

- `Setup: venv + deps`
- `MkDocs: Serve`
- `Release: Prep (bump + notes)`
