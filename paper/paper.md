---
title: 'BrkRaw: A comprehensive tool for accessing raw Bruker Biospin data'
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
    orcid: 0000-0001-6529-911X
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
Accessing and analyzing Magnetic Resonance Imaging (MRI) data required conversion from a hardware-specific format 
to one compatible with available analysis software. The Digital Imaging and Communications in Medicine (DICOM) 
is considered as an international standard for handling MRI data in the clinical field due to its flexibility 
to cover the broad range of information from various imaging modalities and patient information. On the other hand, 
the complex data structure and the inclusion of unnecessary metadata in DICOM decrease analysis efficiency 
on various imaging research when the patient-related metadata is not essential for the study. 
For this reason, image data formats with a more efficient structure capable of encompassing spatial and temporal 
in a single file, such as NifTi-1, ANALYZE, or NRRD file formats, are becoming the new standard of choice 
in many imaging research studies. Converting the raw data into DICOM format is still necessary for clinical research, 
since it is important to preserve the patient-related metadata coupled with the image data. 
However, the preclinical MRI research using laboratory animals or objects does not require the DICOM conversion step 
and is rather inefficient. 

Researchers have developed conversion software for Bruker Biospin (the leading preclinical MRI vendor), 
for converting raw data directly into a NIfTI or ANALYZE format 
[@Brett:2002; @Ferraris:2017; @Chavarrias:2017; @Rorden:2018] for improving efficiency for data processing.

Although the converters significantly improve analysis workflow by direct converting into software friendly file format,
the software introduced so far has not provided the convenience of using the data immediately without conversion.
Here we present the 'BrkRaw' python module, a more comprehensive preclinical tool for accessing and utilizing
raw Bruker Biospin MRI data. The module has built up using robust low-level Python Application Programming Interface 
(API) allowing direct raw data access without conversion to provide the advanced and easy-to-use features 
for data analysis. 

The current version of BrkRaw is composed of four components, the low-level Python API, the high-level Python API,
the command-line tools, and the graphical user interface (GUI). 

The low-level Python API provides a robust JCAMP-DX loader to convert parameter files embedded in raw data 
into a Python object and the raw Bruker data loader that converting a whole folder containing parameter and 
binary files of a single imaging study session into a Python object. We also designed the zip file to be loaded 
without extraction, considering the accessibility of the archived data.

For the high-level Python API, we focused on providing useful functions to reduce extra effort on converting data into 
a usable form. It preserves the coordinate system of the image according to the subject position and orientation 
 on the scanner coordinate system (Figure1), which is known to be a challenge in the Bruker Biospin MRI system.
[@Ferraris:2017, @Naveau:2019].
The high-level Python API offers to load image data as the two most convenient object types 
in the Python eco-system for image processing (nibabel[@Brett:2020] and SimpleITK[@Lowekamp:2013]), 
as well as to convert multiple parameters into a structured JSON-type object using a custom JSON-based syntax.

The BrkRaw modules provide two command-line tools, which mainly utilizing low- and high-level Python API for automating 
routine operation for data management, as well as data conversion. The 'brk-backup' used the direct accessibility 
of the archived file (zip compressed) to enable the validation of archived data compared to corresponding 
raw data without extraction. As a result, the command offers to automate the inspection of raw and archived data, 
archiving of missing or updated data and removing the broken or duplicated data (Figure2).

The 'brkraw' command, on the other hand, offers a useful function to check data information (Figure3) and 
to convert data into NifTi-1 format. In addition to this, the command provides automate conversion and organization 
of large datasets into a ready-to-share data structure, the Brain Imaging Data Structure (BIDS), 
a standard data structure for neuroimaging research proposed by the open science community 
for pursuing reproducible science [@Gorgolewski:2016] (Figure4).

Lastly, via 'brkraw gui' command, the GUI offers improved accessibility for previewing the image and parameters 
without conversion. The converting button will convert a previewing image into NifTi-1 format, 
so allow the user to visually check the image before conversion (Figure 5).  

This module has been actively utilized in the Center for Animal MRI (CAMRI) 
at the University of North Carolina at Chapel Hill for several on-going preclinical functional MRI studies, 
including sequence development and data management. We expect this tool to reduce the burden of handling, 
and management of raw Bruker MRI data, thereby benefitting other animal imaging researchers.
In the future we will develop additional Python-based tools for acute quality control and real-time fMRI data analysis.

# Figures
![Bruker2Nifti_QA](../../brkraw.github.io/imgs/bruker2nifti_qa.png)
**Figure 1. The overlapped converted images that shows successful conversion of Bruker2Nifti_QA dataset**

![Data management](../../brkraw.github.io/imgs/brk_backup.png)
**Figure 2. The main function of brk-backup command for data management**

![brkraw info](../../brkraw.github.io/imgs/brkraw_info.png)
**Figure 3. The example of brkraw command usage to print out data information** 

![BIDS convert](../../brkraw.github.io/imgs/brkraw_bids.png)
**Figure 4. The example usage of the command-line tool 'brkraw' for BIDS data organization.**

![brkraw GUI](../../brkraw.github.io/imgs/brkraw_gui.png)
**Figure 5. The graphical user interface (GUI) for previewing image and parameters**

# Acknowledgements

We thank to the researchers of the Rorden lab at the University of South Carolina, especially 
Drs. Chris Rorden and Sebastiano Ferraris, regarding their pioneer works that inspire us to start this project, 
as well as their support on sharing accumulated know-how. We also thank Dr. Mikael Naveau at Cyceron and 
Gabriel A. Devenyi at Douglas Mental Health University Institute who shared the dataset for benchmarking converter. 
Lastly, We thank to the staff and colleagues in the Center for Animal MRI (CAMRI) at the University 
of North Carolina at Chapel Hill for the testing and providing helpful feedback. Especially thanks to 
Ms. Tzu-Wen Wang for the test the data management tools and Ms. Alicia M. Stevans for the help of 
critical reading of the manuscript. This work was supported by NIH 
(Grant No: RF1MH117053, R01MH111429, and R01NS091236).

# References