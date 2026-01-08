# Roadmap: Dataset-driven integration tests

This project currently has strong unit-tested coverage in core/dataclasses, but
end-to-end validation of `resolver/`, `apps/`, and `cli/` is limited by the need
for real Paravision datasets.

The goal of this roadmap is to add **dataset-driven integration tests** that
can run locally and in CI by downloading a canonical dataset bundle and
executing a detailed validation suite over every discovered study.

---

## Guiding principles

- Prefer **real data** over mocks for resolver/app behavior.
- Fail on **exceptions**, not on domain-specific `None` returns (unless the API
  contract says otherwise).
- Produce **structured logs/artifacts** per study/scan/reco so failures are easy
  to diagnose after CI runs.
- Keep tests configurable: fast subset locally, full suite in CI/nightly.
- Avoid new runtime dependencies unless required; keep optional extras behind
  `.[dev]` or `.[test]` if introduced.

---

## Dataset strategy

This test plan assumes **multiple datasets** are available to CI and local
developers, and that those datasets may be delivered via different mechanisms
(committed as pruned archives vs fetched from external links).

### Two contribution paths

There are two supported ways to contribute datasets used by integration tests.
Both paths are discoverable through the dataset registry (so CI and
`brkraw test` can run the same selection logic).

1) **PR a pruned dataset into `brkraw-dataset`** (the "hosted" path)
   - The dataset is a single archive produced by `brkraw prune`.
   - The manifest is a true *sidecar*: its filename must match the archive
     filename (same basename), for example:
     - `unc_camri_pv51_example_001.zip`
     - `unc_camri_pv51_example_001.yaml` (or `.yml`)
   - Add a registry entry in the same PR so CI can discover and select it.
   - Intended for small, sequence-focused, reviewable datasets.
   - Recommended size policy: keep each pruned dataset bundle **≤ 200 MB**.
   - Repository layout recommendation:
     - Store hosted datasets under a contributor-owned namespace folder, e.g.:
       `datasets/<contributor_slug>/<dataset_basename>.zip` and
       `datasets/<contributor_slug>/<dataset_basename>.yaml`.
     - Tests should treat the `dataset.yaml` derived from the sidecar as the
       source of truth for `dataset_id` and `version` (folder names are only for
       organization and ownership clarity).

2) **Register an external dataset link in a registry** (the "linked" path)
   - The dataset is not committed to the repo, but a pinned download source is
     registered so CI (and other institutions) can fetch it reproducibly.
   - Registry entries control which CI tier the dataset runs in.

### Canonical dataset repository

Notes:
- Canonical dataset repo: `https://github.com/BrkRaw/brkraw-dataset.git`
- Prefer Git LFS for hosted binary datasets when needed.
- The repo may be large; prefer caching and incremental fetch.

### Dataset registry and CI tiers

Maintain a registry (in `brkraw-dataset`) that lists datasets and how to fetch
them. Registry entries also control CI selection:

- `priority: true` → runs in `integration-small`
- `priority: false` → runs only in `integration-full` (scheduled/nightly)

Example registry entry (conceptual):

```yaml
datasets:
  - dataset_id: unc_camri_pv51_example_001
    priority: true
    source:
      type: local
      archive: datasets/shlee/unc_camri_pv51_example_001.zip
      manifest: datasets/shlee/unc_camri_pv51_example_001.yaml
      sha256: "<archive-hash>"
  - dataset_id: private_site_dataset_002
    priority: false
    source:
      type: http
      url: https://example.org/brkraw/private_site_dataset_002.tar.zst
      sha256: "<archive-hash>"
      extract: tar
      subdir: private_site_dataset_002
```

Acquisition logic should:

- Support `local` (use checked-in archive + verify `sha256`) and `http` (download
  + verify `sha256` + extract) at minimum.
- Produce a normalized on-disk layout: a single `BRKRAW_TEST_DATA_ROOT`
  containing one or more dataset roots with `dataset.yaml`.
- Cache by immutable identifiers:
  - `local`: cache key includes archive path + `sha256`
  - `http`: cache key includes URL + `sha256`
- Allow private sources via secrets (tokenized git URLs or authenticated
  downloads).

