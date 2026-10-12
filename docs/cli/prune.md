# prune

Copy a ParaVision study into one zip, whole or only the scans and recos you
choose. The source is never changed.

```bash
brkraw prune /path/to/study.zip                     # ./pruned_study.zip: all scans, no changes
brkraw prune                                        # scanner console: the open study
brkraw prune /path/to/study.zip -s 3 5 -r 1 -o scans_3_5.zip
brkraw prune /path/to/study.zip --exclude-files fid
brkraw prune /path/to/study.zip --institution "Example University"
brkraw prune /path/to/study.zip --anonymize --subject-id M01 --dry-run
```

By default every file of the chosen scans is copied as it is, including raw
data (`fid`, `rawdata.job0`) and study files such as `subject`. **Nothing is
anonymized.** For sharing outside your institution, use `--anonymize` (or
your own [pruner spec](../extensions/pruner-specs.md)) and check the result.

Without a path, the study set with `brkraw session` is used, or on a scanner
console the study open in ParaVision (with several open studies, brkraw asks
which one in a terminal).

!!! note "Changed in 0.6.0"
    `--spec` is no longer required; `--spec-name` was merged into `--spec`;
    `--scan-ids` / `--reco-ids` became `-s` / `-r`; the built-in spec
    `deid4share` became `anonymize`; `--mode` was replaced by `--files` /
    `--exclude-files`. See [Migrating to 0.6](../getting-started/migrating.md).

## What to copy

| Option | Meaning |
| --- | --- |
| `-s`, `--scan-id` | Copy only these scans (space or comma separated). Study files are kept. |
| `-r`, `--reco-id` | Copy only these recos of each chosen scan. |
| `--files NAME …` | Copy only files with these names or relative paths. |
| `--exclude-files NAME …` | Copy everything except files with these names (for example `fid`). |

brkraw warns about a chosen scan that is missing, a scan with raw data only
(it cannot be converted), and a scan with neither image nor raw data files.

## Values

| Option | Meaning |
| --- | --- |
| `--institution NAME` | Write `NAME` into the institution fields that exist (`ACQ_institution`, `VisuInstitution`, `SUBJECT_institution`). |
| `--anonymize` | Apply the example anonymization spec shipped with brkraw (`anonymize`). A starting point, not a guarantee. |
| `--spec SPEC` | Apply a pruner spec: a YAML path, an installed name or a built-in name. Not with `--anonymize`. |
| `--subject-id ID` | Value for `$subject_id` (default `anon`). |
| `--study-id ID` | Value for `$study_id` (default `anon`). |
| `--set-var KEY=VALUE` | Fill another `$KEY` placeholder (repeatable). A placeholder left unfilled stops the run. |
| `--strip-jcamp-comments` / `--keep-jcamp-comments` | Remove or keep `$$` comment lines (default: the spec's setting; kept without a spec). |

## Output

| Option | Meaning |
| --- | --- |
| `-o`, `--output` | Output zip. It changes only the file name; the top folder inside the zip stays the study folder name (or the spec's `root_name`). |
| `--overwrite` | Replace an existing output file. Without it, an existing file stops the run. |
| `--dry-run` | Show what would be copied and changed; write nothing. |
| `--no-validate` | Skip pruner spec validation. |
| `--root DIR` | Config folder to use. |

Default output names (in the current folder):

| Run | Output |
| --- | --- |
| no spec, or a spec without `anonymize: true` | `pruned_<study>.zip` |
| `--anonymize`, or a spec with `anonymize: true` | `pruned_anon_<subject-id>_<study-id>.zip` (the original study name is not used) |

The zip is written to a temporary file first and moved into place, so an
interrupted run leaves no partial zip. Members over 2 GiB are written in ZIP64
format.

## The record: `.prune.yaml`

Next to the zip, brkraw writes `<output>.prune.yaml` with the time, the
command, the input and output file names (the input name is left out when
anonymizing), the spec file name with its SHA-256 and a summary of the spec,
and the options used. It records names only, never full paths.

## Anonymizing

`--anonymize` keeps the image files, replaces subject and study IDs with
`--subject-id` / `--study-id`, removes names, operators, institution,
station, dates and UIDs, removes `$$` comment lines and sets the zip's top
folder to the subject ID. Some fields that can still hold names or the
original folder name (scan descriptions, reconstruction inputs) are only
suggested in the spec. Before sharing:

```bash
brkraw prune /path/to/study.zip --anonymize --subject-id M01 --dry-run
brkraw prune /path/to/study.zip --anonymize --subject-id M01
brkraw info pruned_anon_M01_anon.zip
```

To change what is anonymized, copy the built-in spec, edit it and use
`--spec`; keep `anonymize: true` in your copy so the output name and the
record do not carry the original study name. The format is described in
[Pruner specs](../extensions/pruner-specs.md).

## Python API

See [prune (Python API)](../api/prune.md).
