from shleeh import *
from shleeh.errors import *
from .loader import BrukerLoader
from .utils import get_dirsize, get_filesize, yes_or_no
import os
import sys
import tqdm
import pickle
import zipfile
import datetime
import getpass
_bar_fmt = '{l_bar}{bar:20}{r_bar}{bar:-20b}'
_user = getpass.getuser()
_width = 80
_line_sep_1 = '-' * _width
_line_sep_2 = '=' * _width
_empty_sep = ''


class NamedTuple(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class BackupCache:
    def __init__(self):
        self._init_dataset_class()

    def logging(self, message, method):
        now = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.log_data.append(NamedTuple(datetime=now, method=method, message=message))

    @property
    def num_raw(self):
        return len(self.raw_data)

    @property
    def num_arc(self):
        return len(self.arc_data)

    def _init_dataset_class(self):
        # dataset
        self.raw_data = []
        self.arc_data = []
        self.log_data = []

    def get_rpath_obj(self, path, by_arc=False):
        if len(self.raw_data):
            if by_arc:
                data_pid = [b.data_pid for b in self.arc_data if b.path == path]
                if len(data_pid):
                    rpath_obj = [r for r in self.raw_data if r.data_pid == data_pid[0]]
                    if len(rpath_obj):
                        return rpath_obj[0]
                    else:
                        return None
                else:
                    return None
            else:
                rpath_obj = [r for r in self.raw_data if r.path == path]
                if len(rpath_obj):
                    return rpath_obj[0]
                else:
                    return None
        else:
            return None

    def get_bpath_obj(self, path, by_raw=False):
        if len(self.arc_data):
            if by_raw:
                r = self.get_rpath_obj(path)
                if r is None:
                    return []
                else:
                    return [b for b in self.arc_data if b.data_pid == r.data_pid]
            else:
                data_pid = [b for b in self.arc_data if b.path == path][0].data_pid
                return [b for b in self.arc_data if b.data_pid == data_pid]
        else:
            return []

    def isin(self, path, raw=True):
        if raw:
            list_data = self.raw_data
        else:
            list_data = self.arc_data
        _history = [d for d in list_data if d.path == path]
        if len(_history):
            return True
        else:
            return False

    def set_raw(self, dirname, raw_dir, removed=False):
        # rawobj: data_pid, path, garbage, removed, backup
        if not removed:
            dir_path = os.path.join(raw_dir, dirname)
            if not self.isin(dirname, raw=True):  # continue if the path is not saved in this cache obj
                if os.path.isdir(dir_path):
                    raw = BrukerLoader(dir_path)
                    garbage = False if raw.is_pvdataset else True
                    rawobj = NamedTuple(data_pid=self.num_raw,
                                        path=dirname,
                                        garbage=garbage,
                                        removed=removed,
                                        backup=False)
                    self.raw_data.append(rawobj)
                else:
                    self.logging('{} is not directory. [raw dataset must be a directory]'.format(dir_path),
                                 'set_raw')
        else:
            rawobj = NamedTuple(data_pid=self.num_raw,
                                path=dirname,
                                garbage=None,
                                removed=removed,
                                backup=True)
            self.raw_data.append(rawobj)

    def set_arc(self, arc_fname, arc_dir, raw_dir):
        # arcobj: data_pid, path, garbage, crashed, issued
        arc_path = os.path.join(arc_dir, arc_fname)
        if not self.isin(arc_fname, raw=False):  # continue if the path is not saved in this cache obj
            issued = False
            try:
                arc = BrukerLoader(arc_path)
                raw_dname = arc.pvobj.path
                raw_path = os.path.join(raw_dir, raw_dname)
                garbage = False if arc.is_pvdataset else True
                crashed = False
            except:
                self.logging('{} is crashed.'.format(arc_path),
                             'set_arc')
                arc = None
                raw_dname = None
                raw_path = None
                garbage = True
                crashed = True

            if raw_dname is not None:
                r = self.get_rpath_obj(raw_dname)
            else:
                r = None

            if r is None:
                raw_dname = os.path.splitext(arc_fname)[0]
                self.set_raw(raw_dname, raw_dir, removed=True)
                r = self.get_rpath_obj(raw_dname)
                r.garbage = garbage
                if crashed:
                    issued = True
            else:
                if arc is None:
                    issued = True
                else:
                    if not r.removed:
                        raw = BrukerLoader(raw_path)
                        if raw.num_recos != arc.num_recos:
                            issued = True
            arcobj = NamedTuple(data_pid=r.data_pid,
                                path=arc_fname,
                                garbage=garbage,
                                crashed=crashed,
                                issued=issued)
            if not crashed:
                if not issued:
                    # backup completed data must has no issue
                    r.backup = True

            self.arc_data.append(arcobj)

    def is_duplicated(self, file_path, by_arc=False):
        if by_arc:
            b = self.get_bpath_obj(file_path, by_raw=False)
        else:
            b = self.get_bpath_obj(file_path, by_raw=True)
        if len(b) > 1:
            return True
        else:
            return False


class BackupCacheHandler:
    def __init__(self, raw_path, backup_path, fname='.brk-backup_cache'):
        """ Handler class for backup data

        Args:
            raw_path:       path for raw dataset
            backup_path:    path for backup dataset
            fname:          file name to pickle cache data
        """
        self._cache = None
        self._rpath = os.path.expanduser(raw_path)
        self._apath = os.path.expanduser(backup_path)
        self._cache_path = os.path.join(self._apath, fname)
        self._load_pickle()
        # self._parse_info()

    def _load_pickle(self):
        if os.path.exists(self._cache_path):
            try:
                with open(self._cache_path, 'rb') as cache:
                    self._cache = pickle.load(cache)
            except EOFError:
                os.remove(self._cache_path)
                self._cache = BackupCache()
        else:
            self._cache = BackupCache()
        self._save_pickle()

    def _save_pickle(self):
        with open(self._cache_path, 'wb') as f:
            pickle.dump(self._cache, f)

    def logging(self, message, method):
        method = 'Handler.{}'.format(method)
        self._cache.logging(message, method)

    @property
    def is_duplicated(self):
        return self._cache.is_duplicated

    @property
    def get_rpath_obj(self):
        return self._cache.get_rpath_obj

    @property
    def get_bpath_obj(self):
        return self._cache.get_bpath_obj

    @property
    def arc_data(self):
        return self._cache.arc_data

    @property
    def raw_data(self):
        return self._cache.raw_data

    @property
    def scan(self):
        return self._parse_info

    def _parse_info(self):
        print('\n-- Parsing data information from folders --')
        list_of_raw = sorted([d for d in os.listdir(self._rpath) if
                              os.path.isdir(os.path.join(self._rpath, d))])
        list_of_brk = sorted([d for d in os.listdir(self._apath) if
                              (os.path.isfile(os.path.join(self._apath, d)) and
                               (d.endswith('zip') or d.endswith('PvDatasets')))])

        # parse dataset
        print('\nScanning raw dataset and update cache...')
        for r in tqdm.tqdm(list_of_raw, bar_format=_bar_fmt):
            self._cache.set_raw(r, raw_dir=self._rpath)
        self._save_pickle()

        print('\nScanning archived dataset and update cache...')
        for b in tqdm.tqdm(list_of_brk, bar_format=_bar_fmt):
            self._cache.set_arc(b, arc_dir=self._apath, raw_dir=self._rpath)
        self._save_pickle()

        # update raw dataset information (raw dataset cache will remain even its removed)
        print('\nScanning raw dataset cache...')
        for r in tqdm.tqdm(self.raw_data[:], bar_format=_bar_fmt):
            if r.path is not None:
                if not os.path.exists(os.path.join(self._rpath, r.path)):
                    if not r.removed:
                        r.removed = True
        self._save_pickle()

        print('\nReviewing archived dataset cache...')
        for b in tqdm.tqdm(self.arc_data[:], bar_format=_bar_fmt):
            arc_path = os.path.join(self._apath, b.path)
            if not os.path.exists(arc_path):  # backup dataset is not existing, remove the cache
                self.arc_data.remove(b)
            else:  # backup dataset is existing then check status again
                if b.issued:  # check if the issue has benn resolved.
                    if b.crashed:  # check if the dataset re-backed up.
                        if zipfile.is_zipfile(arc_path):
                            b.crashed = False  # backup success!
                            b.issued = False if self.is_same_as_raw(b.path) else True
                            if b.issued:
                                if b.garbage:
                                    if BrukerLoader(arc_path).is_pvdataset:
                                        b.garbage = False
                        # else the backup dataset it still crashed.
                    else:  # the dataset has an issue but not crashed, so check if the issue has been resolved.
                        b.issued = False if self.is_same_as_raw(b.path) else True
                        if not b.issued:  # if issue resolved
                            r = self.get_rpath_obj(b.path, by_arc=True)
                            r.backup = True
                else:  # if no issue with the dataset, do nothing.
                    r = self.get_rpath_obj(b.path, by_arc=True)
                    if not r.backup:
                        r.backup = True
        self._save_pickle()

    def is_same_as_raw(self, filename):
        arc = BrukerLoader(os.path.join(self._apath, filename))
        if arc.pvobj.path is not None:
            raw_path = os.path.join(self._rpath, arc.pvobj.path)
            if os.path.exists(raw_path):
                raw = BrukerLoader(raw_path)
                return arc.num_recos == raw.num_recos
            else:
                return None
        else:
            return None

    def get_duplicated(self):
        duplicated = dict()
        for b in self.arc_data:
            if self.is_duplicated(b.path, by_arc=True):
                rpath = self.get_rpath_obj(b.path, by_arc=True).path
                if rpath in duplicated.keys():
                    duplicated[rpath].append(b.path)
                else:
                    duplicated[rpath] = [b.path]
            else:
                pass
        return duplicated

    def get_list_for_backup(self):
        return [r for r in self.get_incompleted() if not r.garbage]

    def get_issued(self):
        return [b for b in self.arc_data if b.issued]

    def get_crashed(self):
        return [b for b in self.arc_data if b.crashed]

    def get_incompleted(self):
        return [r for r in self.raw_data if not r.backup]

    def get_completed(self):
        return [r for r in self.raw_data if r.backup]

    def get_garbage(self):
        return [b for b in self.arc_data if b.garbage]

    @staticmethod
    def _gen_header(title, width=_width):
        lines = []
        gen_by = 'Generated by {}'.format(_user).rjust(width)

        lines.append(_empty_sep)
        lines.append(_line_sep_2)
        lines.append(_empty_sep)
        lines.append(title.center(width))
        lines.append(gen_by)
        lines.append(_line_sep_2)
        lines.append(_empty_sep)
        return lines

    def _get_backup_status(self):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = self._gen_header('Report of backup status review [{}]'.format(now))
        list_need_to_be_backup = self.get_list_for_backup()[:]
        total_list = len(list_need_to_be_backup)
        if len(list_need_to_be_backup):
            lines.append('>> Raw dataset need to be backup.')
            lines.append('[Note: The raw dataset does not has any "fid" will not be listed here]')
            lines.append(_line_sep_1)
            lines.append('{}{}'.format('Rawdata Path'.center(_width-10), 'Size'.rjust(10)))
            for r in list_need_to_be_backup:
                if len(r.path) > _width-10:
                    path_name = '{}... '.format(r.path[:_width-14])
                else:
                    path_name = r.path
                raw_path = os.path.join(self._rpath, r.path)
                dir_size, unit = get_dirsize(raw_path)
                if unit == 'B':
                    dir_size = '{} {}'.format(dir_size, unit).rjust(10)
                else:
                    dir_size = '{0:.2f}{1}'.format(dir_size, unit).rjust(10)
                lines.append('{}{}'.format(path_name.ljust(_width-10), dir_size))
            lines.append(_line_sep_1)
            lines.append(_empty_sep)

        list_issued = self.get_issued()
        total_list += len(list_issued)
        if len(list_issued):
            lines.append('>> Failed or incompleted archived dataset.')
            lines.append('[Note: The listed files are either crashed or incompleted]')
            lines.append(_line_sep_1)
            lines.append('{}{}{}'.format('Backup Path'.center(60),
                                         'Condition'.rjust(10),
                                         'Size'.rjust(10)))
            for b in self.get_issued():
                if len(b.path) > _width-20:
                    path_name = '{}... '.format(b.path[:_width-24])
                else:
                    path_name = b.path
                arc_path = os.path.join(self._apath, b.path)
                file_size, unit = get_filesize(arc_path)
                if b.crashed:
                    raw_path = self.get_rpath_obj(b.path, by_arc=True).path
                    if raw_path is None:
                        condition = 'Failed'
                    else:
                        condition = 'Crashed'
                else:
                    condition = 'Issued'
                if unit == 'B':
                    file_size = '{} {}'.format(file_size, unit).rjust(10)
                else:
                    file_size = '{0:.2f}{1}'.format(file_size, unit).rjust(10)
                lines.append('{}{}{}'.format(path_name.ljust(_width-20),
                                             condition.center(10),
                                             file_size))
            lines.append(_line_sep_1)
            lines.append(_empty_sep)

        list_duplicated = self.get_duplicated()
        total_list += len(list_duplicated)
        if len(list_duplicated.keys()):
            lines.append('>> Duplicated archived dataset.')
            lines.append('[Note: The listed raw dataset has multiple archived files]')
            lines.append(_line_sep_1)
            lines.append('{}  {}'.format('Raw Path'.center(int(_width/2)-1),
                                         'Archived'.center(int(_width/2)-1)))
            for rpath, bpaths in list_duplicated.items():
                if rpath is None:
                    rpath = '-- Removed --'
                if len(rpath) > int(_width/2)-1:
                    rpath = '{}... '.format(rpath[:int(_width/2)-5])
                for i, bpath in enumerate(bpaths):
                    if len(bpath) > int(_width/2)-1:
                        bpath = '{}... '.format(bpath[:int(_width/2)-5])
                    if i == 0:
                        lines.append('{}:-{}'.format(rpath.ljust(int(_width/2)-1),
                                                     bpath.ljust(int(_width/2)-1)))
                    else:
                        lines.append('{} -{}'.format(''.center(int(_width/2)-1),
                                                     bpath.ljust(int(_width/2)-1)))
            lines.append(_line_sep_1)
            lines.append(_empty_sep)

        if total_list == 0:
            lines.append(_empty_sep)
            lines.append('Backup status is up-to-date...'.center(80))
            lines.append(_empty_sep)
            lines.append(_line_sep_1)
        return '\n'.join(lines)

    def print_status(self, fobj=sys.stdout):
        summary = self._get_backup_status()
        print(summary, file=fobj)

    def print_completed(self, fobj=sys.stdout):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = self._gen_header('List of archived dataset [{}]'.format(now))
        list_of_completed = self.get_completed()
        if len(list_of_completed):
            lines.append(_line_sep_1)
            lines.append('{}{}{}'.format('Rawdata Path'.center(_width - 20),
                                         'Removed'.rjust(10),
                                         'Archived'.rjust(10)))
            for r in list_of_completed:
                if len(r.path) > _width - 20:
                    path_name = '{}... '.format(r.path[:_width - 24])
                else:
                    path_name = r.path
                removed = 'True' if r.removed else 'False'
                archived = 'True' if r.backup else 'False'
                lines.append('{}{}{}'.format(path_name.ljust(_width - 20),
                                             removed.center(10),
                                             archived.center(10)))
            lines.append(_line_sep_1)
            lines.append(_empty_sep)
        else:
            lines.append(_empty_sep)
            lines.append('No archived data...'.center(80))
            lines.append(_empty_sep)
            lines.append(_line_sep_1)
        summary = '\n'.join(lines)
        print(summary, file=fobj)

    def clean(self):
        print('\n[Warning] This command will remove backup data that classified as issued and cannot be revert.')
        print('          Prior to run this process, please update your backup status using "review" function.\n')
        ans = yes_or_no('Are you sure to continue?')

        if ans:
            list_data = dict(issued=self.get_issued()[:],
                             garbage=self.get_garbage()[:],
                             crashed=self.get_crashed()[:],
                             duplicated=self.get_duplicated().copy())
            for label, dset in list_data.items():
                if label == 'duplicated':
                    print('\nStart removing {} backup dataset...'.format(label.upper()))
                    if len(dset.items()):
                        for raw_dname, arcs in dset.items():
                            if raw_dname is not None:
                                raw_path = os.path.join(self._rpath, raw_dname)
                                if os.path.exists(raw_path):
                                    r_size, r_unit = get_dirsize(raw_path)
                                    r_size = '{0:.2f} {1}'.format(r_size, r_unit)
                                else:
                                    r_size = 'Removed'
                                if len(raw_dname) < 60:
                                    raw_dname = '{}...'.format(raw_dname[:56])
                            else:
                                r_size = 'Removed'
                                raw_dname = 'No name'
                            print('Raw dataset: [{}] {}'.format(raw_dname.ljust(60), r_size.rjust(10)))
                            num_dup = len(arcs)
                            dup_list = ['  +-{}'] * num_dup
                            print('\n'.join(dup_list).format(*arcs))
                            for arc_fname in arcs:
                                path_to_clean = os.path.join(self._apath, arc_fname)
                                ans_4rm = yes_or_no(' - Are you sure to remove [{}] ?\n  '.format(arc_fname))
                                if ans_4rm:
                                    try:
                                        os.remove(path_to_clean)
                                        a = self.get_bpath_obj(arc_fname)
                                        if len(a):
                                            self.arc_data.remove(a[0])
                                    except OSError:
                                        error = RemoveFailedError(path_to_clean)
                                        self.logging(error.message, 'clean')
                                        print('    Failed! The file is locked.')
                                    else:
                                        raise UnexpectedError
                else:
                    if len(dset):
                        print('\nStart removing {} backup dataset...'.format(label.upper()))

                        def ask_to_remove():
                            ans_4rm = yes_or_no(' - Are you sure to remove [{}] ?\n  '.format(path_to_clean))
                            if ans_4rm:
                                try:
                                    os.remove(path_to_clean)
                                    self.arc_data.remove(a)
                                except OSError:
                                    error = RemoveFailedError(path_to_clean)
                                    self.logging(error.message, 'clean')
                                    print('    Failed! The file is locked.')
                                else:
                                    raise UnexpectedError
                        for a in dset:
                            path_to_clean = os.path.join(self._apath, a.path)
                            if label == 'issued':
                                if a.garbages or a.crashed:
                                    pass
                                else:
                                    ask_to_remove()
                            elif label == 'garbage':
                                if a.crashed:
                                    pass
                                else:
                                    ask_to_remove()
        self._save_pickle()

    def backup(self, fobj=sys.stdout):
        list_raws = self.get_list_for_backup()[:]
        list_issued = self.get_issued()[:]
        print('\nStarting backup for raw data not listed in the cache...')
        self.logging('Backup process start...', 'backup')

        for i, dlist in enumerate([list_raws, list_issued]):
            if i == 0:
                print('\n[step1] Performing backup for the raw datasets that has not been archived.')
                self.logging('backup the raw dataset has not been archived...', 'backup')
            elif i == 1:
                print('\n[step2] Performing backup for the datasets that has issued on archived data.')
                self.logging('backup the raw dataset contain issues...', 'backup')

            for r in tqdm.tqdm(dlist, unit=' dataset(s)', bar_format=_bar_fmt):
                run_backup = True
                raw_path = os.path.join(self._rpath, r.path)
                arc_path = os.path.join(self._apath, '{}.zip'.format(r.path))
                tmp_path = os.path.join(self._apath, '{}.part'.format(r.path))
                if os.path.exists(raw_path):
                    if os.path.exists(tmp_path):
                        print(' -[{}] is detected and removed...'.format(tmp_path), file=fobj)
                        os.unlink(tmp_path)
                    if os.path.exists(arc_path):
                        if not zipfile.is_zipfile(arc_path):
                            print(' -[{}] is crashed file, removing...'.format(arc_path), file=fobj)
                            os.unlink(arc_path)
                        else:
                            arc = BrukerLoader(arc_path)
                            raw = BrukerLoader(raw_path)
                            if arc.is_pvdataset:
                                if arc.num_recos != raw.num_recos:
                                    print(' - [{}] is mismatching with raw dataset, removing...'.format(arc_path), file=fobj)
                                    os.unlink(arc_path)
                                else:
                                    run_backup = False
                            else:
                                print(' - [{}] is mismatching with raw dataset, removing...'.format(arc_path), file=fobj)
                                os.unlink(arc_path)
                    if run_backup:
                        print('\n :: Compressing [{}]...'.format(raw_path), file=fobj)
                        # Compressing
                        timer = TimeCounter()
                        try:  # exception handling in case compression is failed
                            with zipfile.ZipFile(tmp_path, 'w') as zip:
                                # prepare file counters for use of tqdm
                                file_counter = 0
                                for _ in os.walk(raw_path):
                                    file_counter += 1

                                for i, (root, dirs, files) in tqdm.tqdm(enumerate(os.walk(raw_path)),
                                                                        bar_format=_bar_fmt,
                                                                        total=file_counter,
                                                                        unit=' file(s)'):
                                    splitted_root = root.split(os.sep)
                                    if i == 0:
                                        root_idx = splitted_root.index(r.path)
                                    for f in files:
                                        arc_name = os.sep.join(splitted_root[root_idx:] + [f])
                                        zip.write(os.path.join(root, f), arcname=arc_name)
                            print(' - [{}] is generated'.format(os.path.basename(arc_path)), file=fobj)

                        except Exception:
                            error = ArchiveFailedError(raw_path)
                            self.logging(error.message, 'backup')
                            raise error

                        print(' - processed time: {} sec'.format(timer.time()), file=fobj)

                        # Backup validation
                        if not os.path.exists(tmp_path):  # Check if the file is generated
                            error = ArchiveFailedError(raw_path)
                            self.logging(error.message, 'backup')
                            raise error
                        else:
                            try:
                                os.rename(tmp_path, arc_path)
                            except OSError:
                                error = RenameFailedError(tmp_path, arc_path)
                                self.logging(error.message, 'backup')
                                raise error
                            else:
                                error = UnexpectedError
                                self.logging(error.message, 'backup')
                                raise error
