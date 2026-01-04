# CLI: addon

Manage installed specs, pruner specs, rules, transforms, and maps.

Specs include remapper specs (`info_spec`, `metadata_spec`). Pruner specs are
installed separately under `pruner_specs/`.

## brkraw addon add

Install a spec or rule file.

Example:

- `brkraw addon add path/to/spec.yaml`

## brkraw addon list

List installed specs, pruner specs, rules, transforms, and maps.

Example:

- `brkraw addon list`

Notes:

- Spec listings include `name`, `version`, `description`, and `category` from `__meta__`.

- Map listings show the bound spec filenames when available.

## brkraw addon attach-map

Attach a context map to an installed spec.

Examples:

- `brkraw addon attach-map path/to/maps.yaml metadata_common`

- `brkraw addon attach-map path/to/maps.yaml metadata_common --category metadata_spec`

Notes:

- The spec must already be installed.

- The context map is copied into `maps/`, and the spec `__meta__.context_map` is updated.

- If the spec already has a context map, you will be prompted to replace it.

- Use `--force` to replace without prompting.

## brkraw addon rm

Remove installed addons by filename (wildcards supported).

Examples:

- `brkraw addon rm metadata_func.yaml`

- `brkraw addon rm "*.yaml" --kind spec --force`

- `brkraw addon rm "prune.yaml" --kind pruner`

- `brkraw addon rm "maps.yaml" --kind map`

Notes:

- Dependency checks run by default; use `--force` to remove anyway.

- `--kind` can limit removal to `spec`, `pruner`, `rule`, `transform`, or `map`.

- Removing a context map clears any matching `__meta__.context_map` entries.

## brkraw addon edit

Open an installed spec or rule in the configured editor (`editor` or `$EDITOR`).

Examples:

- `brkraw addon edit metadata_anat --kind spec`

- `brkraw addon edit rules.yaml --kind rule`

- `brkraw addon edit prune.yaml --kind pruner`

- `brkraw addon edit metadata_spec --kind rule --category metadata_spec`
