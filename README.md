# Bruker PVdataset Loader and Converter
## Version: 0.1.0

The tools to convert Bruker raw to Nifti format.
This converter is optimized for PV 6.0.1, but also works with PV 5.1 (lower version was not fully tested)

### Features
- The object parting almost all parameter as python friendly datatype (which help to use it to apply custom reconstruction tool such as BART)
- The orientation issues are corrected. This means the image in the same session will be aligned at the same space on scanner coordination system. (Please report and provide the dataset if you have any issue regarding the orientation.)
- Orientation correction for species (R-L, A-P, I-S is labelled based on the species brain position and orientation).
- For the position correction, currently only Head_Prone and Head_Supine are available.
- Data slope and offset are applied on nifti header - dataobj will be 16bit integer for most case that help saving the storage
- Zip file conversion (including .PVdatasets from transferred or achieved from PV 6.0.1)
- Summary print out
- Automatic BIDS structure conversion (pynipt project)

### Future plan
- Documentation
- Complete the all case of position based orientation correction (Head_left, Head_right, Foot_....) - when my time is available
- Meta data output (json for BIDS)           - soon
- GUI reader (Thumbnail viewer)              - when my time is available
- BART integration (for ZTE image)           - when my time is available

### Requirements
- Linux or Mac OSX
- tested at Python 3.7.6 only, compatible issue with python 2.7 (due to the re module, no plan for backward compatibility)

### Installation
```angular2html
pip install bruker
```

### Contribute
- please contact me (shlee@unc.edu)

### Command line tool
- Help function
```angular2html
brkraw -h
```

- Print out summary of the scan
```angular2html
brkraw summary <session path>
```

- Convert a whole session
```angular2html
brkraw tonii <session path>
```

- Convert only one scan in the session
```angular2html
brkraw tonii <session path> -s <scan id> -r <reco id>
```

- If reco_id is not provided, then default is 1

- To convert all raw data under the folder. This command will scan all folder under the parent folder and the derived file will be structured as BIDS
```angular2html
brkraw tonii_all <parent folder>
```