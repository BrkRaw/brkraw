# CLI Extensions and Plugins

BrkRaw supports extensibility not only at the conversion level (rules, specs,
converter hooks) but also at the **CLI level**.

CLI extensions let you add entirely new commands and workflows without
modifying the BrkRaw core repository.

---

## When to use a CLI extension

Use a CLI extension when you want to:

- Add a **new top-level command** (for example `brkraw viewer`)
- Ship **project-specific workflows** that orchestrate multiple BrkRaw APIs
- Provide **GUI or interactive tools** alongside BrkRaw
- Expose functionality that does not fit the convert/info/params model

Even when using converter hooks, a CLI extension is recommended if you want
custom command-line interfaces or user-facing tools.

---

## Entrypoint group

CLI plugins are registered via the `brkraw.cli` entrypoint group.

Example `pyproject.toml` entry:

```toml
[project.entry-points."brkraw.cli"]
viewer = "brkraw_viewer.cli:get_command"
```

- The entrypoint name becomes the subcommand (`brkraw viewer`)
- The callable must return an `argparse` command definition compatible with
  BrkRaw's CLI dispatcher

---

## Interaction with hooks

CLI extensions and converter hooks are **orthogonal**:

- Converter hooks customize *how scans are converted*
- CLI extensions customize *how users interact with BrkRaw*

A CLI extension may:

- Call `brkraw.load()` and use the Python API directly
- Trigger conversions that rely on installed rules/specs/hooks
- Provide visualization, QA, or batch orchestration tools

This separation keeps conversion logic reusable while allowing rich interfaces.

---

## Example: brkraw-viewer

A typical use case is a lightweight viewer or inspection tool:

```bash
brkraw viewer /path/to/study --scan-id 3
```

Internally, the plugin may:

- Load the dataset using the BrkRaw Python API
- Reuse existing metadata and layout logic
- Display images or summaries using external libraries

The command itself lives entirely outside the BrkRaw core.

---

## Recommended starting point

Use the official CLI extension template repository:

- **CLI plugin template**:
  [https://github.com/brkraw/brkraw-cli.git](https://github.com/brkraw/brkraw-cli.git)

The template demonstrates:

- CLI entrypoint registration
- Command structure and argument parsing
- Integration with the BrkRaw Python API
- Packaging and distribution as an external plugin

---

## Design guidelines

- Prefer CLI extensions over core changes for user-facing tools
- Keep conversion logic in hooks; keep UI/workflows in CLI plugins
- Package CLI plugins as standalone repositories for easier distribution
- Avoid tight coupling to internal BrkRaw modules beyond the public API

---

## Related documents

- Converter hook packages: `reference/hook-packages.md`
- Addons and rules/specs: `reference/addons-and-plugins.md`
- Contribution guide: `dev/contributing.md`

