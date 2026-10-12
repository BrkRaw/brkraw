# Release v0.6.1rc2

Date: 2026-10-12
Changes since 0.5.7

This is the second release candidate of 0.6.1 and the first 0.6 release
published from BrkRaw/brkraw. It is a pre-release: a GitHub pre-release and a
package on TestPyPI, not on PyPI. 0.6.1rc1 was tagged only on the development
fork, where it was used with real data. There is no 0.6.0 release.

- "Changes since 0.6.1rc1" below is new in this candidate: NIfTI output
  options now reach a converter hook's `convert`, and the checks on real data
  moved out of the test suite.
- "Changes since 0.6.0rc2 (0.6.1, for fork testers)" is what 0.6.1 adds to
  0.6.0: frames read from `2dseq` without reading the whole file, a fix for
  `cycle_index`, a cache size warning, and faster file opening.
- Everything else in this note is the 0.6.0 content, which reaches users for
  the first time in this release.

The main goal of 0.6.0 is context mapping for BIDS-style output. 0.6.0 also
rebuilds the subject orientation of all 16 poses and fixes per-frame intensity
scaling. **Moving from 0.5.x: read
[Migrating to 0.6](docs/getting-started/migrating.md)** (the same page is in
the documentation). Names and options change without aliases (except the
cycle options, see below).

## Highlights

- **Context maps v3.** A YAML file next to a dataset (same name) defines output
  values in namespaces you name, without changing the original information.
  Four value forms (direct, `from`, `from` + `map` + `default`, `when`), a
  `layout_template` with optional `[ ... ]` groups and `utils` values
  (`counter`, `slicepack`, `split`), `convert: false` to skip scans, `split`
  of multi-frame scans with numpy-style `{axis, frames}`, `sidecar` fields,
  and `include` of shared base maps. Output paths are planned first; a name
  collision stops the run by default (`on_collision: suffix` adds `_2`, `_3`).
- **Shared context maps**: `brkraw addon add` installs a base map into the
  config folder's `context_maps/`; hook packages can ship base maps (manifest
  key `context_maps`, installed under `context_maps/<package name>/` and
  removed with the hook). A dataset's own map stays next to the dataset.
- **`MethodBase`**: the method without the vendor prefix (`Bruker:EPI` →
  `EPI`); `Method` keeps the original value.
- **Frame selection**: `brkraw convert --axis/--frames` and
  `get_dataobj(..., axis=, frames=)`; `brkraw info` shows each reco's frame
  axes. `--cycle-index/--cycle-count` (and `cycle_index/cycle_count`) still
  work with a deprecation warning and are removed in 0.7.0.
- **prune redesign**: without a spec, the chosen scans are copied unchanged
  into `pruned_<study>.zip`; `--anonymize` applies the example spec
  `anonymize`; `--files`, `--exclude-files`, `--institution`, `--dry-run`;
  safe writing (temporary file, no overwrite without `--overwrite`, ZIP64 for
  large members); a `.prune.yaml` record with names only. Pruner spec keys
  `jcamp_headers` and `anonymize: true`.
- **Command line**: `convert --batch` (replaces `convert-batch`);
  `convert -s 3 4 5` (or `-s 3,4,5`) converts several scans; `brkraw init`
  only (`config init` removed); `--root` on every command; a ParaVision study
  chooser on scanner consoles; `brkraw -h` groups the commands (Data,
  Workspace, Extensions) and ends with first steps.

## Compatibility: what changes

| Removed or renamed | Use instead |
| --- | --- |
| context map syntax of 0.5.x (`type: mapping`, `cases`, `selector`, `target`, `override`, `__split__`, `__meta__.layout_entries`, `__meta__.slicepack_suffix`) | context map v3 (the loader names the old word) |
| `BRKRAW_CONVERT_CONTEXT_MAP`, `session set --convert-option CONTEXT_MAP=…` | same-name file next to the dataset, or `-M FILE` |
| `brkraw convert-batch` | `brkraw convert --batch` |
| `brkraw config init` | `brkraw init` |
| `brkraw prune --spec-name`, `--scan-ids`, `--reco-ids`, `--mode` | `--spec`, `-s/--scan-id`, `-r/--reco-id`, `--files` / `--exclude-files` |
| built-in pruner spec `deid4share` | `anonymize` (`--anonymize`) |
| `from brkraw.api import addon` (context maps) | `from brkraw.api import context_map` |
| `src/brkraw/schema/context_map.yaml` | removed (validation is in `brkraw.specs.context_map`) |

