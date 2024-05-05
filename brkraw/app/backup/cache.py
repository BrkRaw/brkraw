from brkraw.app.tonifti import StudyToNifti

import os
import datetime



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
        #TODO: need to check if the space enough to perform backup, as well as handle the crash event
        #during the backup (the cache updated even the backup failed)

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
                    raw = StudyToNifti(dir_path)
                    garbage = False if raw.is_pvdataset else True
                    rawobj = NamedTuple(data_pid=self.num_raw,
                                        path=dirname,
                                        garbage=garbage,
                                        removed=removed,
                                        backup=False)
                    self.raw_data.append(rawobj)
                else:
                    self.logging('{} is not a valid directory. [raw dataset must be a directory]'.format(dir_path),
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
                arc = StudyToNifti(arc_path)
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

            if raw_dname != None:
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
                        if not r.backup:
                            pass
                        else:
                            raw = StudyToNifti(raw_path)
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



