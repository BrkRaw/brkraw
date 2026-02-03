# hook

Manage converter hook packages and their bundled addon assets (specs, rules, pruner specs, transforms).

A converter hook is a Python package that exposes one or more entrypoints in the
`brkraw.converter_hook` group. Hook packages can optionally ship addon files via a
hook manifest (`brkraw_hook.yaml` / `brkraw_hook.yml`).

!!! note "Available hook packages"
    Currently installable hook packages include `brkraw-mrs` and `brkraw-dti`.

---

## Common options

### --root

Override config root directory (default: `BRKRAW_CONFIG_HOME` or `~/.brkraw`).

```bash
brkraw hook --root /path/to/config list
```

---

## What gets installed

When you install a hook, BrkRaw installs addon assets under a per-hook namespace
to avoid filename collisions:

- specs: `~/.brkraw/specs/<hook-namespace>/...`
- rules: `~/.brkraw/rules/<hook-namespace>/...`
- pruner specs: `~/.brkraw/pruner_specs/<hook-namespace>/...`
- transforms: `~/.brkraw/transforms/<hook-namespace>/...`

BrkRaw also records installed files in a registry file:

- `~/.brkraw/hooks.yaml`

This registry is used for status reporting and clean uninstall.

---

## hook list

List detected hook packages in the current Python environment and show whether
their addon assets are installed in the config root.

```bash
brkraw hook list
```

---

## hook install

Install addon assets bundled with a hook package.

```bash
brkraw hook install <hook-name>
```

You can also install by entrypoint name:

```bash
brkraw hook install <entrypoint-name>
```

Install all detected hooks:

```bash
brkraw hook install all
```

Options:

- `--upgrade`: reinstall when a newer version is available.
- `--force`: reinstall even if the same (or older) version is installed.

---

## hook uninstall

Remove addon assets installed by a hook.

```bash
brkraw hook uninstall <hook-name>
```

Option:

- `--force`: remove even if dependency checks are detected.

Notes:

- This removes files recorded in `~/.brkraw/hooks.yaml`.
- The Python package itself is not uninstalled automatically.

---

## hook docs

Show documentation shipped by a hook package (from its manifest).

```bash
brkraw hook docs <hook-name>
```

Option:

- `--render`: render markdown using `rich` (if installed).

---

## hook preset

Generate a YAML template for hook arguments by inspecting the hook entrypoint signature.

```bash
brkraw hook preset <hook-entrypoint>
```

Write to a file:

```bash
brkraw hook preset <hook-entrypoint> -o hook_args.yaml
```

You can pass the generated file to `brkraw convert` / `brkraw convert-batch` via `--hook-args-yaml`.
