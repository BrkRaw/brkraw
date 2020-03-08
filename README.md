# Bruker PVdataset Loader and Converter
## Version: 0.1.0

The tools to convert Bruker raw to Nifti format.
This converter is optimized for PV 6.0.1, but also works with PV 5.1 (lower version was not fully tested)

### Features
- The orientation issues are corrected. This means the image in the same session will be aligned at the same space on scanner coordination system.
- Orientation correction for species (R-L, A-P, I-S is labelled based on the species brain position and orientation).
- For the position correction, currently only Head_Prone and Head_Supine is available.
- Zip file conversion (including .PVdatasets from transferred or achieved from PV 6.0.1)
- Summary print out
- automatic BIDS structure conversion (pynipt project)

### Future plan
- Meta data output (json for BIDS)           - soon
- GUI reader (Thumbnail viewer)              - when time is available
- BART converter integration (for ZTE image) - when time is available

### Requirements
- Linux or Mac OSX
- tested at Python 3.7.6 only, compatible issue with python 2.7

### Installation
```angular2html
pip install bruker
```

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

- If <reco id> is not provided, then default is 1

- To convert all raw data under the folder. This command will scan all folder under the parent folder and the derived file will be structured as BIDS
```angular2html
brkraw tonii_all <parent folder>
```