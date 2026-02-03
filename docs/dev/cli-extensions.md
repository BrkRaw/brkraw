# Building CLI plugins

CLI plugins are Python packages that add new subcommands to the `brkraw` CLI.

This page covers authoring and packaging. For user-facing behavior and
terminology, see [Extensibility model](../extensions/extensibility.md) and
[Addons and plugins](../extensions/addons-and-plugins.md).

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
viewer = "brkraw_viewer.cli:register"
```

- The entrypoint name becomes the subcommand (`brkraw viewer`).
- The entrypoint must be a callable that accepts the main CLI `subparsers` and
  registers one or more commands (i.e., `register(subparsers)`).

Minimal example:

```python
import argparse

def cmd_viewer(_: argparse.Namespace) -> int:
    print("hello from viewer")
    return 0

def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
    parser = subparsers.add_parser("viewer", help="Open the GUI viewer.")
    parser.set_defaults(func=cmd_viewer)
```

---

## Runtime behavior and best practices

BrkRaw discovers CLI plugins at startup by iterating entrypoints in the
`brkraw.cli` group.

Notes:

- If a plugin fails to import/load, BrkRaw prints a warning and continues without it.
- Keep imports inside your `register(...)` or command handlers lightweight, to avoid
  slowing down `brkraw --help` and other CLI operations.

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
