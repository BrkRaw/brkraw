# CLI overview

`brkraw -h` lists the commands in three groups:

| Group | Command | What it does |
| --- | --- | --- |
| Data | [`info`](info.md) | show study and scan information (including each reco's frame axes) |
| | [`params`](params.md) | search parameter files for a key |
| | [`convert`](convert.md) | convert scans to NIfTI (one, several or all), one study or a folder of studies (`--batch`) |
| | [`prune`](prune.md) | copy a ParaVision study, or chosen scans, into one zip |
| Workspace | [`init`](init.md) | create the config folder and install defaults |
| | [`config`](config.md) | show and change the config |
| | [`cache`](cache.md) | show and clear the cache |
| | [`session`](session.md) | keep defaults (path, scan ID …) in the shell |
| Extensions | [`addon`](addon.md) | install and manage spec, rule, pruner spec and shared context map files |
| | [`hook`](hook.md) | register the files of hook packages installed with pip |

Every command takes `--root DIR` for another config folder (default:
`BRKRAW_CONFIG_HOME`, else `~/.brkraw`). Without a dataset path, commands use
the study set with `brkraw session`, or on a scanner console the study open in
ParaVision.

## First steps

```bash
brkraw init                                   # config folder (asks about defaults and shell helpers)
brkraw info /path/to/study                    # what is in the study
brkraw convert /path/to/study -s 3 -o out/    # one scan
eval "$(brkraw session set -p /path/to/study -s 3 -r 1)"
brkraw convert -o out/                        # uses the session defaults
```

Output names come from the config layout, or from a context map next to the
dataset (see [Layout and naming](../extensions/layout.md) and
[Context maps](../extensions/context-map.md)). File formats of the
extensions are described in the [Extensions](../extensions/extensibility.md)
section.
