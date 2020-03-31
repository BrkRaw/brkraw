#!/usr/scripts/env python

from .. import __version__
from ..lib.backup import BackupCacheHandler
import argparse
import datetime
import os


def main():
    parser = argparse.ArgumentParser(prog='brk-backup',
                                     description="Command line tool for Bruker rawdata backup")
    parser.add_argument("-v", "--version", action='version', version='%(prog)s v{}'.format(__version__))

    subparsers = parser.add_subparsers(title='Sub-commands',
                                       description='brk-backup provides convenient tool for backup rawdata',
                                       help='description',
                                       dest='function',
                                       metavar='command')

    scan = subparsers.add_parser("scan", help='Scan the backup status')
    scan.add_argument("raw_path", help="Folder location of the Bruker raw datasets", type=str)
    scan.add_argument("backup_path", help="Folder location of the backed-up datasets", type=str)

    report = subparsers.add_parser("report", help='Report the backup status')
    report.add_argument("raw_path", help="Folder location of the Bruker raw datasets", type=str)
    report.add_argument("backup_path", help="Folder location of the backed-up datasets", type=str)
    report.add_argument("-l", "--logging", help="option for logging output instead printing", action='store_true')

    clean = subparsers.add_parser("clean", help='Clean unnecessary archived dataset')
    clean.add_argument("raw_path", help="Folder location of the Bruker raw datasets", type=str)
    clean.add_argument("backup_path", help="Folder location of the backed-up datasets", type=str)

    now = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_fname = 'brk-backup_{}.log'.format(now)
    args = parser.parse_args()

    if args.function == 'scan':
        rpath = args.raw_path
        bpath = args.backup_path
        handler = BackupCacheHandler(raw_path=rpath, backup_path=bpath)
        handler.scan()

    elif args.function == 'report':
        rpath = args.raw_path
        bpath = args.backup_path
        handler = BackupCacheHandler(raw_path=rpath, backup_path=bpath)
        if args.logging:
            if os.path.exists(log_fname):
                with open(log_fname, 'a') as f:
                    handler.report(fobj=f)
            else:
                with open(log_fname, 'w') as f:
                    handler.report(fobj=f)
        else:
            handler.report()

    elif args.function == 'clean':
        rpath = args.raw_path
        bpath = args.backup_path
        handler = BackupCacheHandler(raw_path=rpath, backup_path=bpath)
        handler.clean()

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
