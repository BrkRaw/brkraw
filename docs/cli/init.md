# init

Create the brkraw config folder, and optionally install the default specs and
rules and the shell helpers.

```bash
brkraw init                              # asks each step
brkraw init --install-default --yes      # no questions; your shell file is not changed
brkraw init --yes --shell-rc ~/.zshrc    # no questions, and add the shell helpers
brkraw init --root /path/to/config       # another config folder
```

The config folder is `BRKRAW_CONFIG_HOME`, else `~/.brkraw`. Every command
also takes `--root DIR`.

!!! note "Changed in 0.6.0"
    `brkraw config init` was removed; `brkraw init` is the one command that
    creates the config folder.

## What it does

Asked step by step without `--yes`:

1. create the config folder and `config.yaml` (you can change the values);
2. install the default specs, rules, pruner specs and transforms
   (`--install-default`), needed for sidecar metadata (`-c`);
3. add the shell helpers `brkraw-set` and `brkraw-unset` to your shell file.

With `--yes`, brkraw asks nothing and writes `config.yaml` with the default
values. It changes a shell file only when you name one with `--shell-rc FILE`
(once; a second run sees the helpers and does nothing). Without `--yes`, the
shell helper question suggests `~/.zshrc` or `~/.bashrc`.

!!! note "Changed in 0.6.0rc1"
    In 0.6.0b1, `--yes` appended the shell helpers to `~/.zshrc` or
    `~/.bashrc` by itself. It no longer does.

## Options

| Option | Meaning |
| --- | --- |
| `--root ROOT` | Config folder to create or use. |
| `--no-exist-ok` | Stop if the folder already exists. |
| `--config` | Create or replace `config.yaml` only (asks for the values). |
| `--install-default` | Install the default specs, rules, pruner specs and transforms. |
| `--shell-rc FILE` | Append the shell helpers to this file (also with `--yes`). |
| `--yes` | No questions; use the defaults. Does not change any shell file. |

## Shell helpers

```bash
brkraw-set -p /path/to/study -s 3    # same as: eval "$(brkraw session set -p /path/to/study -s 3)"
brkraw-unset                         # clear the session defaults
```

See [session](session.md).