This makes integration tests reproducible regardless of whether data is stored
in Git or provided as an external download.

---

## Registry implementation (to build)

The dataset registry is a first-class component and needs implementation work
in both the dataset repo and BrkRaw:

- Registry format
  - Define a stable YAML schema for entries (`dataset_id`, `priority`, `source`,
    optional tags/metadata).
- Hosted datasets
  - Support entries that reference pruned archives stored in `brkraw-dataset`
    (recommended `source.type: local`).
- External datasets
  - Support `source.type: http` with `sha256` and extraction rules.
  - Support authenticated/private sources via CI secrets.
- Tooling
  - Add a small helper to:
    - load and validate the registry
    - resolve the selected dataset set (`--small/--full`, tags)
    - materialize datasets into `BRKRAW_TEST_DATA_ROOT`
    - emit a resolved list for test parametrization

This work is required before CI can reliably run `integration-small` vs
`integration-full` tiers using only the registry.

---

## Dataset governance (hosted vs linked)

Governance requirements should be proportional to how datasets are contributed.
This plan distinguishes:

- **Hosted datasets**: pruned archives submitted by PR to `brkraw-dataset`.
- **Linked datasets**: external datasets registered via the dataset registry.

The hosted path should remain lightweight so contributors can submit small
sequence-focused datasets without excessive paperwork, while still ensuring
legal clarity and CI reproducibility.

### Hosted datasets (PR to `brkraw-dataset`): required vs recommended

Required (must be provided in the sidecar manifest):

- Permission statement: contributor confirms they can distribute the pruned
  archive via the `brkraw-dataset` repository.
- License identifier (for the dataset bundle).
- Minimal attribution (at least names; ORCIDs optional).
- Paravision version (if known) and a short `notes` description.
- Privacy confirmation: de-identified / no PHI.
- Integrity pinning: a checksum for the archived bundle (recommended `sha256`).

Recommended (helps long-term maintenance, but not required for acceptance):

- Dataset-level `CITATION.cff` / `CITATION.md` content (or a pointer to a paper).
- Provenance fields (scanner/site, acquisition date range, etc.).
- `curation` details (which `brkraw prune` spec/version was used).

### Linked datasets (registry): required vs recommended

Required (must be present in the registry entry, and/or resolvable via a linked
manifest):

- Pinned source with immutable versioning:
  - `git`: commit SHA (preferred) or immutable tag
  - `http`: `sha256` of the downloaded archive
- License and attribution information (either embedded or via a stable link).
- Access method documented (public vs authenticated via CI secrets).

Recommended:

- Same provenance/curation/privacy fields as hosted datasets.
- Size/tier guidance so only representative subsets run in `integration-small`.

### Dataset manifest (YAML)

Use a single YAML manifest per dataset and keep its schema stable so CI can
validate it and so test runs can emit consistent per-dataset reports.

There are two representations:

- **Hosted (archive + sidecar in `brkraw-dataset`)**
  - The manifest is stored next to the pruned archive as a sidecar (same basename).
- **Materialized (directory under `BRKRAW_TEST_DATA_ROOT`)**
  - Acquisition tooling should write/copy a canonical `dataset.yaml` into the
    extracted dataset directory so tests can discover datasets uniformly.
  - For hosted archives, `dataset.yaml` is derived from the sidecar.

Naming rule:

- If the pruned dataset archive is `NAME.zip` (or `.tar.gz`, etc.), the manifest
  must be `NAME.yaml` (same basename).

Recommended minimal schema:

```yaml
dataset_id: unc_camri_pv51_example_001
version: 1

institution: Center for Animal MRI, UNC at Chapel Hill
authors:
  - name: Sung-Ho Lee
  - name: Yen-Yu Ian Shih
license: CC-BY-4.0

subject:
  species: rat
  strain: SD

paravision:
  version: "5.1"

scans:
  3:
    name: FLASH
    recos: [1]
  4:
    name: FieldMap
    recos: [1]

curation:
  tool: brkraw prune
  pruner_spec: deid_v1
  notes: Pruned from original export; removed non-essential/sensitive files.

privacy:
  deidentified: true
  notes: No PHI; JCAMP comments stripped where applicable.

artifacts:
  sha256: "<bundle-or-root-hash>"

notes: Paravision 5.1 example dataset
comments: Add any additional context if needed
```

