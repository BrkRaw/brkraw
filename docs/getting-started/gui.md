# Graphical User Interface

`brkraw-viewer` is an optional GUI extension that plugs into BrkRaw to provide
interactive tools for raw-data workflows. Its primary goal is to let you
quickly inspect raw data images for QC without requiring a prior conversion
step.

The legacy GUI features that previously shipped with BrkRaw have been retired
and split into this separate module. Going forward, the GUI will evolve as an
independent, GUI-first ecosystem around BrkRaw.

The viewer is built to be extensible through the BrkRaw hook system, so hook
packages can introduce dedicated GUI extensions and deliver modality-specific
QC experiences.

Current development focuses on:

- Improving the image viewer compared to earlier versions.
- Implementing orientation inspection and reorientation workflows.
- Bringing core capabilities that already exist in the CLI into the GUI.

Project links:

- [BrkRaw Viewer page](https://brkraw.github.io/brkraw-viewer)
- [GitHub repository](https://github.com/BrkRaw/brkraw-viewer)
