"""provide all conventional function with backward compatibility, but also provide function to send file via FTP server
as well as compress only file needed
"""

import argparse
from brkraw import __version__

def main():
    """main script allows convert brkraw
    provide list function of all available converting mode (including plugin)
    """
    parser = argparse.ArgumentParser(prog='brk_tonifti',
                                     description="BrkRaw command-line interface for NifTi conversion")
    parser.add_argument("-v", "--version", action='version', version='%(prog)s v{}'.format(__version__))

    subparsers = parser.add_subparsers(title='Sub-commands',
                                       description='To run this command, you must specify one of the functions listed'
                                                   'below next to the command. For more information on each function, '
                                                   'use -h next to the function name to call help document.',
                                       help='description',
                                       dest='function',
                                       metavar='command')

    input_str = "input raw Bruker data"
    input_dir_str = "input directory that contains multiple raw Bruker data"
    output_dir_str = "output directory name"
    output_fnm_str = "output filename"
    bids_opt = "create a JSON file contains metadata based on BIDS recommendation"

    info = subparsers.add_parser("info", help='Prints out the information of the internal contents in Bruker raw data')
    
    scan = subparsers.add_parser("scan", help='Convert a single raw Bruker data into NifTi file(s)')
    study = subparsers.add_parser("study", help="Convert All raw Bruker data located in the input directory")
    dataset = subparsers.add_parser("dataset", help="Convert All raw Bruker data located in the input directory")

    # info
    info.add_argument("input", help=input_str, type=str)
    
    
if __name__ == '__main__':
    main()