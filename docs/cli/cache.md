# cache

Manage temporary data and cache files.

BrkRaw and its extensions may use a central cache directory (by default `~/.brkraw/cache`)
to store temporary data, downloaded assets, or intermediate processing results.

Use this command to:

- check the current cache location and size,
- clear cached files to free up disk space.

---

## Subcommands

### cache info

Show the path, total size, and file count of the cache directory.

```bash
brkraw cache info
```

Example output:

```text
Path:  /home/user/.brkraw/cache
Size:  12.50 MB
Files: 4
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

To skip confirmation:

```bash
brkraw cache clear --yes
```
