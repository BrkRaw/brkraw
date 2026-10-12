# Pruner specs

A pruner spec is a YAML file that tells `brkraw prune` which files to copy
and which parameter values to change. This page is the reference for the
format; [prune](../cli/prune.md) shows how to run it.

!!! note "Changed in 0.6.0"
    `brkraw prune` no longer needs a spec: without one it copies the chosen
    scans unchanged. The built-in example spec is now called `anonymize`
    (was `deid4share`). New keys: `jcamp_headers`, `anonymize`. A placeholder
    left unfilled now stops the run. See
    [Migrating to 0.6](../getting-started/migrating.md).

## Example

```yaml
__meta__:
  name: lab_share
  version: "1.0.0"
  description: Share image files with lab IDs.
  category: pruner_spec

anonymize: true                 # this spec anonymizes (naming and record as --anonymize)
mode: keep
files: [subject, acqp, method, reco, visu_pars, 2dseq]
root_name: "$subject_id"
strip_jcamp_comments: true
jcamp_headers: {OWNER: anon}

update_params:
  subject:
    SUBJECT_id: "<$subject_id>"
    SUBJECT_name_string: null
  visu_pars:
    VisuSubjectId: "<$subject_id>"
    VisuInstitution: null
```

```bash
brkraw prune /path/to/study --spec lab_share.yaml --subject-id M01
```

## Keys

| Key | Required | Meaning |
| --- | --- | --- |
| `__meta__` | yes | `name` (lowercase, `_` between words), `version`, `description`, `category: pruner_spec` |
| `files` | yes | file names or dataset-relative paths (for example `visu_pars`, `3/pdata/1/visu_pars`) |
| `mode` | no | `keep` (default): copy only the files in `files`; `drop`: copy everything except them |
| `dirs` | no | folder rules, see below |
| `update_params` | no | JCAMP parameter changes per file, see below |
| `strip_jcamp_comments` | no | remove `$$` comment lines from copied JCAMP files (default `false`) |
| `jcamp_headers` | no | values for `##NAME=` header lines of every copied JCAMP file, for example `{OWNER: anon}` |
| `root_name` | no | name of the top folder inside the zip (default: the original study folder name) |
| `add_root` | no | put the files under a top folder (default `true`) |
| `anonymize` | no | `true` when the spec anonymizes: the default output name uses the replacement IDs and the `.prune.yaml` record leaves out the original input name, as with `--anonymize` |

Unknown keys are errors (`--no-validate` skips the check).

## Folder rules: `dirs`

```yaml
dirs:
  - {level: 1, dirs: [3, 5]}   # scan folders 3 and 5
  - {level: 3, dirs: [1]}      # reco folder 1 under pdata
```

- Level 1 is the scan folder, level 3 the reco folder under `pdata`.
- With `mode: keep` a rule keeps only the listed folders; with `mode: drop`
  it removes them.
- A rule for level L only affects paths that have a folder at level L:
  study files such as `subject` and scan files such as `3/acqp` are decided
  by `files` alone.
- `brkraw prune -s` and `-r` replace the level 1 and level 3 rules.

## Parameter changes: `update_params`

```yaml
update_params:
  <file name>:
    <PARAMETER>: <new JCAMP value>   # text, written as it is
    <PARAMETER>: null                # removes the parameter
```

- Keys are file names (not paths) and apply to every copied file of that
  name.
- A value is written as the new JCAMP value text; text values in ParaVision
  are in angle brackets (`"<M01>"`).
- `null` removes the parameter. A parameter that is not in the file is not
  added.
- A file that cannot be parsed as JCAMP stops the run.

## Placeholders: `$name`

Values may contain `$name` placeholders, filled from the command line:

| Placeholder | Filled by |
| --- | --- |
| `$subject_id` | `--subject-id ID` (default `anon`) |
| `$study_id` | `--study-id ID` (default `anon`) |
| `$KEY` | `--set-var KEY=VALUE` (repeatable) |

- A name is letters, digits and `_` after `$`, so `$project_shared` is the
  placeholder `project_shared`. To follow a placeholder with text, put
  another character first: `$project-shared`.
- A placeholder left unfilled stops the run with its name. Placeholders in
  `__meta__` (for example in the description) do not need to be filled.
- `--set-var` without `=` is an error.

## The built-in `anonymize` spec

`brkraw prune --anonymize` (or `--spec anonymize`) uses the example spec that
ships with brkraw. It keeps the image files, replaces subject and study IDs
with `$subject_id` / `$study_id`, removes names, operators, institution,
station, dates and UIDs, and sets the top folder to the subject ID. Lines
starting with `# suggest:` are fields that can still hold names or the
original folder name (scan descriptions, reconstruction inputs); they are
left off on purpose. Copy the file, turn on what your data needs, and check
the result with `--dry-run` and `brkraw info` before sharing.

Find the file with `python -c "import brkraw, pathlib; print(pathlib.Path(brkraw.__file__).parent / 'default/pruner_specs/anonymize.yaml')"`,
or install the defaults with `brkraw init --install-default` and look in the
config folder's `pruner_specs/`.

## Where brkraw looks for a spec

`--spec VALUE` is tried in this order: a file path; a file in the current
folder; the config folder's `pruner_specs/`; a spec built into brkraw.
`brkraw addon add my_spec.yaml` installs a spec into the config folder.

## Python API

See [prune (Python API)](../api/prune.md).
