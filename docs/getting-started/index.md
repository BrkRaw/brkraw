# Getting Started

This section provides task-oriented entry points for using BrkRaw.
Each page focuses on a common workflow with minimal setup and practical examples.

---

## Installation

### Prerequisites

BrkRaw supports Python 3.8 or higher. We recommend Python 3.10+ for better compatibility
with current and future extension modules, including converter hooks.

### Virtual Environment

We recommend installing BrkRaw in a virtual environment to isolate dependencies and avoid conflicts.

Common tools include:

- **[Conda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html)**: Popular for scientific computing.
- **[uv](https://github.com/astral-sh/uv)**: A fast Python package and project manager.
- **[pyenv](https://github.com/pyenv/pyenv)**: Simple Python version management.

### Install via pip

Install the latest stable release from PyPI:

```bash
python -m pip install brkraw
```

!!! tip "Why `python -m`?"
    Using `python -m pip` ensures that the package is installed into the specific
    Python environment you are currently using. Running `pip` directly can sometimes
    install packages into a different Python version if your system `PATH` is not configured perfectly.

To upgrade an existing installation:

```bash
python -m pip install --upgrade brkraw
```

Verify the installation:

```bash
brkraw --help
```

---

## Initial configuration

BrkRaw uses a user-level configuration directory for output layout,
logging, and extensions. Initialize the default configuration by running:

```bash
brkraw init
```

This creates a configuration directory (by default under `~/.brkraw`)
and a base `config.yaml` file.

Most users can start with the defaults and adjust settings later as needed.

---

## Next step

Choose the entry point that matches your use case:

- [**Command Line Interface (CLI)**](cli.md)  
- [**Python API**](api.md)
- [**Graphical User Interface (GUI)**](gui.md)
- [**BIDS integration**](bids.md)
- [**User Configuration**](config.md)