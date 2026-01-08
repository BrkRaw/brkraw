# Converter hook packages (overview)

Converter hook packages are Python distributions that extend BrkRaw's
conversion pipeline (data loading/affine/conversion) while reusing the existing
metadata, layout, and sidecar infrastructure.

They are the recommended mechanism when you need sequence-specific conversion
logic that should not live in the core project.

## Relationship to addons

- Addons (rules/specs/transforms) provide case-dependent customization.
- Hook packages provide new conversion behavior and may optionally ship addon
  assets via a manifest.

## Developer guide

For authoring, packaging, and manifests, see `docs/dev/hook-packages.md`.
