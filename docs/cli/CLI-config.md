# CLI: config

Manage the configuration root and related paths.

## brkraw config init

Create the config root and optional `config.yaml`.

Examples:

- `brkraw config init`

- `brkraw config init --no-config`

## brkraw config show

Show resolved config values as YAML.

Example:

- `brkraw config show`

Defaults are included even if the key is missing from `config.yaml`.

## brkraw config path

Print a specific config path.

Example:

- `brkraw config path specs`

- `brkraw config path pruner_specs`


## brkraw config set

Set a config key to a YAML value.

Example:

- `brkraw config set output.layout_entries '[{key: Subject.ID, entry: sub, hide: false}]'`

- `brkraw config set output.layout_template='sub-{Subject.ID}/study-{Study.ID}'`

- `brkraw config set logging.level=DEBUG`

## brkraw config unset

Remove a config key.

Example:

- `brkraw config unset output.layout_template`

## brkraw config reset

Reset `config.yaml` to defaults.

Example:

- `brkraw config reset --yes`

## brkraw config edit

Open `config.yaml` in the configured editor (`editor` or `$EDITOR`).

Example:

- `brkraw config edit`
