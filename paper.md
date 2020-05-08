---
title: 'BrkRaw: Comprehensive tool to handle Bruker PV dataset'
tags:
  - Preclinical MRI converter
  - Bruker
  - Python API
  - Command-line tool
  - BIDS
  - cross-platform
authors:
  - name: Sung-Ho Lee
    orcid: 0000-0001-5292-0747
    affiliation: "1, 2, 3"
  - name: Woomi Ban
    affiliation: "1, 3"
  - name: Yen-Yu Ian Shih
    affiliation: "1, 2, 3"
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
To access the raw Magnetic Resonance Imaging (MRI) data for research, 
it required data conversion from the vendor-specific to software compatible format.
Usually, this step takes an additional layer to convert it as DICOM, 
the standard imaging format in Medicine, which has the capability of covering 
a huge variety of Metadata that not really necessary to keep in the preclinical research field, 
which using the animal as a subject. In addition to this, the data structure 
of DICOM is not intuitive to understand, so that many software takes field-specific standard formats, 
such as NifTi and Analyze, that required additional layer of data conversion.

For the above reason, several researchers had developed Bruker raw to the NifTi or 
Analyze format converter[@Brett:2002; @Ferraris:2017; @Rorden:2018; @Chavarrias:2017]
to bypass this DICOM conversion step, but still, the converter does not take account too much on metadata access, 
especially the subject orientation profile, mostly due to the complex nature of the way that Paravision software, 
the user interface to control Bruker MRI scanner handling this information. 
So, most of the previous converter does not preserve the originate orientation and 
position of the subject in the scanner coordinate system.

![Figure 1. Example of converted image alignment on Fsleye.\label{fig:1}](imgs/brkraw_alignment.png)
**Fig.1** Example subject alignment shown on FSLeyes, the overlayed localizer image for each slice axis(gray) and a EPI image(red) are align in the same space while the preserve subject orientation (correct R-L, I-S, A-P on rodent)

To preserve the position and orientation information of raw data, as well as the metadata 
required to keep for the research, we developed a python module 'BrkRaw' as a comprehensive tool 
to access raw MRI data for the Bruker preclinical MRI scanner without losing position and orientation profile \autoref{fig:1}
Since the converter is the first layer to access raw data, we made more efforts 
to cover the needs from various type of user as much as possible, 
including MRI system operator, maintainer, MR sequence developer, imaging researcher, and data scientist.
Therefore, the module designed not only can be used for the NifTi converter, 
but also provides features, such as previewing, data archiving, Python data loader, 
and BIDS data organizer including JSON format Metadata parser using custom syntax.
The module is compatible with the ZIP file format so that no need to uncompress the file to access data.

The module provides cross-platform command-line tools for the above features as well as Python API 
so that it can be utilized for various purposes such as developing automate macro files to post-process 
and analyze the acquired image online, archiving raw data and backup file inspection and maintenance, 
and project-level multi dataset automatic conversion into BIDS. 
To provide more convenience on accessing the raw data during data analysis the BrkRaw python API will load 
the data as python object using either Nibabel or SimpleITK, which the two major IO modules widely utilizing 
in python medical imaging communities, that enable to avoid unnecessary file conversion.
In addition to this, the module provide some minor function for the neuroimaging research as follows.
1) For fMRI image, it preserves slice timing information in NifTi Header.
2) In order to reduce the size of the file, VisuCoreSlope and Offset parameter are used instead correcting it.
3) Provide function to extract diffuse direction as FSL format (bval, bvec, bmat).

Brkraw module is currently utilizing as a first-line tool in our group at The University of North Carolina at 
Chapel Hill for operating image acquisition core service as well as several on-going projects in our institute 
for analyzing neuroimaging data. We expect this tool can benefit other animal imaging research sites and researchers 
to reduce their burden on handling and management of Bruker raw datasets and further data organization 
for reproducible science. Future direction will be developing online python-based tool to perform quality control
and fMRI data analysis realtime, as well as the BIDS based automatic pipeline platform for neuroimaging data analysis.

# Figures


Fenced code blocks are rendered with syntax highlighting:
```python
for n in range(10):
    yield f(n)
```	

# Acknowledgements

We acknowledge contributions from Brigitta Sipocz, Syrtis Major, and Semyeong
Oh, and support from Kathryn Johnston during the genesis of this project.

# References