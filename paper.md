---
title: 'BrkRaw: Comprehensive tool to handle Bruker PV dataset'
tags:
  - Preclinical MRI converter
  - Bruker
  - Python API
  - Command-line tool
  - BIDS
authors:
  - name: Sung-Ho Lee
    orcid: 0000-0001-5292-0747
    affiliation: "1, 2, 3"
  - name: Woomi Ban
    affiliation: "1, 3"
affiliations:
 - name: Center for Animal MRI, University of North Carolina at Chapel Hill
   index: 1
 - name: Department of Neurology, University of North Carolina at Chapel Hill
   index: 2
 - name: Biomedical Research Imaging Center(BRIC), University of North Carolina at Chapel Hill 
   index: 3
date: 22 April 2020
bibliography: paper.bib
---

# Summary


While the Bruker MRI scanner has been widely used for preclinical MR imaging research, 
the direct accessibility of Bruker's raw dataset is poor compared to the clinical MRI scanner due to the limited resource to handle the format.
So far, several Bruker raw data converter had been introduced, still, a few issues remain.
1. The converted data does not preserve the original subject orientation, as well as the subject type-specific position.
2. Lack of a robust tool to handle and preview of raw dataset.

To improve these issues, **BrkRaw** module is designed to provide comprehensive access to the Bruker's PVdataset.
We focused on providing useful features for Bruker MRI operator and preclinical MRI researcher via below functions
- preserving the subject position and orientation to converted the NifTi1 file.
- correction of animal orientation based on the species and position.
- providing the GUI tool for preview the dataset and NifTi1 format conversion.
- the command-line tool for converting to NifTi1 format, previewing metadata of the dataset, checking backup status.
- providing fMRI and DTI study friendly features: slice-order update on the header, Diffusion parameter file generation.
- BIDS(v1.2.2) support: parameter file generation, automatic generation of the folder structure.
- Object-oriented robust dataset parser.
- compressed data readability (compatible with .zip and .PVdatasets format).
- providing robust and easy-to-use python API for developers, including JCAMP-DX parser.
- the python API also providing data handler object through either nibabel and simpleITK to make convenient to the researcher can implement their own code.  

The forces on stars, galaxies, and dark matter under external gravitational
fields lead to the dynamical evolution of structures in the universe. The orbits
of these bodies are therefore key to understanding the formation, history, and
future state of galaxies. The field of "galactic dynamics," which aims to model
the gravitating components of galaxies to study their structure and evolution,
is now well-established, commonly taught, and frequently used in astronomy.
Aside from toy problems and demonstrations, the majority of problems require
efficient numerical tools, many of which require the same base code (e.g., for
performing numerical orbit integration).

`Gala` is an Astropy-affiliated Python package for galactic dynamics. Python
enables wrapping low-level languages (e.g., C) for speed without losing
flexibility or ease-of-use in the user-interface. The API for `Gala` was
designed to provide a class-based and user-friendly interface to fast (C or
Cython-optimized) implementations of common operations such as gravitational
potential and force evaluation, orbit integration, dynamical transformations,
and chaos indicators for nonlinear dynamics. `Gala` also relies heavily on and
interfaces well with the implementations of physical units and astronomical
coordinate systems in the `Astropy` package [@astropy] (`astropy.units` and
`astropy.coordinates`).

`Gala` was designed to be used by both astronomical researchers and by
students in courses on gravitational dynamics or astronomy. It has already been
used in a number of scientific publications [@Pearson:2017] and has also been
used in graduate courses on Galactic dynamics to, e.g., provide interactive
visualizations of textbook material [@Binney:2008]. The combination of speed,
design, and support for Astropy functionality in `Gala` will enable exciting
scientific explorations of forthcoming data releases from the *Gaia* mission
[@gaia] by students and experts alike.

# Mathematics

Single dollars ($) are required for inline mathematics e.g. $f(x) = e^{\pi/x}$

Double dollars make self-standing equations:

$$\Theta(x) = \left\{\begin{array}{l}
0\textrm{ if } x < 0\cr
1\textrm{ else}
\end{array}\right.$$

You can also use plain \LaTeX for equations
\begin{equation}\label{eq:fourier}
\hat f(\omega) = \int_{-\infty}^{\infty} f(x) e^{i\omega x} dx
\end{equation}
and refer to \autoref{eq:fourier} from text.

# Citations

Citations to entries in paper.bib should be in
[rMarkdown](http://rmarkdown.rstudio.com/authoring_bibliographies_and_citations.html)
format.

If you want to cite a software repository URL (e.g. something on GitHub without a preferred
citation) then you can do it with the example BibTeX entry below for @fidgit.

For a quick reference, the following citation commands can be used:
- `@author:2001`  ->  "Author et al. (2001)"
- `[@author:2001]` -> "(Author et al., 2001)"
- `[@author1:2001; @author2:2001]` -> "(Author1 et al., 2001; Author2 et al., 2002)"

# Figures

Figures can be included like this:
![Caption for example figure.\label{fig:example}](figure.png)
and referenced from text using \autoref{fig:example}.

Fenced code blocks are rendered with syntax highlighting:
```python
for n in range(10):
    yield f(n)
```	

# Acknowledgements

We acknowledge contributions from Brigitta Sipocz, Syrtis Major, and Semyeong
Oh, and support from Kathryn Johnston during the genesis of this project.

# References