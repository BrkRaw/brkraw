# CLI overview

The `brkraw` CLI is organized around a few core tasks:

- Initialize a reproducible config root (`init`, `config`)
- Keep defaults across commands in a shell session (`session`)
- Inspect datasets (`info`, `params`)
- Convert scans and write outputs (`convert`, `convert-batch`)
- Manage mapping logic and extensions (`prune`, `addon`, `hook`)

This section documents what each command is for and how they fit together.

Recommended starting sequence:

1. Initialize:

    ```bash
    brkraw init
    ```

2. Inspect a dataset:

    ```bash
    brkraw info /path/to/study
    ```

3. Convert a scan:

    ```bash
    brkraw convert /path/to/study --scan-id 3
    ```

4. When running many conversions, use session defaults:

    ```bash
    eval "$(brkraw session set --path /path/to/study --scan-id 3 --reco-id 1)"
    brkraw convert
    ```

Notes:

- Output naming is controlled by configuration (`config.yaml`) and optionally by
  a `context_map` YAML at runtime.
- Extensions are installed as addons (rules/specs/transforms files) and plugins
  (hook packages and CLI plugins as Python packages).

Roadmap:

- Practical BIDS organization requiring scan_id mapping, modality-aware naming,
  and project-specific rules is planned as `brkraw-bids`.
