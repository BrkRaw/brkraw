# Command Line Interface (CLI)

This page provides a quick-start overview of the BrkRaw Command Line Interface (CLI).
The CLI is designed for interactive inspection and lightweight conversion of
ParaVision datasets, with support for extensible rules, specs, and sequence-specific hooks.

---

## Inspect a dataset (brkraw info)

Print a structured overview of a ParaVision dataset, including
study-level and scan-level information.

```bash
brkraw info /path/to/study
```

This command works with dataset directories, zip archives, and
ParaVision-exported `.PvDatasets` files.

The default scope (`full`) shows the study and every scan. To see only the
study, or to include reco entries (with each reco's frame axes, such as
`echo(2), cycle(3)`):

```bash
brkraw info /path/to/study --scope study
brkraw info /path/to/study --show-reco
```

---

## Inspect scan parameters (brkraw params)

Search acquisition or reconstruction parameters from ParaVision parameter files
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

Convert one scan (every reco of it):

```bash
brkraw convert /path/to/study --scan-id 3
```

Without `--reco-id`, brkraw converts every reco of the scan; without
`--scan-id`, every scan.

Specify a reconstruction ID and output directory:

```bash
brkraw convert /path/to/study \
    --scan-id 3 \
    --reco-id 1 \
    --output ./nifti_out
```

Output file names and folders come from the config layout, or from a context
map next to the dataset (see [Layout and naming](../extensions/layout.md) and
[BIDS integration](bids.md)).

---

## Generate sidecar metadata

Write metadata sidecars alongside the converted NIfTI files.

```bash
brkraw convert /path/to/study \
    --scan-id 3 \
    --reco-id 1 \
    --sidecar
```

The sidecar content comes from the metadata spec (installed with
`brkraw init --install-default`) plus the `sidecar` fields of a context map.

---

## Convert many studies (brkraw convert --batch)

Convert every study in a folder (sub-folders and `.zip` files directly under
it):

```bash
brkraw convert /path/to/studies --batch --output ./converted --sidecar
```

Each study uses its own same-name context map, if any. The other `convert`
options apply to every study; `-s`, `-r` and `-M` cannot be used with
`--batch`. See [convert](../cli/convert.md).

---

## Share a study (brkraw prune)

Copy a study, or chosen scans, into one zip:

```bash
brkraw prune /path/to/study -s 3 5                           # values unchanged
brkraw prune /path/to/study --anonymize --subject-id M01     # example anonymization
```

Nothing is anonymized unless you ask for it. See [prune](../cli/prune.md).

---

## Install and manage hooks

BrkRaw supports optional, installable hooks that extend conversion and
reconstruction workflows for specific modalities or sequences (e.g. MRS, DTI).

!!! note "Available hook packages"
    Currently installable hook packages include `brkraw-mrs`, `brkraw-dti`
    and `brkraw-sordino`.

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
You can use `brkraw convert` (with or without `--batch`) as usual, without changing your workflow.

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
