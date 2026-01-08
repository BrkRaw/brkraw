# Dataset viewer (CLI extension)

`brkraw-viewer` is a graphical dataset viewer distributed as a
separate CLI extension.

The viewer has been intentionally separated from the BrkRaw core to
encourage independent contributions and experimentation around GUI
development.

A new GUI is planned. The current viewer provides a minimal
implementation based on functionality from earlier BrkRaw versions.

---

## Install the viewer

Install the extension package:

```bash
pip install brkraw-viewer
```

Verify the command is available:

```bash
brkraw-viewer --help
```

---

## Launch

Start the viewer:

```bash
brkraw-viewer
```

Select a dataset directory, zip archive, or `.PvDatasets` file from the UI.

---

## When to use it

The viewer is useful for:

- Browsing study and scan structure
- Checking scan and reconstruction IDs
- Inspecting acquisition metadata interactively

For conversion and reproducible workflows, use the BrkRaw CLI or
Python API instead.
