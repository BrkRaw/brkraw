# CLI: prune

Create a pruned dataset zip using a prune spec.

## brkraw prune

Required:

- `path`: source dataset path

- `--spec`: prune spec YAML path

Optional overrides:

- `--output`: override spec `dest`

- `--no-validate`: skip spec validation

- `--strip-jcamp-comments`: remove `$$` comment lines from kept JCAMP files

- `--mode`: override spec `mode` (`keep` or `drop`)

- `--scan-ids`: override scan IDs to keep (space or comma separated)

- `--reco-ids`: override reco IDs to keep (space or comma separated)

If `--output` is omitted, the default filename uses `root_name` from the spec
(falling back to `<input>_pruned` when `root_name` is missing).

Notes on `update_params`:

- This feature edits JCAMP parameter values and should be used with care.

- It applies to every matching parameter file (by basename), not to a specific scan id.

- Use it for de-identification or redaction when preparing datasets for sharing.

Optional JCAMP cleanup:

- `strip_jcamp_comments: true` removes `$$` comment lines from JCAMP files that
  are kept in the pruned archive.

- No helper utilities are provided; you must ensure JCAMP compliance yourself.

Compatibility guidance:

- File selectors match basenames, so you can list `reco`, `visu_pars`, `2dseq`

  without the full `pdata/<reco_id>/` path.

- A minimal readable dataset needs `method`, `acqp`, plus `reco`, `visu_pars`,

  and `2dseq` from each kept reconstruction.

- Missing `visu_pars` prevents BrkRaw from recognizing the study.

- Keep `subject` only when subject metadata is required (remove it for privacy).

Dropping scans:

- Scans live under top-level numeric folders (e.g. `1/`, `2/`, `13/`).

- Use `dirs` to drop scan folders by level. `dirs` inherits the top-level `mode`.

  For example, to drop scan 13:

```yaml
dirs:

  - level: 1

    dirs: ["13"]
```

Keeping specific scans/reconstructions without editing the spec:

```bash
brkraw prune /data/study --spec specs/prune.yaml --scan-ids 1 3
brkraw prune /data/study --spec specs/prune.yaml --scan-ids 1 --reco-ids 1,2
```

Example:

```bash
brkraw prune /data/study --spec specs/prune.yaml --output /data/out/pruned.zip
```

## Example prune spec (minimal compatible)

```yaml
__meta__:
  name: "pruner_default"
  version: "1.0.0"
  description: "Default prune spec."
  category: "pruner_spec"
mode: "keep"
files:

  - "method"

  - "acqp"

  - "reco"

  - "visu_pars"

  - "2dseq"

update_params:
  method:
    PVM_ScanTimeStr: "120.0"
strip_jcamp_comments: true
add_root: true
root_name: "study_pruned"
```
