# Configuration basics

BrkRaw uses a user-level configuration directory to control output
naming, layout behavior, logging, and installed extensions.

Most users only need to adjust a small subset of configuration options
to be productive. This page focuses on those commonly used settings.

---

## Config location

By default, BrkRaw stores configuration under:

```text
~/.brkraw
```

You can override this location by setting:

```bash
BRKRAW_CONFIG_HOME=/path/to/config
```

The main configuration file is `config.yaml`.

It is created automatically by:

```bash
brkraw init
```

---

## What you may want to customize first

### 1. Output naming and layout

BrkRaw does not hard-code output filenames. Instead, filenames are
generated from metadata using configurable layout rules.

The most commonly adjusted settings live under:

```text
output.layout_entries
output.layout_template
```

Typical reasons to edit layout settings:

- Match an existing lab naming convention
- Include or hide protocol names
- Separate outputs by subject or session
- Shorten long protocol strings

Most users start with `layout_entries` and leave
`layout_template` unset.

---

### 2. Logging verbosity

To see more details about what BrkRaw is doing, increase the logging
level:

```yaml
logging.level: DEBUG
```

This is useful when debugging rules, specs, or hooks.

---

### 3. Table formatting

If CLI tables wrap badly on your terminal, adjust:

```text
logging.print_width
```

This affects commands such as `brkraw info` and `brkraw hook list`.

---

### 4. Floating-point formatting

BrkRaw rounds floating-point values when displaying metadata and
derived outputs.

You can control this via:

```text
output.float_decimals
```

This is mainly a display preference.

---

## Multi-slicepack outputs

Some scans produce multiple slice packs. In this case, BrkRaw appends
a suffix to distinguish outputs.

The default behavior can be customized via:

```text
output.slicepack_suffix
```

Most users should keep the default. Advanced users may include
orientation labels or other metadata.

---

## Common layout patterns

Below are three example layout patterns that reflect common
research workflows.

These examples are starting points, not fixed standards.

---

### Minimal layout

A simple, compact naming scheme suitable for quick experiments or
temporary outputs.

```yaml
output:
  layout_entries:
    - key: Subject.ID
      entry: sub
    - key: ScanID
      entry: scan
```

Produces filenames such as:

```text
sub-01_scan-3.nii.gz
```

---

### Lab-style layout

A more descriptive layout that includes session and protocol
information, commonly used in lab-managed datasets.

```yaml
output:
  layout_entries:
    - key: Subject.ID
      entry: sub
      sep: "/"
    - key: Session.ID
      entry: ses
      sep: "/"
    - key: ScanID
      entry: scan
    - key: Protocol
      hide: true
```

Produces paths such as:

```text
sub-01/ses-1/scan-3_T2w.nii.gz
```

---

### BIDS-like layout (informal)

A layout that resembles BIDS naming, useful for inspection or
preparation, but not intended as a full BIDS implementation.

```yaml
output:
  layout_entries:
    - key: Subject.ID
      entry: sub
      sep: "/"
    - key: Session.ID
      entry: ses
      sep: "/"
    - key: Modality
      hide: true
    - key: ScanID
      entry: scan
```

Produces paths such as:

```text
sub-01/ses-1/anat_scan-3.nii.gz
```

Important notes:

- This layout is **not BIDS-compliant by itself**.
- scan_id-based naming is often insufficient for BIDS.
- Modality-aware and project-specific mapping is required for
  correct BIDS organization.

---

## Future direction: brkraw-bids

BrkRaw intentionally avoids hard-coding BIDS logic into the core.

More advanced organization tasks, such as:

- Modality-aware naming
- scan_id to BIDS entity mapping
- Project- or study-specific conventions
- Dataset-wide validation and restructuring

are planned to be handled by a dedicated tool:

```text
brkraw-bids
```

This separation keeps BrkRaw focused on reliable data access,
metadata normalization, and extensible conversion, while allowing
BIDS-specific logic to evolve independently.

---

## Installed extensions and files

The configuration directory also contains subdirectories for
extensions:

```text
rules/
specs/
pruner_specs/
transforms/
```

These are populated automatically when you install addons or hooks.
Most users should not edit these files manually.

---

## Stability and future changes

The configuration schema may evolve over time.

- `config_version` is managed internally and should not be edited.
- New configuration keys may be added in future releases.
- Existing keys may gain new optional fields.

For authoritative details, refer to the Configuration Reference
section of the documentation.

---

## Next steps

- To explore all available configuration options, see the full
  Configuration Reference.
- To edit configuration interactively, run:

```bash
brkraw config edit
```
