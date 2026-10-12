# cache

Manage temporary data and cache files.

BrkRaw and its extensions may use a central cache directory (by default `~/.brkraw/cache`)
to store temporary data, downloaded assets, or intermediate processing results.
Extensions keep their files in their own subfolder (for example `sordino/` for the
SORDINO reconstruction hook, whose cache files can be several GB per scan).

Use this command to:

- check the current cache location and size, in total and per subfolder,
- clear cached files to free up disk space, all of them or chosen subfolders.

You can override the config root (and therefore the cache location) with `--root`.

!!! note "New in 0.6.1"
    `cache info` lists each subfolder, `cache clear --only NAME` clears chosen
    entries, and other commands warn when the cache grows too large (below).

---

## Subcommands

### cache info

Show the path, total size and file count of the cache directory, then one line
per entry: each subfolder, and `(files)` for the files directly in the cache
folder. Entry sizes do not follow links (they show what clearing frees; a link
is removed, not what it points to), so they can add up to less than the total.

```bash
brkraw cache info
```

Example output:

```text
Path:  /home/user/.brkraw/cache
Size:  11.90 GB
Files: 45
Entries:
  sordino/   11.88 GB  41 files
  viewer/    20.00 MB   3 files
  (files)     1.50 KB   1 files
```

---

### cache clear

Clear all files in the cache directory.

```bash
brkraw cache clear
```

By default, it prompts for confirmation if files exist:

```text
Clear 4 files from /home/user/.brkraw/cache? [y/N]:
```

Only `y` or `yes` clears; any other answer keeps the files.

To clear only some entries, name them with `--only` (repeatable; the names are
those of `cache info`):

```bash
brkraw cache clear --only sordino
brkraw cache clear --only sordino --only "(files)"
```

An unknown name stops the command before anything is deleted.

To skip confirmation:

```bash
brkraw cache clear --yes
brkraw cache clear -y
brkraw cache clear --only sordino -y
```

---

## Size warning before other commands

Before any other command (not `cache`, `config` or `init`, and never for `-h`
or `--version`), BrkRaw adds up the cache. When it is larger than
`cache.warn_size_gb` (in `config.yaml`, default `10`, in GB of 1024³ bytes), a
warning with the entry table goes to stderr:

```text
warning: the brkraw cache holds 11.90 GB in 45 files, more than 10.00 GB (cache.warn_size_gb):
  /home/user/.brkraw/cache
  sordino/   11.88 GB  41 files
  viewer/    20.00 MB   3 files
```

In a terminal it then asks, entry by entry and largest first:

```text
Clear sordino/ (11.88 GB, 41 files)? [y/N]:
```

Only `y` or `yes` deletes that entry. Enter, any other answer and end of input
keep it (end of input also stops the questions). Without a terminal (scripts,
CI, output to a pipe or file) nothing is asked and nothing is deleted; the
warning says how to clear. The command itself then runs as usual; its result
does not change.

To turn the check off, set `cache.warn_size_gb: 0` (or `.inf`) in `config.yaml`,
or set the environment variable `BRKRAW_NO_CACHE_CHECK=1` for one shell. The
check never stops a command: if it cannot measure the cache or write the
warning, the command runs without it.
