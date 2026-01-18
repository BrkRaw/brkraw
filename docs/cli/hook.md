# brkraw hook

Manage converter hook packages and their bundled addon assets (specs, rules, pruner specs, transforms).

A converter hook is a Python package that exposes one or more entrypoints in the `brkraw.converter_hook` group and can optionally ship addon files via a hook manifest.

Typical example: `brkraw-mrs` (a converter hook package that installs specs/rules/transforms for MRS outputs).

---

## What gets installed

When you install a hook, BrkRaw installs addon assets under a per-hook namespace to avoid filename collisions:

- specs: `~/.brkraw/specs/<hook_namespace>/...`
- rules: `~/.brkraw/rules/<hook_namespace>/...`
- pruner specs: `~/.brkraw/pruner_specs/<hook_namespace>/...`
- transforms: `~/.brkraw/transforms/<hook_namespace>/...`

BrkRaw also records installed files in a registry file:

- `~/.brkraw/hooks.yaml`

This registry is used for status reporting and clean uninstall.

---

## brkraw hook list

List detected converter hook packages in the current Python environment and show whether their addon assets are installed.

```bash
brkraw hook list
```

The table shows:

- name: distribution name (package name)
- version: installed package version
- entrypoints: names registered in `brkraw.converter_hook`
- installed: one of:
  - Yes (all expected assets are present)
  - Partially (registry exists but some files are missing)
  - No (hook detected but not installed into config root)

---

## brkraw hook install

Install addon assets bundled with a hook package.

Install by package name:

```bash
brkraw hook install brkraw-mrs
```

Install by entrypoint name (if you prefer the entrypoint label):

```bash
brkraw hook install mrs
```

Install all detected hooks in the current environment:

```bash
brkraw hook install all
```

Upgrade behavior:

```bash
brkraw hook install brkraw-mrs --upgrade
```

Force reinstall (even if same or older version is already installed):

```bash
brkraw hook install brkraw-mrs --force
```

Notes:

- Hooks are discovered via the `brkraw.converter_hook` entrypoint group.
- A hook package must ship a manifest file named:
  - `brkraw_hook.yaml` or `brkraw_hook.yml`
- The manifest lists addon assets to install:
  - `specs`, `rules`, `pruner_specs`, `transforms`
- During install, rule `use:` references may be rewritten so rules point to the namespaced spec paths (for example `specs/<namespace>/<specfile>.yaml`).

---

## brkraw hook uninstall

Remove addon assets installed by a hook and print the pip uninstall command for the Python package itself.

```bash
brkraw hook uninstall brkraw-mrs
```

Force uninstall even when dependencies are detected:

```bash
brkraw hook uninstall brkraw-mrs --force
```

Notes:

- This removes installed addon files recorded in `~/.brkraw/hooks.yaml`.
- The Python package itself is not uninstalled automatically.
  The command prints something like:

```text
To uninstall the package, run: pip uninstall brkraw-mrs
```

---

## brkraw hook docs

Show documentation shipped by a hook package (from its manifest).

```bash
brkraw hook docs brkraw-mrs
```

Render markdown using `rich` (if installed):

```bash
brkraw hook docs brkraw-mrs --render
```

Notes:

- The manifest must include either:
  - `docs: path/to/file.md`
  - or `readme: path/to/file.md`
- The docs file is resolved relative to the manifest location inside the package.

---

## brkraw hook preset

Generate a YAML template for hook arguments by inspecting the hook entrypoint signature.

```bash
brkraw hook preset mrs
```

Write to a file:

```bash
brkraw hook preset mrs -o hook_args.yaml
```

You can pass the generated file to `brkraw convert` via `--hook-args-yaml`.

Notes:

- The template is a best-effort based on Python function signatures.
- Unknown keys in presets are ignored at runtime (logged at DEBUG).

---

## Common workflow example (brkraw-mrs)

Install the hook assets:

```bash
brkraw hook install brkraw-mrs
```

Verify installation status:

```bash
brkraw hook list
```

Read hook-specific usage notes:

```bash
brkraw hook docs brkraw-mrs --render
```

If you later remove it:

```bash
brkraw hook uninstall brkraw-mrs
pip uninstall brkraw-mrs
```