Behavior to know:

- `brkraw prune DATA` without a spec no longer stops; it copies without
  changing values. Nothing is anonymized unless you ask.
- `brkraw init --yes` writes `config.yaml` with defaults and changes no shell
  file; add the shell helpers with `--shell-rc FILE`.
- `brkraw convert -s` with two or more scans needs a folder for `--output`.
  With `-r`, every named scan must have that reco, else nothing is written;
  without `-s`, scans that lack it are skipped and a warning names them. An
  unknown scan ID stops the run before anything is written.
- `BRKRAW_SCAN_ID` (from `brkraw session`) is read with the same rule as `-s`:
  `info` and `convert` use every ID in it, `params` accepts one.
- `brkraw params` prints its result to standard output (not through the log).

## Outputs that change

The conversion code is unchanged since 0.6.0b1; the numbers below were
measured on 0.6.0b1.

### Intensity scaling (slope and offset)

ParaVision stores one `VisuCoreDataSlope` / `VisuCoreDataOffs` value per frame.

- Exactly equal values stay one header value and the data keeps its integer
  type: the output equals 0.5.7.
- Different values are applied to their own frames (the count is matched
  against the slice packs first, then against the frame axes multiplied from
  the last one); the data is written as floating point with header slope 1,
  so **such files are larger**. When no layout matches, brkraw warns and
  writes the data without scaling.
- Compared with 0.5.7 on brkraw's test data (61 datasets, 582 recos): 536
  exactly equal, 11 different — all with slopes that differ per frame: 10 DTI
  images (reco 2; slopes differing by factors from 10³ to about 10⁹) and one
  functional (fMRI) time series whose slope differs per repetition (up to
  about **3 %** over time). 0.5.7 scaled these with the first frame's value
  only. In the same data, 547 recos convert in both versions and 0.6.0b1 fails
  none that 0.5.7 converts; every converted reco matches an independent
  numpy reference (24 exactly, 523 within 1e-6).
- 0.6.0a1 (fork pre-release) stopped with "VisuCoreDataSlope has N values" on
  every reco with more than one frame per slice; fixed since 0.6.0b1. Do not
  use 0.6.0a1 for such data.
- New warnings (data unchanged): the frames of one slice pack do not share one
  orientation; the slice packs do not add up to the slice frame group; a slope
  or offset stored with 2+ dimensions does not match the frame axes. None
  appeared on the 107 multi-pack recos checked.

### Subject orientation (affine)

The subject orientation of all 16 poses is rebuilt from one list of steps.
Default output (`subject_ras`): 8 poses change from 0.5.7 (Biped Head_Left,
Head_Right; Quadruped Head_Supine, Foot_Supine, Head_Left, Head_Right,
Foot_Left, Foot_Right). Scanner space: 4 poses (Foot_Left, Foot_Right for Biped
and Quadruped). With a pose or subject-type override: 12 poses. Convert again
before comparing or combining with 0.5.7 outputs.

## Changes since 0.6.1rc1

- **NIfTI output options reach a converter hook.** `xyz_units`, `t_units`
  (`brkraw convert --xyz-units/--t-units`) and `override_header` (`--header`)
  now go to a hook's `convert` when it takes a parameter of that name or
  `**kwargs`, so a hook that builds its own NIfTI header can apply them. Up to
  0.6.1rc1 they went to `get_dataobj`/`get_affine` when those took `**kwargs`
  (so a hook that replaces only `convert` never got them), and
  `override_header` never reached a hook. `get_dataobj` and `get_affine` now
  get them only when they name them as parameters. An `override_header` passed
  to `convert` directly wins over one given as a hook argument. Conversion
  without a hook is unchanged. See "NIfTI output options in `convert`" in
  [Building converter hook packages](docs/dev/hook-packages.md).