Guidelines:

- `dataset_id` must be unique within the dataset set and stable over time.
- `version` should change when curated contents change (even if the source study
  is the same).
- `scans` keys should be scan ids as they appear in BrkRaw (`loader.avail`).
- Prefer structured `authors` entries so ORCIDs/affiliations can be added later.

### Manifest validation (in the dataset repo)

Add a lightweight validator to `brkraw-dataset` so PRs cannot introduce
incomplete/invalid manifests.

Minimum checks:

- For hosted datasets: archive + sidecar manifest basenames match
  (`NAME.*` + `NAME.yaml`/`NAME.yml`).
- Registry contains an entry for every hosted dataset bundle.
- required keys present (`dataset_id`, `license`, `paravision.version`, `scans`)
- scan ids are integers and scan entries include `name`
- `license` matches an allowlist (SPDX-like identifiers where possible)
- optional: verify `artifacts.sha256` matches the dataset root content

Implementation options (pick one):

- JSON Schema + `jsonschema` (already a dependency here; would be new there)
- Simple Python validator (no extra deps) run via `python -m` or pytest

### CI integration with manifests

Use manifests to drive the integration suite:

- discover dataset roots by locating `dataset.yaml`
- optionally select subsets by tags/fields (institution, paravision version, size)
- name artifacts using `dataset_id` rather than filesystem paths

### Using `brkraw prune` to curate datasets

Instead of committing raw exports directly, prefer a standardized pipeline:

1) Start from an original study export (kept outside the repo).
2) Use `brkraw prune` with a published pruner spec to:
   - drop sensitive files
   - rewrite/strip JCAMP comments when needed
   - normalize directory structure for test stability
3) Commit only the pruned output plus the dataset manifest/license/credit files.

This keeps the dataset repo smaller, consistent, and reviewable, while also
making the curation steps reproducible.

Open questions to settle for the dataset system:

- Where should pruner specs live (in `brkraw-dataset`, or bundled here under
  `docs/dev/` with a mirror copy in the dataset repo)?
- Do we enforce a single license for the entire dataset repo, or per-dataset?
- Do we require `CITATION.cff` at dataset-level, repo-level, or both?
- Where should the dataset registry live, and how are private download sources
  represented (secrets, presigned URLs, separate registry)?

---

## Test harness design

### Inputs

- `BRKRAW_TEST_DATA_ROOT`: directory containing one or more datasets (each
  dataset is expected to have a `dataset.yaml` when materialized).
- `BRKRAW_TEST_DATASET`: optional path to a single dataset (directory or archive).
- `BRKRAW_TEST_REGISTRY`: optional registry file path (for fetching/selecting datasets).
- `BRKRAW_TEST_INCLUDE_FID=1`: include FID-based resolvers (default off).
- `BRKRAW_TEST_MAX_STUDIES`, `BRKRAW_TEST_MAX_SCANS`, `BRKRAW_TEST_MAX_RECOS`:
  caps for local runs.

### Dataset and study discovery

Implement a discovery routine that:

1) identifies dataset roots (prefer `dataset.yaml` when available), then
2) discovers Paravision study roots under each dataset root.

Study discovery should:

- ignore hidden directories and common junk (`.git`, `.venv`, `__pycache__`, etc.)
- detect candidate studies based on Paravision directory structure heuristics
  (define explicit rules and keep them stable)
- deduplicate nested matches (prefer the shallowest valid root)

### Execution model

For each discovered study:

1) Load with `brkraw.load(...)` (or the lowest-level loader API that is stable).
2) Iterate scans and reconstructions:
   - determine `scan_id` list (from `loader.avail`)
   - determine `reco_id` list (from scan availability; include hook-specific
     `reco_id=None` cases when applicable)
3) Run a set of checks and log results.

### Logging/artifacts

Write machine-readable artifacts grouped by dataset and study, e.g.:

- `artifacts/<dataset_id>/<study_slug>/results.jsonl` (one line per check)
- `artifacts/<dataset_id>/<study_slug>/summary.json`
- `artifacts/<dataset_id>/<study_slug>/brkraw.log` (captured logs)

