# Getting Started

This guide covers the minimum setup steps and the quickest ways to run BrkRaw
from both the CLI and Python.

## Installation

Install from GitHub:

```bash
pip install git+https://github.com/BrkRaw/brkraw.git
```

For development:

```bash
pip install -e .
```

## Configuration

Initialize the config root and defaults:

```bash
brkraw init
```

Common flags:

- `--root` to override the config root.
- `--no-config` to skip creating `config.yaml`.
- `--install-example` to install example rules/specs.
- `--shell-rc` to append shell helpers.
- `--yes` to skip prompts.

The config reference lives in `docs/configuration.md`.

## CLI quickstart

Inspect a dataset:

```bash
brkraw info /path/to/dataset.zip
```

Convert a scan to NIfTI:

```bash
brkraw convert /path/to/dataset.zip -s 1
```

Convert everything under a root:

```bash
brkraw convert-batch /path/to/root -o /path/to/out
```

See `docs/cli/info-and-params.md` and `docs/cli/convert.md` for full CLI
options.

## Python API quickstart

Load a dataset and inspect metadata:

```python
import brkraw as brk

loader = brk.load("/path/to/dataset.zip")
info = loader.info(scope="study", as_dict=True)
print(info["Study"])
```

Convert a scan and save:

```python
nii = loader.convert(3, reco_id=1, format="nifti")
nii.to_filename("scan3.nii.gz")
```

For API mappings to CLI commands, see `docs/api/cli-workflows.md`.
