# CLI quickstart

This page provides a minimal, task-oriented introduction to the
BrkRaw command-line interface. The examples are intended for
first-time users who want to inspect and convert Paravision datasets
from the terminal.

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

Search acquisition or reconstruction parameters across scans.

```bash
brkraw params /path/to/study PVM_RepetitionTime
```

Limit the search to a specific scan:

```bash
brkraw params /path/to/study PVM_RepetitionTime --scan-id 3
```

This is useful for verifying protocol settings before conversion.

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
    --out ./nifti_out
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
    --write-metadata
```

The content of sidecar metadata is determined by context maps,
rules, and specs.

---

## Convert multiple scans (batch-style usage)

Convert all available scans in a dataset using a shell loop.

```bash
for sid in 1 2 3 4; do
    brkraw convert /path/to/study \
        --scan-id $sid \
        --reco-id 1 \
        --out ./nifti_out
done
```

For large-scale automation, consider using the Python API.

---

## Manage addons (brkraw addon)

List installed addons (rules, specs, hooks):

```bash
brkraw addon list
```

Add a new addon:

```bash
brkraw addon add /path/to/spec.yaml
```

Remove an installed addon:

```bash
brkraw addon remove spec.yaml
```

---

## When to use the CLI

The CLI is best suited for:

- Interactive inspection of datasets
- One-off or small batch conversions
- Verifying metadata and scan IDs
- Running conversions in shell-based workflows

For complex logic, conditional processing, or large-scale automation,
use the Python API instead.