Each record should include at least:

- study path + derived identifier
- scan_id / reco_id (when applicable)
- component (`resolver.affine`, `resolver.nifti`, `apps.loader`, etc.)
- operation (`get_affine`, `get_metadata`, `convert`, ...)
- status (`ok`/`fail`)
- duration
- exception type/message/traceback when failing
- key result statistics when successful (e.g. affine shape, determinant,
  header fields, output object type)

---

## Proposed test suite (phased)

### Phase 1: Infrastructure + discovery

- Add `tests/integration/` with:
  - dataset discovery helper
  - pytest parametrization across studies
  - artifact/log writer utilities
- Add CI job skeleton (without enabling on PRs yet).

Deliverable:
- Running `pytest -m integration` locally against a dataset root produces
  artifacts and a clear summary.

### Phase 2: Resolver coverage (detailed)

Per scan/reco, validate that the following do not raise exceptions:

- `resolver.affine`:
  - compute requested affine spaces
  - log determinant/orthogonality checks and shape
- `resolver.shape`:
  - compute expected data shape and timing-related outputs
- `resolver.nifti`:
  - build NIfTI objects with header validation

Define stable expectations that do not require "golden" outputs, e.g.:

- affine is 4x4
- determinant not near zero
- voxel sizes are finite
- header qform/sform are present and consistent

Deliverable:
- A detailed per-study scan/reco report that flags anomalies and exceptions.

### Phase 3: Apps coverage

Validate high-level app behaviors against real datasets:

- `apps.loader`:
  - `get_scan`, `get_dataobj`, `get_affine`, `convert`, metadata access
- `apps.addon`:
  - load bundled/default addons
  - validate example specs/rules/transforms resolve
- `apps.hook`:
  - list/install/uninstall flows against a temporary config root
  - ensure hook manifest parsing and file installation paths are correct

Deliverable:
- Integration tests that exercise the public APIs without depending on CLI I/O.

### Phase 4: CLI smoke tests (minimal but real)

CLI is a thin frontend, so keep this to:

- `brkraw info` against one known dataset
- `brkraw convert` producing at least one `.nii`/`.nii.gz` in a temp directory
  (and optionally a sidecar JSON)
- addon/hook CLI commands against a temp config root for a known example addon/hook

Deliverable:
- A small number of CLI tests that catch packaging/argparse regressions.

### Phase 5: FID resolver (optional / gated)

FID reconstruction can be expensive and not universally needed.

- Default: excluded in CI and local runs.
- Opt-in: `BRKRAW_TEST_INCLUDE_FID=1` enables FID tests.
- Consider separating into a dedicated CI workflow or nightly job.

Deliverable:
- A gated suite that provides coverage without slowing default pipelines.

---

## CI plan (GitHub Actions)

### Jobs

- `unit` (PR): existing unit tests (fast, no dataset).
- `integration-small` (PR, optional): runs on a small, prioritized dataset subset.
- `integration-full` (scheduled/nightly): runs against the full registry validate set.

### Caching

- cache fetched datasets keyed by immutable identifiers from the registry:
  - hosted/local: archive path + `sha256`
  - http: URL + `sha256`
- cache Python deps via pip and the venv wheel cache.

### Artifacts

- always upload `artifacts/` when integration job fails.
- optionally upload on success in nightly runs for auditing.

---

## Open questions

- What is the stable heuristic for "Paravision study root" discovery?
- Which datasets are representative enough for PR-level checks?
- Should integration tests assert numerical ranges (tight) or only structural
  invariants (loose)?
- How do we handle known-bad datasets (xfail list vs allowlist)?

---

## Developer UX: `brkraw test` command

To make dataset-driven testing usable outside CI (for example, at different
institutions), add a first-party command:

```text
brkraw test
```

Goals:

- Run the same integration suite locally against:
  - a dataset root path, or
  - a registry entry (fetch + cache + run)
- Support tier selection (`--small` / `--full`) consistent with CI semantics.
- Support `--include-fid` opt-in for the expensive FID resolver suite.
- Write the same `artifacts/` outputs as CI for easy sharing and debugging.
