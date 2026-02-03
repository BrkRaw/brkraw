# Command Line Interface (CLI)

This page provides a quick-start overview of the BrkRaw Command Line Interface (CLI).
The CLI is designed for interactive inspection and lightweight conversion of
Paravision datasets, with support for extensible rules, specs, and sequence-specific hooks.

---

## Inspect a dataset (brkraw info)

Print a structured overview of a Paravision dataset, including
study-level and scan-level information.

```bash
brkraw info /path/to/study
```

This command works with dataset directories, zip archives, and
Paravision-exported `.PvDatasets` files.

To include detailed scan and reconstruction information:

```bash
brkraw info /path/to/study --scope full
```

---

## Inspect scan parameters (brkraw params)

Search acquisition or reconstruction parameters from Paravision parameter files
(e.g. `method`, `acqp`, `visu_pars`, `reco`).

Search for a parameter key across the study:

```bash
brkraw params /path/to/study -k PVM_RepetitionTime
```

Limit the search to a specific scan:

```bash
brkraw params /path/to/study -k PVM_RepetitionTime --scan-id 3
```

Limit the search to a specific reconstruction within a scan:

```bash
brkraw params /path/to/study -k PVM_RepetitionTime --scan-id 3 --reco-id 1
```

Restrict the search to specific parameter files:

```bash
brkraw params /path/to/study -k PVM_RepetitionTime --file method acqp
```

This command is useful for inspecting protocol settings and understanding
how acquisition and reconstruction parameters vary before conversion.

---

## Convert a scan to NIfTI (brkraw convert)

Convert a single scan using the default reconstruction.

```bash
brkraw convert /path/to/study --scan-id 3
```

If `--scan-id` is supplied without `--reco-id`, BrkRaw converts all available recos.

Specify a reconstruction ID and output directory:

```bash
brkraw convert /path/to/study \
    --scan-id 3 \
    --reco-id 1 \
    --output ./nifti_out
```

Output filenames and directory structure are controlled by the
configured layout entries and templates.

---

## Generate sidecar metadata

Write metadata sidecars alongside the converted NIfTI files.

```bash
brkraw convert /path/to/study \
    --scan-id 3 \
    --reco-id 1 \
    --sidecar
```

The content of sidecar metadata is determined by context maps,
rules, and specs.

---

## Convert multiple studies (brkraw convert-batch)

Convert all Bruker studies located under a root directory. This command is intended
for batch-style conversion when multiple studies are organized under a common folder.

The target path should be a directory containing one or more Paravision studies.

```bash
brkraw convert-batch /path/to/root_folder
```

By default, each detected study is converted using the configured rules, specs,
and hooks.

Common options:

- `-o, --output`: Output directory for converted files
- `--sidecar`: Generate metadata sidecars
- `--context-map`: Override the context map used for conversion
- `--hook-arg`, `--hook-args-yaml`: Pass arguments to conversion hooks
- `--space`: Select output coordinate space (`raw`, `scanner`, `subject_ras`)
- `--no-convert`: Parse metadata and generate sidecars without converting images

Example with explicit output directory and sidecar generation:

```bash
brkraw convert-batch /path/to/root_folder \
    --output ./converted \
    --sidecar
```

This command is useful for converting large collections of studies in a
consistent and reproducible manner.

For large-scale automation, consider using the Python API.

---

## Install and manage hooks

BrkRaw supports optional, installable hooks that extend conversion and
reconstruction workflows for specific modalities or sequences (e.g. MRS, DTI).

!!! note "Available hook packages"
    Currently installable hook packages include `brkraw-mrs` and `brkraw-dti`.

### Install a hook

First, install the hook package using pip:

```bash
python -m pip install <hook-package>
```

Then register the hook with BrkRaw:

```bash
brkraw hook install <hook-name>
```

Once a hook is installed, it is automatically applied during conversion.
You can use `brkraw convert` or `brkraw convert-batch` as usual, without changing your workflow.

```bash
brkraw convert /path/to/study --scan-id 3
```

If a hook requires additional options, pass them explicitly using
`--hook-arg` or `--hook-args-yaml`:

```bash
brkraw convert /path/to/study \
    --scan-id 3 \
    --hook-arg "<hook-name>:key=value"
```

Hook-specific arguments and supported options are documented by each hook package.

### List installed hooks

Show all hooks currently available to BrkRaw:

```bash
brkraw hook list
```

This includes both built-in hooks and hooks installed from external packages.

### Uninstall a hook

Remove a previously installed hook from BrkRaw:

```bash
brkraw hook uninstall <hook-name>
```

This does not uninstall the Python package itself. To remove the package:

```bash
python -m pip uninstall <hook-package>
```

## When to use the CLI

The CLI is best suited for:

- Interactive inspection of datasets and metadata
- One-off or small batch conversions
- Shell-based conversion workflows

For complex logic, conditional processing, or large-scale automation,
use the Python API instead.
