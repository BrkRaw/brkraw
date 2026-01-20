# Getting Started

This section provides **task-oriented entry points** for using BrkRaw.
Each page focuses on a common user workflow with minimal setup and
practical examples.

Before diving into specific workflows, make sure BrkRaw is installed
and initialized.

---

## Installation

Install BrkRaw using pip:

```bash
pip install brkraw
```

Verify the installation:

```bash
brkraw --help
```

This documentation assumes that BrkRaw is available on your PATH.

---

## Initial configuration

BrkRaw uses a user-level configuration directory to manage output
layout, logging, and installed extensions.

Initialize the default configuration by running:

```bash
brkraw init
```

This creates a configuration directory (by default under `~/.brkraw`)
and a base `config.yaml` file.

Most users can start with the default configuration and adjust it
later as needed. A guided overview of commonly modified settings is
available in the **Configuration basics** section.

---

## Choose a workflow

Select the entry point that best matches your use case:

- **CLI quickstart**  
  Inspect datasets and convert scans from the command line.

- **Python API quickstart**  
  Script conversions, automate workflows, and integrate BrkRaw into
  analysis pipelines.

- **Configuration basics**  
  Learn which configuration options are commonly adjusted and why.

- **Converter hooks**  
  Extend BrkRaw with modality-specific converters
  (e.g. NIfTI-MRS output).

- **MRS converter (brkraw-mrs)**  
  MRS-specific hooks and specs for NIfTI-MRS outputs.

- **BIDS integration (early guidance)**  
  Current reference path for BIDS-style workflows.

- **Dataset viewer**  
  Interactively inspect Paravision datasets using a lightweight viewer.

- **Admin tools (brkraw-backup)**  
  Optional admin-focused helpers for managing BrkRaw datasets and artifacts.

---

## Notes

- These pages focus on practical usage rather than exhaustive
  reference material.
- Advanced configuration options and full parameter definitions are
  documented elsewhere in the Reference sections.
- Some configuration options and extension interfaces may evolve in
  future releases as BrkRaw develops.
