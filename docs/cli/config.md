# config

Manage BrkRaw configuration locations and `config.yaml`.

Use this command to:

- create or reset config roots,
- inspect resolved configuration,
- set or unset individual keys,
- open `config.yaml` in your preferred editor.

By default, BrkRaw stores configuration under `~/.brkraw`, or you can override it
with `BRKRAW_CONFIG_HOME` or `--root`.

---

## Subcommands

### config init

Create the config folders and optionally create `config.yaml`.

```bash
brkraw config init
```

Options:

- `--no-config`  
  Do not create `config.yaml`.

- `--no-exist-ok`  
  Fail if the config root already exists.

---

### config show

Print resolved config values (ordered for readability).

```bash
brkraw config show
```

If `config.yaml` is empty, prints:

```text
config.yaml: <empty>
```

---

### config path

Print a specific config path.

```bash
brkraw config path root
brkraw config path config
brkraw config path rules
brkraw config path specs
brkraw config path transforms
```

---

### config edit

Edit `config.yaml` in an editor.

```bash
brkraw config edit
```

BrkRaw resolves the editor in this order:

1. `config.yaml: editor`
2. `$VISUAL`
3. `$EDITOR`

If `config.yaml` does not exist, it is reset to defaults before editing.

---

### config set

Set a config key.

```bash
brkraw config set logging.level DEBUG
brkraw config set output.float_decimals 4
```

Nested keys are supported with dot notation:

```bash
brkraw config set logging.print_width 160
```

You can also use `KEY=VALUE` form:

```bash
brkraw config set logging.level=DEBUG
```

Values are parsed as YAML scalars (e.g., `true`, `false`, numbers, lists).

---

### config unset

Unset a config key.

```bash
brkraw config unset logging.level
brkraw config unset output.layout_template
```

Nested keys are supported with dot notation. When nested dicts become empty,
they are removed automatically.

---

### config reset

Reset `config.yaml` to defaults.

```bash
brkraw config reset
```

To skip confirmation:

```bash
brkraw config reset --yes
```
