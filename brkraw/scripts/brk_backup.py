# -*- coding: utf-8 -*-
from .. import __version__
from ..lib.backup import BackupCacheHandler
import argparse
import datetime


def main():
    parser = argparse.ArgumentParser(prog='brk-backup',
                                     description="Command line tool for archiving Bruker dataset.")
    parser.add_argument("-v", "--version", action='version', version='%(prog)s v{}'.format(__version__))

    subparsers = parser.add_subparsers(title='Sub-commands',
                                       description='brk-backup provides convenient tool '
                                                   'for archiving and check the status.',
                                       help='description',
                                       dest='function',
                                       metavar='command')

    raw_path_str = "Folder location of the Bruker raw dataset"
    arc_path_str = "Folder location of the archived dataset"

    archived = subparsers.add_parser("archived", help='Scan the backup status')
    archived.add_argument("raw_path", help=raw_path_str, type=str)
    archived.add_argument("archived_path", help=arc_path_str, type=str)
    archived.add_argument("-l", "--logging", help="option for logging output instead printing", action='store_true')

    review = subparsers.add_parser("review", help='Report the backup status')
    review.add_argument("raw_path", help=raw_path_str, type=str)
    review.add_argument("archived_path", help=arc_path_str, type=str)
    review.add_argument("-l", "--logging", help="option for logging output instead printing", action='store_true')

    clean = subparsers.add_parser("clean", help='Clean unnecessary archived dataset')
    clean.add_argument("raw_path", help=raw_path_str, type=str)
    clean.add_argument("archived_path", help=arc_path_str, type=str)

    now = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_fname = 'brk-backup_{}.log'.format(now)
    lst_fname = 'brk-backup_archived_{}.log'.format(now)
    args = parser.parse_args()

    if args.function == 'archived':
        rpath = args.raw_path
        bpath = args.archived_path
        handler = BackupCacheHandler(raw_path=rpath, backup_path=bpath)
        handler.scan()
        if args.logging:
            with open(lst_fname, 'w') as f:
                handler.print_completed(fobj=f)
        handler.print_completed()

    elif args.function == 'review':
        rpath = args.raw_path
        bpath = args.archived_path
        handler = BackupCacheHandler(raw_path=rpath, backup_path=bpath)
        handler.scan()
        if args.logging:
            with open(log_fname, 'w') as f:
                handler.print_status(fobj=f)
        else:
            handler.print_status()

    elif args.function == 'clean':
        rpath = args.raw_path
        bpath = args.archived_path
        handler = BackupCacheHandler(raw_path=rpath, backup_path=bpath)
        handler.scan()
        handler.clean()

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
