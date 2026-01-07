# CLI: hook

Manage converter hook packages and their addon assets (rules/specs/transforms).


## brkraw hook list

List installed converter hook packages. Metadata comes from the Python package
metadata (name, version, description) plus converter hook entrypoint names.

```bash
brkraw hook list
```


## brkraw hook install

Install addon assets bundled with a hook package.

```bash
brkraw hook install brkraw-sordino
```

Install all hook packages detected in the current environment:

```bash
brkraw hook install all
```

Reinstall when a newer package version is available:

```bash
brkraw hook install brkraw-sordino --upgrade
```

Notes:

- Hook packages are discovered via the `brkraw.converter_hook` entrypoint group.

- Each package must ship a `brkraw_hook.yaml` manifest that lists the spec/rule/
  transform files to install (see contrib docs).

- Hook assets are installed under a package namespace (for example
  `~/.brkraw/specs/<hook_name>/`) to avoid filename collisions.

- `install all` skips hooks that are already installed unless `--upgrade` is set.


## brkraw hook uninstall

Remove addon assets installed by a hook package and print the pip uninstall
command for the package itself.

```bash
brkraw hook uninstall brkraw-sordino
```

Notes:

- This command removes installed specs/rules/transforms registered by the hook.

- The Python package itself is not uninstalled; use the printed `pip uninstall`
  command to remove it from the environment.


## brkraw hook docs

Show hook documentation from the package manifest.

```bash
brkraw hook docs brkraw-sordino
```

Notes:

- The hook package must ship a `brkraw_hook.yaml` with a `docs` (or `readme`)
  entry that points to a packaged markdown/text file.
- Use `--render` to render markdown via `rich` when it is installed.
