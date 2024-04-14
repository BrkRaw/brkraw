"""
dependency:
    bids, plugin
"""
import argparse
from brkraw import __version__
from .loader import Loader

__all__ = [Loader]

def load(*args, **kwargs):
    """Load data in Facade design pattern
    """
    Loader()

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

    # tonii
    scan.add_argument("input", help=input_str, type=str)
    scan.add_argument("-b", "--bids", help=bids_opt, action='store_true')
    scan.add_argument("-o", "--output", help=output_fnm_str, type=str, default=False)
    scan.add_argument("-s", "--scanid", help="Scan ID, option to specify a particular scan to convert.", type=str)
    scan.add_argument("-r", "--recoid", help="RECO ID (default=1), "
                                            "option to specify a particular reconstruction id to convert",
                     type=int, default=1)
    scan.add_argument("-t", "--subjecttype", help="override subject type in case the original setting was not properly set." + \
                     "available options are (Biped, Quadruped, Phantom, Other, OtherAnimal)", type=str, default=None)
    scan.add_argument("-p", "--position", help="override position information in case the original setting was not properly input." + \
                     "the position variable can be defiend as <BodyPart>_<Side>, " + \
                     "available BodyParts are (Head, Foot, Tail) and sides are (Supine, Prone, Left, Right). (e.g. Head_Supine)", type=str, default=None)
    scan.add_argument("--ignore-slope", help='remove slope value from header', action='store_true')
    scan.add_argument("--ignore-offset", help='remove offset value from header', action='store_true')
    scan.add_argument("--ignore-rescale", help='remove slope and offset values from header', action='store_true')
    scan.add_argument("--ignore-localizer", help='ignore the scan if it is localizer', action='store_true', default=True)

    # tonii_all
    dataset.add_argument("input", help=input_dir_str, type=str)
    dataset.add_argument("-o", "--output", help=output_dir_str, type=str)
    dataset.add_argument("-b", "--bids", help=bids_opt, action='store_true')
    dataset.add_argument("-t", "--subjecttype", help="override subject type in case the original setting was not properly set." + \
                     "available options are (Biped, Quadruped, Phantom, Other, OtherAnimal)", type=str, default=None)
    dataset.add_argument("-p", "--position", help="override position information in case the original setting was not properly input." + \
                     "the position variable can be defiend as <BodyPart>_<Side>, " + \
                     "available BodyParts are (Head, Foot, Tail) and sides are (Supine, Prone, Left, Right). (e.g. Head_Supine)", type=str, default=None)
    dataset.add_argument("--ignore-slope", help='remove slope value from header', action='store_true')
    dataset.add_argument("--ignore-offset", help='remove offset value from header', action='store_true')
    dataset.add_argument("--ignore-rescale", help='remove slope and offset values from header', action='store_true')
    dataset.add_argument("--ignore-localizer", help='ignore the scan if it is localizer', action='store_true')

if __name__ == '__main__':
    main()