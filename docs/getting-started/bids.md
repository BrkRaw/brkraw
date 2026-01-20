# BIDS integration (early guidance)

BrkRaw will provide a more direct BIDS interface as an extension in a future
release. For now, BIDS-style workflows are built by combining the existing
extensibility layers.

Example workflow (short):

- Rules select modality-specific info/metadata specs and hooks.
- Specs map Bruker params into BIDS-facing fields for `info` and sidecars.
- Context maps normalize subject/session names and per-scan metadata.
- Layout renders BIDS-style paths with `run-{Counter}` when needed.

Use these references as the current integration path:

- Rules for modality-specific selection: [Rule syntax](../reference/rules.md)
- Specs for `info_spec` and `metadata_spec`: [Spec syntax](../reference/specs.md)
- Context maps for runtime remapping: [Context map syntax](../reference/context-map.md)
- Layout rules for BIDS paths and `run-{Counter}`: [Layout and naming](../reference/layout.md)
