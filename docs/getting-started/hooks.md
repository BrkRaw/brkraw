# Converter hooks

BrkRaw supports **converter hook packages** that extend the conversion pipeline
without modifying the core library.

Hooks are distributed as normal Python packages, discovered via entry points,
and installed into your BrkRaw config root as addon files (specs, rules,
pruner specs, transforms).

---

## List available hooks

Show detected hook packages (installed status included):

```bash
brkraw hook list
```

If nothing appears, verify that the hook package is installed in the same
Python environment as `brkraw`.

---

## Install a hook

Install hook addons by hook name (or by entrypoint name):

```bash
brkraw hook install <hook-name>
```

Install all detected hooks at once:

```bash
brkraw hook install all
```

Reinstall if a newer version is available:

```bash
brkraw hook install <hook-name> --upgrade
```

---

## Read hook documentation

Print the hook's bundled documentation (if provided by the hook manifest):

```bash
brkraw hook docs <hook-name>
```

Render markdown nicely in the terminal (requires `rich`):

```bash
brkraw hook docs <hook-name> --render
```

---

## Generate hook argument presets

When a hook supports many optional arguments, generate a YAML template:

```bash
brkraw hook preset <hook-entrypoint> -o hook_args.yaml
```

Then pass it to `brkraw convert`:

```bash
brkraw convert /path/to/study --scan-id 14 --hook-args-yaml hook_args.yaml
```

---

## Uninstall a hook

Remove the installed hook addons from the config root:

```bash
brkraw hook uninstall <hook-name>
```

If dependencies are detected, uninstall may stop. To remove anyway:

```bash
brkraw hook uninstall <hook-name> --force
```

Note: uninstalling the hook addons does not uninstall the Python package.
To remove the package itself:

```bash
pip uninstall <hook-name>
```

---

## Example: brkraw-mrs

Install the hook package:

```bash
pip install brkraw-mrs
```

Install its addons into BrkRaw:

```bash
brkraw hook install brkraw-mrs
```

Optionally, view its docs:

```bash
brkraw hook docs brkraw-mrs --render
```

After installation, run conversion as usual. The hook is applied automatically
when the dataset matches the hook's conditions:

```bash
brkraw convert /path/to/study --scan-id 14
```
