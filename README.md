# Bruker PVdataset Loader and Converter
## Version: 0.1.0

The tools to convert Bruker raw to Nifti format.

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