- **Tests use synthetic data only.** The checks on approved anonymized
  studies (`BRKRAW_AGENT_FIXTURES`) moved from `tests/` to
  `scripts/validate/check_agent_fixtures.py`, which is run by hand before a
  release; CI and a plain `pytest` do not collect it. See
  [Contributing](docs/dev/contributing.md).

## Changes since 0.6.0rc2 (0.6.1, for fork testers)

- **`2dseq` is read by the frames you ask for.** `get_dataobj(..., axis=,
  frames=)` and `convert --axis/--frames` now read only those frames from a
  folder, a stored zip or a compressed zip, instead of reading the whole
  `2dseq` and cutting afterwards. Measured on a synthetic 150 MiB `2dseq`
  (128 x 128 x 16 slices x 300 cycles): asking for 3 cycles took about 3-8 MiB
  of extra memory (was 150 MiB; 407 MiB for a compressed zip), one cycle
  about 1-5 MiB. Values, dtype, shape and the array properties are the same
  as 0.6.0, including the memory layout that `convert -F` uses to choose the
  flatten order; when the smaller read would change that layout (a step
  slice such as `::2`, or a single frame or `a:b` slice of an axis that has
  other frame axes after it), brkraw reads all like 0.6.0. A compressed zip can only
  be read forward, so reading late frames still has to decompress the frames
  before them (in small steps, with no extra memory); a stored zip and a
  folder jump straight to the frames.
- **The whole `2dseq` is read once, not twice.** The file was opened twice
  for one read (an existence check and the read itself each loaded it), so a
  compressed zip was decompressed two times and needed about 2.6 times the
  file size in memory; now one time and about 1.1 times. `cycle_index/cycle_count`
  (deprecated) read only their block as well.
- **Damaged zip files:** a read of only some frames from a zip does not check
  the whole entry's CRC-32 (that needs every byte read), so if the zip is
  damaged, those frames can come back with wrong values where 0.6.0 stopped
  with `BadZipFile`. Reading all of the data still checks it. Check a
  zip you doubt with `python -m zipfile -t file.zip`.
- A read with `frames` no longer keeps the whole array in the scan afterwards
  (it did in 0.6.0); a later read of the full data reads the file again. If
  the full array is already loaded, `frames` cuts that array as before.
