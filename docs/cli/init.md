# init

Initialize a BrkRaw config root and (optionally) install the default addon set.

This command is a convenience wrapper around `brkraw config init` plus optional
extras (default addons, shell helpers).

---

## Usage

```bash
brkraw init
```

---

## Options

### --root

Override the config root directory (default: `BRKRAW_CONFIG_HOME` or `~/.brkraw`).

```bash
brkraw init --root /path/to/config
```

### --no-exist-ok

Fail if the root directory already exists.

```bash
brkraw init --no-exist-ok
```

### --config

Create or replace `config.yaml` only (does not install default addons or shell helpers).

```bash
brkraw init --config
```

### --install-default

Install the default bundled addon set (specs/rules/pruner specs/transforms) into the config root.

```bash
brkraw init --install-default
```

### --shell-rc

Append shell helper functions to a shell rc file (defaults to `~/.zshrc` or `~/.bashrc`).

This enables convenient wrappers like `brkraw-set` / `brkraw-unset` for setting
session defaults.

```bash
brkraw init --shell-rc ~/.zshrc
```

### --yes

Skip prompts and use defaults.

```bash
brkraw init --yes
```
