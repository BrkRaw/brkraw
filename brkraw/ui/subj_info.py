import tkinter as tk
from .config import font, button_size

class LabelItem(tk.Frame):
    def __init__(self, *args, **kwargs):
        super(LabelItem, self).__init__(*args, **kwargs)

    def set_label(self, text):
        self.label = tk.Label(self, text=text, width=8, anchor=tk.CENTER)
        self.entry = tk.Entry(self)
        self.label.pack(side=tk.LEFT, fill=tk.X,
                        anchor=tk.W, ipadx=5)
        self.entry.pack(side=tk.LEFT, fill=tk.X,
                        anchor=tk.W, ipadx=5)
        self.label.configure(font=font)
        self.entry.config(width=16, font=font)

    def set_entry(self, text):
        self.entry.config(state=tk.NORMAL)
        self.entry.delete(0, tk.END)
        if text == None:
            self.entry.insert(tk.END, '')
            self.entry.config(state=tk.DISABLED)
        else:
            self.entry.insert(tk.END, text)
            self.entry.config(state="readonly")


class SubjInfo(tk.Frame):
    def __init__(self, *args, **kwargs):
        super(SubjInfo, self).__init__(*args, **kwargs)
        self._init_layout()
        self.config(padx=10)

    def _init_layout(self):
        self._upper_frame = tk.Frame(self)
        self._upper_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, anchor=tk.CENTER)
        self._init_upper_frame()

    def _extend_layout(self):
        self._path_label = tk.Label(self._upper_frame, text='DataPath',
                                    width=button_size, font=font)
        self._path_label.pack(side=tk.LEFT, anchor=tk.E)
        self._close = tk.Button(self._upper_frame, text='Close',
                                font=font, width=button_size)
        self._close.pack(side=tk.RIGHT)
        self._path = tk.Text(self._upper_frame, height=1, font=font)
        self._path.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, anchor=tk.CENTER)
        self._path.config(state=tk.DISABLED)



        self._main_frame = tk.Frame(self)
        self._main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, anchor=tk.CENTER)
        self._init_main_frame()

    def _set_path(self, brkraw_obj):
        self._path.config(state=tk.NORMAL)
        self._path.insert(tk.END, brkraw_obj._pvobj.path)
        self._path.config(state=tk.DISABLED)

    def _clean_path(self):
        self._path.config(state=tk.NORMAL)
        self._path.delete(1.0, tk.END)
        self._path.config(state=tk.DISABLED)

    def _init_upper_frame(self):
        self._loadfile = tk.Button(self._upper_frame, text='Open File',
                                   font=font, width=button_size)
        self._loaddir  = tk.Button(self._upper_frame, text='Open Directory',
                                   font=font, width=button_size)
        self._loadfile.pack(side=tk.LEFT)
        self._loaddir.pack(side=tk.LEFT)

    def _init_main_frame(self):
        self._c0 = tk.Frame(self._main_frame)
        self._c0.pack(side=tk.LEFT, fill=tk.X, anchor=tk.NW)
        self._c1 = tk.Frame(self._main_frame)
        self._c1.pack(side=tk.LEFT, fill=tk.X, anchor=tk.NW)
        self._c2 = tk.Frame(self._main_frame)
        self._c2.pack(side=tk.LEFT, fill=tk.X, anchor=tk.NW)
        self._c3 = tk.Frame(self._main_frame)
        self._c3.pack(side=tk.LEFT, fill=tk.X, anchor=tk.NW)
        self._init_labelitems()

    @staticmethod
    def _set_labelitem(frame, label, text=None):
        item = LabelItem(frame)
        item.pack(side=tk.TOP)
        item.set_label(label)
        item.set_entry(text)
        return item

    def _init_labelitems(self):
        self._account       = self._set_labelitem(self._c0, 'Account')
        self._scandate      = self._set_labelitem(self._c0, 'Scan Date')
        self._researcher    = self._set_labelitem(self._c0, 'Researcher')
        self._subjectid     = self._set_labelitem(self._c1, 'Subject ID')
        self._sessionid     = self._set_labelitem(self._c1, 'Session ID')
        self._studyid       = self._set_labelitem(self._c1, 'Study ID')
        self._dob           = self._set_labelitem(self._c2, 'DOB')
        self._sex           = self._set_labelitem(self._c2, 'Sex')
        self._weight        = self._set_labelitem(self._c2, 'Weight')
        self._type          = self._set_labelitem(self._c3, 'Type')
        self._position      = self._set_labelitem(self._c3, 'Position')
        self._entry         = self._set_labelitem(self._c3, 'Entry')

    def load_data(self, brkraw_obj):
        datetime = brkraw_obj.get_scan_time()
        pvobj = brkraw_obj._pvobj
        self._account.set_entry(pvobj.user_account)
        self._researcher.set_entry(pvobj.user_name)
        self._scandate.set_entry('{}, {}'.format(datetime['date'], datetime['start_time']))
        self._subjectid.set_entry(pvobj.subj_id)
        self._sessionid.set_entry(pvobj.session_id)
        self._studyid.set_entry(pvobj.study_id)
        self._dob.set_entry(pvobj.subj_dob)
        self._sex.set_entry(pvobj.subj_sex)
        self._weight.set_entry('{} kg'.format(pvobj.subj_weight))
        self._type.set_entry(pvobj.subj_type)
        self._position.set_entry(pvobj.subj_pose)
        self._entry.set_entry(pvobj.subj_entry)
        self._set_path(brkraw_obj)