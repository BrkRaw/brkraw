# Core vs Addon Development

BrkRaw development follows two clearly separated paths:

- **Core updates**: maintain compatibility with current and upcoming
  Paravision layouts, file structures, and metadata conventions.
- **Addons and plugins**: implement rules, specs, transforms, context_map
  definitions, or custom CLI tooling without modifying core code.

This separation is intentional and helps keep the core stable while allowing
rapid experimentation and customization through extensions.

---

## When core changes are appropriate

Core changes are intentionally limited to Paravision compatibility and
low-level loader or infrastructure concerns.

If you believe a change must live in core, start with a GitHub Discussion and
explain clearly why the behavior cannot be implemented as an addon or plugin.
Once there is agreement, open one or more scoped issues before submitting a
pull request.

---

## Using the shared VSCode setup

Core development should use the shared VSCode configuration to ensure
consistent workflows across contributors.

1) Create a virtual environment and install development dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

2. In VSCode, select the workspace interpreter (`.venv/bin/python`).

3. Optional tasks available from the Command Palette:

- `Standard: Setup venv + deps`
- `Standard: MkDocs Serve`
- `Optional: Release Prep (bump + notes)`
