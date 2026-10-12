# Graphical User Interface

`brkraw-viewer` is the optional visualization application plugin for BrkRaw.
Its default interface lets you inspect raw images for QC without a prior
conversion step. It also hosts optional modality-specific visualization
extensions; BrkRaw core remains responsible for data loading and conversion.

The legacy GUI features that previously shipped with BrkRaw have been retired
and split into this separate module. Going forward, the GUI will evolve as an
independent, GUI-first ecosystem around BrkRaw.

The viewer is extensible through `brkraw.viewer.hook`, so hook packages can
introduce dedicated visualization panels. Shared display and interaction
behavior belongs in `brkraw-viewer`.

Current development focuses on:

- Improving the image viewer compared to earlier versions.
- Implementing orientation inspection and reorientation workflows.
- Bringing core capabilities that already exist in the CLI into the GUI.

Project links:

- [BrkRaw Viewer page](https://brkraw.github.io/brkraw-viewer)
- [GitHub repository](https://github.com/BrkRaw/brkraw-viewer)
