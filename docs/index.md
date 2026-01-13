# A modular toolkit for Bruker MRI raw-data handling.

Documentation for BrkRaw.

BrkRaw is a toolkit for loading Bruker Paravision MRI studies, inspecting and
normalizing metadata, mapping parameters through rule and spec systems, and
exporting data to NIfTI with optional sidecar metadata.

It provides both a CLI and a Python API, and is designed to be extended through
add-on rules, specs, and converter plugins.

---

## Highlights

- Load Bruker Paravision datasets from directories, zip archives, or
  Paravision-exported `.PvDatasets` files
- Inspect study, scan, and reconstruction metadata via rich CLI tables
- Map parameters using rule-based selection and remapper specs
- Convert scans to NIfTI with configurable layout entries and templates
- Extend conversion behavior via rules, specs, and converter hooks

---

## Supported scope and limitations

BrkRaw focuses on **preclinical MRI datasets acquired with Bruker Paravision**.
The current scope is intentionally constrained to ensure correctness and
reproducibility.

### Supported

- Bruker Paravision datasets (PV5, PV6, PV7, PV360)
- Paravision-exported `.PvDatasets` archives
- Preclinical MRI acquisitions (2D and 3D)
- Multiple reconstructions (`reco_id`) per scan
- Multi-slicepack acquisitions
  (exported as separate outputs with suffixes)
- Loading from directory trees, zip archives, or `.PvDatasets` files
- Export to NIfTI with optional JSON sidecar metadata

### Tested Paravision versions

BrkRaw has been validated using **Bruker Paravision standard datasets**
exported from the following versions:

- Paravision **PV 360.3.5 - 360.3.7**

Standard dataset definitions are based on Bruker documentation:
<https://www.bruker.com/en/products-and-solutions/preclinical-mri/paravision>

Support for other Paravision versions may work but has not been
systematically validated.

### Not in scope / limitations

- Clinical DICOM datasets
- Automatic DICOM-to-NIfTI conversion
- Vendor-agnostic MRI pipelines
- Full BIDS compliance without user-provided rules or specs
- Interactive visualization (handled by external viewers)

BrkRaw intentionally separates **data interpretation** from
**conversion rules**. Users are expected to encode project- or
modality-specific logic through rules, specs, or extensions rather
than hard-coded heuristics.

---

## Ecosystem and extensions

BrkRaw is designed as a **core engine** with a growing ecosystem of
extensions and supporting tools.

### Official resources

- BrkRaw organization page  
  <https://brkraw.github.io>

- Jupyter notebook tutorials  
  <https://github.com/BrkRaw/brkraw-tutorial>

### Converter and UI extensions

- **brkraw-mrs**  
  MRS (Magnetic Resonance Spectroscopy) support via converter hook  
  <https://github.com/BrkRaw/brkraw-mrs>

- **brkraw-viewer**  
  Support plugin for orientation QC/reorientation, metadata/spec utilities, naming-policy tests, and config editing  
  <https://github.com/BrkRaw/brkraw-viewer>

### Extension templates

- **brkraw-cli**  
  Template repository for building BrkRaw CLI extensions  
  <https://github.com/BrkRaw/brkraw-cli>

- **brkraw-hook**  
  Public template for implementing converter hooks  
  <https://github.com/BrkRaw/brkraw-hook>
