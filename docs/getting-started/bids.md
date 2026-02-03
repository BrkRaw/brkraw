# BIDS integration (current guidance)

Earlier versions of BrkRaw provided more direct support for BIDS-style workflows,  
and these features were actively used by many users. However, as the BIDS  
specification has rapidly expanded and evolved, maintaining a fully compliant  
BIDS implementation directly within the BrkRaw core became increasingly difficult.

As a result, BrkRaw has shifted toward an extensible, framework-based design,  
rather than hard-coding BIDS logic into the core.

In the current architecture, BIDS-related behavior is conceptually expressed  
through a layered workflow:

- **Rules** select modality-specific logic, metadata specs, and hooks.  
- **Specs** map Bruker ParaVision parameters into normalized metadata fields.  
- **Context maps** normalize subject, session, and scan-level identifiers at runtime.  
- **Output layouts** render structured file paths and filenames.

This rule–spec–context–layout workflow forms the architectural foundation for  
future BIDS-oriented extensions.

---

## Practical guidance (recommended usage)

While the framework above is flexible, it is **not intended for general users**  
to construct fully BIDS-compliant datasets at this stage. In addition, parts of  
the BrkRaw core - particularly **context mapping** and **output layout handling**  
- may continue to evolve.

For now, BIDS-related usage of BrkRaw is recommended in the following, limited scope:

- Generating metadata sidecars via **metadata specs**  
- Producing **BIDS-like directory structures** using output layout templates

These outputs are suitable for inspection, preparation, or downstream processing,  
but **should not be considered strictly BIDS-compliant datasets**.

---

## BIDS-like layout example (informal)

You can approximate a BIDS-like directory structure using output layout  
configuration. This is useful for inspection or early-stage preparation,  
but it does not replace a full BIDS implementation.

Example layout configuration:

```yaml
output:
  layout_entries:
    - key: Subject.ID
      entry: sub
      sep: "/"
    - key: Session.ID
      entry: ses
      sep: "/"
    - key: Subject.ID
      entry: sub
    - key: Session.ID
      entry: ses
    - key: Modality
      hide: true
    - key: ScanID
      entry: scan
```

This configuration produces paths such as:

```text
sub-01/ses-1/sub-01_ses-1_anat_scan-3.nii.gz
```

Important notes:

- This layout is **not BIDS-compliant by itself**.  
- Scan-ID-based naming is often insufficient for BIDS.  
- Correct BIDS organization requires modality-aware and project-specific mapping.

---

## Metadata specs and current defaults

The metadata specs installed via `brkraw init` are **not a frozen BIDS standard**.  
Because the official BIDS specification continues to evolve, BrkRaw does not  
attempt to track all BIDS updates directly within the core package.

Instead, future BIDS-aligned metadata specs are expected to be provided through:

- Dedicated extension packages  
- Modality-specific hooks

At present, the default metadata specs distributed with BrkRaw generate sidecar  
metadata based on the **DICOM metadata definitions provided in the Bruker  
ParaVision manual**, rather than the full BIDS specification.

---

## Future direction: brkraw-bids

BrkRaw intentionally avoids embedding BIDS logic directly into the core.

More advanced and BIDS-specific tasks - such as:

- Modality-aware naming and entity resolution  
- Scan-level to BIDS-entity mapping  
- Project- or study-specific conventions  
- Dataset-wide validation and restructuring

are planned to be handled by a dedicated tool:

```text
brkraw-bids
```

This separation keeps BrkRaw focused on reliable data access, metadata normalization,  
and extensible conversion, while allowing BIDS-specific logic to evolve independently.

---

## References

- Rules for modality-specific selection: [Rule syntax](../extensions/rules.md)  
- Specs for `info_spec` and `metadata_spec`: [Spec syntax](../extensions/specs.md)  
- Context maps for runtime remapping: [Context map syntax](../extensions/context-map.md)  
- Layout rules for directory structure and naming: [Layout and naming](../extensions/layout.md)
