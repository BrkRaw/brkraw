# BrkRaw: Comprehensive tool to access Bruker PV dataset
## Version: 0.3

### Description

The 'BrkRaw' python module is designed to be a more comprehensive tool for the preclinical MRI community for accessing and 
utilizing raw data. And since the converter is front-line tools for medical imaging, the functionality is developed to cover 
the requirements from the various user, including MRI system operator, maintainer, MR sequence developer, imaging researcher, 
and data scientist. In addition to these, we had put extra efforts to preserve the metadata as well as provide tools to help 
organize the data structure into a shareable format that suggested from the open science community for pursuing 
reproducible science [BIDS](https://bids.neuroimaging.io). Therefore, the module designed not only can be used for the NifTi converter, 
but also provides command-line tools and python API for previewing, organizing and archiving data, and parsing metadata, 
accessing the data as users convenient object type ([nibabel](https://nipy.org/nibabel/) or 
[SimpleITK](https://simpleitk.readthedocs.io/en/master/gettingStarted.html#python-binary-files)) 
without the conversion step. The module is compatible with the ZIP file format, so no need to uncompress the file to access data.
including MRI system operator, maintainer, MR sequence developer, imaging researcher, and data scientist.
This module provides easy-to-access of the Bruker's PVdataset from PV 5 to PV 6.0.1 (it has not been tested for above versions)
The major features of this module as follows.

- Reliable converting function with
    - preserving the subject position and orientation to converted the NifTi1 file.
    - correction of animal orientation based on the species and position. (Anterior of subject is Anterior)
    - providing fMRI and DTI study friendly features: slice-order update on the header, Diffusion parameter file generation.
    - BIDS(v1.2.2) support: parameter file generation with custom syntax, automatic generation of the folder structure.
- Capability of quick image validation by
    - providing the GUI tool for preview the dataset without conversion.
    - the command-line tool function for previewing metadata of the dataset for each scan.
- Data management tool 'brk-backup'
    - Data management tool 'brk-backup' for archiving and performing inspection the backup status.
- Robust and easy-to-use python API for developers, including JCAMP-DX parser.
    - Object-oriented robust dataset parser.
    - compressed data readability (compatible with .zip and .PVdatasets format).
    - the python API also providing data handler object through either nibabel and simpleITK to make convenient to the researcher can implement their own code.  


![example_alignment](imgs/brkraw_alignment.png)
**Fig1.** Example subject alignment shown on FSLeyes, the overlayed localizer image for each slice axis(gray) and a EPI image(red) are align in the same space while the preserve subject orientation (correct R-L, I-S, A-P on rodent)

### Compatibility
- Cross-platform compatibility (OSX, Linux, Windows 10)
- Best work on Python 3.7.6, does not support Python 2.
- Dependency: numpy, pillow, nibabel, tqdm, simpleITK, pandas, openpyxl, xlrd, shleeh

### Installation
- We are highly suggesting to use **Python 3.7**

#### Requirement
- The installed Python must be compiled properly, If you use pyenv and are having any issue with python please refer following link: 
[Common Build Problems in PyENV](https://github.com/pyenv/pyenv/wiki/common-build-problems)
- To use gui feature, the installed python should compiled with tkinter module.
- You can test the tkinter installation with below command on your shell.
```angular2html
$ python -m tkinter -c 'tkinter._test()'
```

- In Mac OSX, Homebrew installed tcl-tk and pyenv may have an issue with tkinter, please refer following link to solve the issue:
[Issue with Homebrew installed tcl-tk on pyenv](https://github.com/pyenv/pyenv/issues/1375)

#### Install via PyPI
```angular2html
$ pip install bruker
```

#### Install via Github
```angular2html
$ pip install git+https://github.com/dvm-shlee/bruker
```

#### Known issues
- In most case, the issue will related to the pyenv build, please refer the above links to solve the issue.
- If you experience any other issue, please use 'issue' tab in Github to report.
- If the dataset contains MR Spectroscopy, some method not work properly (such as summary to print out meta data)
- The legacy module 'pyBruker' had issues at orientation in the data has oblique FOV. This module resolved most of the issue, but if you experiencing
that any modality image is incorrectly positioned compared with any other modality, please report use. (except the image required custom reconstruction) 

## Usage
### Command-line tool (brkraw)
#### Quick access of metadata
- Printing out dataset information
```angular2html
$ brkraw summary <session path or compressed dataset>
```
![brkraw summary](imgs/brkraw_print_summary.png)
**Example of printed out dataset information**

#### Legacy converting to NifTi1 format
- Convert a whole session, (adding option '-b' or '--bids' will generate JSON file that contains MR parameters based-on BIDS standard)
```angular2html
$ brkraw tonii <session path or compressed dataset>
```

- Convert a scan, (default reco_id is 1)
```angular2html
$ brkraw tonii <session path or compressed dataset> -s <scan id> -r <reco id>
```

- Build BIDS dataset with multiple Bruker raw datasets.
- Required to copy the datasets into the parent folder.
- All dataset under parent folder will be converted into ./Data folder with BIDS
```angular2html
$ brkraw tonii_all <parent folder>
```

#### Automatic BIDS organizer with template files
![brkraw bids](imgs/brkraw_bids_conv.png)
**The usage of the command-line tool 'brkraw' for BIDS data organization.**

- Upgraded feature to reduce burden on renaming according to BIDS standard.
- Create BIDS file table with excel format to rename the file accordingly for BIDS standard.
- If you need to crop data, you can also specify its range on excel file for each scan.
- This will return also the BIDS_META_REF.json which allows you to input the template of BIDS json parser syntax
- To learn more detail, please check our example Jupyter Notebook.
```angular2html
$ brkraw bids_list <parent folder> <filname>.xlsx
```

- Build BIDS dataset according to the excel file generated with 'bids_list' command above.
```angular2html
$ brkraw bids_converter <parent folder> <BIDS table file.xlsx>

$ brkraw bids_converter <parent folder> <BIDS table file.xlsx> -r <BIDS meta reference file.json>
```

![brkraw summary](imgs/brkraw_bids.png)
**Example of automatically generated BIDS dataset**

- Run GUI with input and output path
```angular2html
$ brkraw gui -i <session path> -o <output path>
```
![brkraw GUI](imgs/brkraw_gui.png)
**brkraw gui interface.**

- Run GUI without path, make sure you select correct button based on the dataset type (file or folder)
- In case of loading folder, you need to enter to the folder instead of just selecting it.
```angular2html
$ brkraw gui
```

### Data management tool
![brk-backup](imgs/brk_backup.png)
**brk-backup script utilizing the Python API to immediately access both raw data and archived data 
to parse the metadata for data management.**

- Print out archived dataset and condition
```angular2html
$ brk-backup archived <rawdata path> <backup path>
```

- Generate log file of review archived dataset and condition
```angular2html
$ brk-backup archived <rawdata path> <backup path> -l
```

- Print out review backup status
```angular2html
$ brk-backup review <rawdata path> <backup path>
```

- Generate log file of review backup status
```angular2html
$ brk-backup review <rawdata path> <backup path> -l
```

- Run interactive archived dataset cleaning helper tool
```angular2html
$ brk-backup clean <rawdata path> <backup path> -l
```

#### Windows 10
- Same as above, but use brkraw.exe instead of brkraw command.
- If this command is not working, please check the version of your Anaconda and Python.

#### Python API
- To learn more detail, please check the Jupyter notebook in 'examples' folder

- import module
```angular2html
>>> import brkraw
```

- load dataset
```angular2html
>>> rawdata = brkraw.load(<PATH>)
```

- For more detail, Please check Jupyter Notebooks in the example directory.

### Contributing
- Please contact shlee@unc.edu if you interest to contribute for following items.
1. integration of reconstruction tool with Python API (such as BART tool).
2. develop online analysis tools for fMRI or DTI study.
3. Documentation or develop tutorials for various use.
- Also if you experience any bug or have any suggestion to improve this tool, please let us know.

### Credits:
- SungHo Lee (shlee@unc.edu)
- Woomi Ban (banwoomi@unc.edu)

### License:
GNU General Public License v3.0
