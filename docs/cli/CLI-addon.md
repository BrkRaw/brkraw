# CLI: addon

Manage installed specs, pruner specs, rules, and transforms.

Specs include remapper specs (`info_spec`, `metadata_spec`). Pruner specs are
installed separately under `pruner_specs/`.

## brkraw addon add

Install a spec or rule file.

Example:

- `brkraw addon add path/to/spec.yaml`

## brkraw addon list

List installed specs, pruner specs, rules, and transforms.

Example:

- `brkraw addon list`

Notes:

- Spec listings include `name`, `version`, `description`, and `category` from `__meta__`.

## brkraw addon rm

Remove installed addons by filename (wildcards supported).

Examples:

- `brkraw addon rm metadata_func.yaml`

- `brkraw addon rm "*.yaml" --kind spec --force`

- `brkraw addon rm "prune.yaml" --kind pruner`

Notes:

- Dependency checks run by default; use `--force` to remove anyway.

- `--kind` can limit removal to `spec`, `pruner`, `rule`, or `transform`.

## brkraw addon edit

Open an installed spec or rule in the configured editor (`editor` or `$EDITOR`).

Examples:

- `brkraw addon edit metadata_anat --kind spec`

- `brkraw addon edit rules.yaml --kind rule`

- `brkraw addon edit prune.yaml --kind pruner`

- `brkraw addon edit metadata_spec --kind rule --category metadata_spec`
