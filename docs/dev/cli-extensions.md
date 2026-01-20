# Building CLI plugins

CLI plugins are Python packages that add new subcommands to the `brkraw` CLI.

This page covers authoring and packaging. For user-facing behavior and
terminology, see [Extensibility model](../reference/extensibility.md) and
[Addons and plugins](../reference/addons-and-plugins.md).

---

## When to build a CLI plugin

Build a CLI plugin when you want to:

- Add a **new top-level command** (for example `brkraw viewer`)
- Ship **project-specific workflows** that orchestrate multiple BrkRaw APIs
- Provide **GUI or interactive tools** alongside BrkRaw
- Expose functionality that does not fit the convert/info/params model

---

## Entrypoint group

CLI plugins are registered via the `brkraw.cli` entrypoint group.

Example `pyproject.toml` entry:

```toml
[project.entry-points."brkraw.cli"]
viewer = "brkraw_viewer.cli:get_command"
```

- The entrypoint name becomes the subcommand (`brkraw viewer`).
- The callable must return an `argparse` command definition compatible with
  BrkRaw's CLI dispatcher.

---

## Interaction with hooks

CLI plugins and converter hooks are orthogonal:

- Converter hooks customize *how scans are converted*.
- CLI plugins customize *how users interact with BrkRaw*.

---

## Recommended starting point

Use the official CLI extension template repository:

- CLI plugin template: https://github.com/brkraw/brkraw-cli.git

The template demonstrates:

- CLI entrypoint registration
- Command structure and argument parsing
- Integration with the BrkRaw Python API
- Packaging and distribution as an external plugin