- **`get_dataobj(cycle_index=...)` no longer changes later reads.** In 0.6.0,
  after one call with the deprecated `cycle_index`/`cycle_count`, a plain
  `get_dataobj()` of the same scan returned that block instead of all of the
  data, and `axis`/`frames` calls after it cut the block (for example "frame 3
  out of range for 1 frames"). The block is now returned to that call only;
  what that call returns is unchanged.
- **Cache size warning:** before a command (not `cache`, `config`, `init`),
  brkraw warns on stderr when the cache folder is larger than
  `cache.warn_size_gb` (new config key, default 10 GB; 0 turns it off; or
  `BRKRAW_NO_CACHE_CHECK=1`) and shows each subfolder's size. In a terminal it
  asks per subfolder (for example `sordino/`), largest first, `[y/N]`; only
  `y`/`yes` deletes. Without a terminal nothing is asked or deleted. The
  command's own result does not change.
- **`brkraw cache`:** `cache info` lists each subfolder and `(files)` for the
  files directly in the folder; `cache clear --only NAME` (repeatable) clears
  only those entries; an unknown name deletes nothing.
  `brkraw.core.cache.get_info(..., by_entry=True)` and
  `clear(..., only=[...])` are the same in Python.
- **Hooks that stop for memory:** a hook may raise a `MemoryError` with a
  `retry_kwargs` dict (hook arguments that would pass, for example
  `{"max_memory_gb": 7.5}`); `brkraw convert` in a terminal asks "Proceed
  anyway?" and on `y` converts that scan once more with them. See
  [Building converter hook packages](docs/dev/hook-packages.md).
- **Faster, lighter file opening:** deciding whether a dataset file is a JCAMP
  parameter file now reads only its first 64 KiB. Before, the whole file was
  decoded and split into lines, so opening a 300 MB `2dseq` spent about 1.8 s
  and up to about 660 MB of extra memory on this check alone. Results are
  unchanged for real parameter files.

## Changes since 0.6.0rc1 (for fork testers)

- **Hook API:** a converter hook's `convert` now gets `reco_id` and the frame
  selection (`axis`, `frames`, legacy cycle options) when it takes them or
  `**kwargs`; the data stay as read. The new public
  `brkraw.api.scale_frames(scan, reco_id, dataobjs, axis=, frames=)` applies
  the per-frame slope/offset rule so a hook gives the same values as the
  default path (pass its flag to `get_nifti1image(..., scaling_applied=...)`);
  it also takes the legacy cycle options and data flattened by `-F` (with an
  error, not a guess, when every spatial axis is 1 and two or more frame axes
  have different values, because the flatten order cannot be told then).
  The default conversion uses the same function; its output is unchanged.
  See "Building converter hook packages" in the developer docs.
- **Python 3.8:** prune works again on 3.8 (`importlib_resources` fallback
  where `importlib.resources.files` was used without it); CI on 3.8 passes.

## Changes since 0.6.0b1 (for fork testers)

- `init --yes` no longer appends the shell helpers to `~/.zshrc`/`~/.bashrc`.
- `convert -s` takes several scans, with the checks above; `-s 99` for a scan
  that does not exist stops with a message (0.6.0b1 crashed).
- `params` prints to standard output; one scan-ID rule for `-s` and
  `BRKRAW_SCAN_ID`; `session` help lists only keys that are read.
- Help: first steps at the end of `brkraw -h`, one command table, clearer
  `addon` and `hook` descriptions (a hook package is installed with pip
  first).
- Checked with a real installed hook package: a shipped base map is installed,
  listed, included by name in a conversion, and removed with the hook.

## Other changes

- Development environment managed with uv (`uv.lock`, Python 3.12);
  packaging and `requires-python` unchanged.
- Tests: config isolation for every test, a synthetic PvDataset builder,
  manual checks on approved anonymized studies kept outside the repository
  (`BRKRAW_AGENT_FIXTURES`, `scripts/validate/`), the documentation's BIDS
  example checked by the test suite; a documentation build check
  (`mkdocs build --strict`) in CI; MkDocs pinned below 2 in the workflows.
- `unixtime_to_datetime` and study info tolerate missing dates (anonymized
  data loads).
- `brkraw.api.layout` is public; `brkraw config path` knows `pruner_specs` and
  `context_maps`; list/tuple hook arguments are parsed from the CLI.
- Documentation: rewritten context map, BIDS, prune, convert and layout pages;
  new "Pruner specs" and "Migrating to 0.6"; navigation by the CLI groups;
  consistent terms.

## All commits since 0.5.7

Subjects are shortened where they named internal planning steps; the
hashes are the fork's commits (`git log 0.5.7..0.6.0rc2`).

### Releases

- Prepare pre-release 0.6.0a1 (812ec9b)
- Prepare pre-release 0.6.0b1 (d8720a8)
- Prepare release candidate 0.6.0rc1 (201bd8f)
- Prepare release candidate 0.6.0rc2 (a0cde2c)

### Converter hooks

- Tests first: hook convert gets reco_id; public scale_frames applies the per-frame slope rule for hooks (72cea85)
- Tests: hook convert also gets the frame selection; brkraw.api import in the public-API test (6d6bf4d)
- Hook API: convert gets reco_id and the frame selection; public scale_frames (brkraw.api) applies the per-frame slope rule; default convert uses it (82e6227)
- Tests first: a hook can scale data flattened by flatten_fg (-F) with scale_frames, and gets the legacy cycle selection (a48062e)
- scale_frames accepts data flattened by flatten_fg (-F), as brkraw passes them to a hook; release notes and hook docs (0430264)
- Tests first: scale_frames refuses -F data whose flatten order cannot be told instead of guessing (2595a6e)
- scale_frames stops with an error when the -F flatten order cannot be told (all spatial axes 1, 2+ varying frame axes) (this commit)

### Python 3.8

- Tests first: every resources.files() user carries the Python 3.8 importlib_resources fallback (10f9dc9)
- Python 3.8: importlib_resources fallback for resources.files in prune and its test (a619a49)

### Orientation

- Fix quadruped supine subject affine (831b32a)
- Rebuild subject orientation for all 16 poses from one labeled step list (54af07d)
- Test each orientation step through _apply_pose_step (7e82630)

### Intensity scaling

- Handle nonuniform NIfTI scaling outside headers (1795e82)
- Model resolver scaling as array-capable metadata (63248f0)
- Route loader scaling through NIfTI update (2d93b67)
- Add failing tests for per-frame VisuCoreDataSlope handling (d398f8c)
- Per-frame VisuCoreDataSlope/Offs: equal values in the header, different values per frame (8ddb389)
- Add failing tests for the slope layout rule; rename a prune test (bdcaabb)
- Slope/offset layout rule; exact equality only (b9ac831)
- Add failing tests for the scaling warnings and context map installation (70ad26c)
- Scaling warnings and installable shared context maps (82275b8)

### Context maps

- Add failing tests for context map v3 value rules (698c7d9)
- Context map v3 value rules in brkraw.specs.context_map (6dc1571)
- Add failing tests for context map output and wiring (8a1745b)
- Context map output and wiring: layout_template, utils, collisions, split, --axis/--frames (de46ccd)
- Add failing tests for review fixes, MethodName and schema removal; xfail scaling repro (fd34392)
- Fix review findings; add MethodName; remove the old context map schema (5355f6a)
- Tests: the Method item without the vendor prefix is MethodBase (deae759)
- MethodBase: Method without the vendor prefix (51090fe)
- Add failing test: brkraw.api.layout is public (1150eed)
- Export brkraw.api.layout (config layout helpers) for the docs examples (1223b63)

### prune

- Add failing tests for prune fixes 1-5 and safe writing (1edd835)
- Fix prune defects 1-5 and write zips safely (7e5f2ad)
- Add failing tests for the prune 0.6.0 design (8ffffe3)
- prune 0.6.0: whole-study copy by default, --files/--exclude-files, --institution, --anonymize example spec (04c5e0e)
- Add failing test: an --anonymize copy must load study info (e451357)
- unixtime_to_datetime returns None for a missing value (3dd14f3)
- Add failing tests: a pruner spec can declare anonymize: true (db987ae)
- Pruner spec key anonymize: true — a custom anonymizing spec names output and record like --anonymize (1e3a121)

### Command line

- Parse list/tuple hook args from CLI (1bedefb)
- Organize convert options by workflow (7d49e5f)
- Group CLI help output by workflow category (79dc2cc)
- Add failing tests for the common CLI changes (1aef5e3)
- Common CLI changes: ParaVision chooser, --root everywhere, convert --batch, init only (a430405)
- Add failing tests: BIDS docs example, config path pruner_specs, api layout example (17e66ac)
- config path: add pruner_specs (30e58c8)
- Tests first: CLI behaviour for rc1 (be7a2b1)
- init --yes leaves shell files alone, params prints to stdout, one scan-id rule, convert takes several scans with a pre-check (deea079)
- Tests first: help wording and -r without -s naming skipped scans (401d8ee)
- Next steps at the end of brkraw -h, one command table, Commands title, addon/hook help and docs; -r without -s names the skipped scans (a2b2af7)
- Test fix: plugins come after the core commands, other installed plugins may follow too (c77db3b)

### Documentation

- Update Zenodo DOI badge (f35a537)
- ci: disabled automatic zenodo badge repleacing (69b393b)
- Add warning to context-map doc (2689553)
- docs: clarify viewer extension boundaries (ca58782)
- Docs for 0.6.0: context maps v3, BIDS example, prune, pruner specs, migration guide (8e55650)
- Docs: remove the two merged overview pages; installable base context maps, include lookup order, new warnings (db8154d)

### Development and tests

- test: cover core extension contracts (f7dd331)
- chore: ignore local agent guidance files (aa088b7)
- Manage the development environment with uv (tracked uv.lock, Python 3.12) (8479318)
- Add failing tests for the shared test base (376146d)
- Isolate tests from local settings; add agent-fixture lookup, synthetic PvDataset builder and docs build check (4d3ee58)
