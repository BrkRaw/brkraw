# -*- coding: utf-8 -*-
from .. import __version__
from ..lib.backup import BackupCacheHandler
import argparse
import datetime


def main():
    parser = argparse.ArgumentParser(prog='brk-backup',
                                     description="BrkRaw command-line interface for archiving")
    parser.add_argument("-v", "--version", action='version', version='%(prog)s v{}'.format(__version__))

    subparsers = parser.add_subparsers(title='Sub-commands',
                                       description='brk-backup provides convenient tool '
                                                   'for archiving and check the status.',
                                       help='description',
                                       dest='function',
                                       metavar='command')

    raw_path_str = "The directory of raw data of current user in ParaVision system."
    arc_path_str = "The directory of archived data. It must be mounted into ParaVision system."
    logging_str = "option for logging output instead printing"

    # added function
    archived    = subparsers.add_parser("archived", help='Scan the status of archived data')
    review      = subparsers.add_parser("review", help='Review the confliction between raw data and archived data')
    backup      = subparsers.add_parser("backup", help='Archive the raw data. must be performed after review')
    clean       = subparsers.add_parser("clean", help='Clean the archived that contains any issue')

    # options for archived function
    archived.add_argument("raw_path",           help=raw_path_str,  type=str)
    archived.add_argument("archived_path",      help=arc_path_str,  type=str)
    archived.add_argument("-l", "--logging",    help=logging_str,   action='store_true')

    # options for review function
    review.add_argument("raw_path",             help=raw_path_str,  type=str)
    review.add_argument("archived_path",        help=arc_path_str,  type=str)
    review.add_argument("-l", "--logging",      help=logging_str,   action='store_true')

    # options for backup function
    backup.add_argument("raw_path",             help=raw_path_str,  type=str)
    backup.add_argument("archived_path",        help=arc_path_str,  type=str)
    backup.add_argument("-l", "--logging",      help=logging_str,   action='store_true')

    # options for clean function
    clean.add_argument("raw_path",              help=raw_path_str,  type=str)
    clean.add_argument("archived_path",         help=arc_path_str,  type=str)

    # filename definitions for logging
    now = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_fname = 'brk-backup_{}.log'.format(now)
    lst_fname = 'brk-backup_archived_{}.log'.format(now)
    rvw_fname = 'brk-backup_review_{}.log'.format(now)

    # initial argument parsing
    args = parser.parse_args()

    # code for archived function
    if args.function == 'archived':
        rpath = args.raw_path
        bpath = args.archived_path
        handler = BackupCacheHandler(raw_path=rpath, backup_path=bpath)
        handler.scan()
        if args.logging:
            with open(lst_fname, 'w') as f:
                handler.print_completed(fobj=f)
        handler.print_completed()

    # code for review function
    elif args.function == 'review':
        rpath = args.raw_path
        bpath = args.archived_path
        handler = BackupCacheHandler(raw_path=rpath, backup_path=bpath)
        handler.scan()
        if args.logging:
            with open(rvw_fname, 'w') as f:
                handler.print_status(fobj=f)
        else:
            handler.print_status()

    # code for backup function
    elif args.function == 'backup':
        rpath = args.raw_path
        bpath = args.archived_path
        handler = BackupCacheHandler(raw_path=rpath, backup_path=bpath)
        handler.scan()
        if args.logging:
            with open(log_fname, 'w') as f:
                handler.backup(fobj=f)
        else:
            handler.backup()

    # code for clean function
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
