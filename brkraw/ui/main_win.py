import tkinter as tk
from tkinter import filedialog
from brkraw import __version__, load
from .scan_list import ScanList
from .scan_info import ScanInfo
from .subj_info import SubjInfo
from .previewer import Previewer
from .config import win_pre_width as _width, win_pre_height as _height
from .config import win_pst_width, win_pst_height
from .config import window_posx, window_posy


class MainWindow(tk.Tk):
    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self._raw = None
        self._scan_id = None
        self._reco_id = None
        self._output = None
        self.title('BrukerRaw GUI - ver {}'.format(__version__))

        # initiated windows size and location
        self.geometry('{}x{}+{}+{}'.format(_width, _height,
                                           window_posx, window_posy))
        # minimal size
        self.minsize(_width, _height)
        self.maxsize(_width, _height)

        self._init_layout()

    def open_filediag(self):
        self._path = filedialog.askopenfilename(
            initialdir = ".",
            title = "Select file",
            filetypes = (("Paravision 6 format", "*.PVdatasets"),
                         ("Zip compressed", "*.zip")))
        self._extend_layout()
        self._load_dataset()

    def open_dirdiag(self):
        self._path = filedialog.askdirectory(
            initialdir = ".",
            title = "Select directory")
        self._extend_layout()
        self._load_dataset()

    def _init_layout(self):
        # level 1
        self._subj_info   = SubjInfo(self)
        self._subj_info.pack(
            side=tk.TOP,    fill=tk.X, anchor=tk.CENTER)

        # Button binding
        self._subj_info._loadfile.config(command=self.open_filediag)
        self._subj_info._loaddir.config(command=self.open_dirdiag)

    def _close(self):
        if self._raw != None:
            self.geometry('{}x{}+{}+{}'.format(_width, _height,
                                               window_posx, window_posy))

            # close opened frames
            self._subj_info._clean_path()
            self._subj_info._main_frame.destroy()
            self._subj_info._path.destroy()
            self._subj_info._path_label.destroy()
            self._subj_info._close.destroy()
            self._main_frame.destroy()

            self._raw.close()
            self._raw = None

            # minimal size
            self.minsize(_width, _height)
            self.maxsize(_width, _height)

    def _extend_layout(self):
        # Change windows size
        self._close()
        if len(self._path) != 0:
            self.geometry('{}x{}+{}+{}'.format(win_pst_width, win_pst_height,
                                               window_posx, window_posy))
            self.minsize(win_pst_width, win_pst_height)
            self.maxsize(win_pst_width, win_pst_height)

            # extend level 1
            self._subj_info._extend_layout()
            self._subj_info._close.config(command=self._close)

            self._main_frame = tk.Frame(self)
            self._main_frame.pack(
                side=tk.BOTTOM, fill=tk.BOTH,   expand=True)

            # level 2
            self._scan_list   = ScanList(self._main_frame)
            view_frame  = tk.Frame(self._main_frame)
            self._scan_list.pack(
                side=tk.LEFT,   fill=tk.BOTH)
            view_frame.pack(
                side=tk.LEFT,   fill=tk.BOTH,   expand=True)

            # level 3
            self._scan_info = ScanInfo(view_frame)
            self._preview   = Previewer(view_frame)
            self._preview.pack(
                side=tk.LEFT, fill=tk.BOTH, expand=True)
            self._scan_info.pack(
                side=tk.LEFT,   fill=tk.BOTH, padx=10, pady=10)
            self._bind_scanlist()
            self._set_convert_button()

    def _load_dataset(self):
        if len(self._path) != 0:
            self._raw = load(self._path)
            self._init_update()

    def _init_update(self):
        # take first image from dataset
        self._scan_id, recos = [v for i, v in enumerate(self._raw._avail.items()) if i == 0][0]

        self._reco_id = recos[0]
        # update subject info
        self._subj_info.load_data(self._raw)

        # update scan and reco listbox
        self._scan_list.load_data(self._raw)
        self._scan_list._update_recos(self._raw, self._scan_id)

        # update scan info of first image
        self._scan_info.load_data(self._raw, self._scan_id, self._reco_id)

        # update preview of first image
        self._preview.load_data(self._raw, self._scan_id, self._reco_id)

    def _bind_scanlist(self):
        self._scan_list._scanlist.bind('<<ListboxSelect>>', self._update_scanid)
        self._scan_list._recolist.bind('<<ListboxSelect>>', self._update_recoid)

    def _update_scanid(self, event):
        w = event.widget
        index = int(w.curselection()[0])
        self._scan_id = self._raw._pvobj.avail_scan_id[index]
        self._reco_id = self._raw._avail[self._scan_id][0]
        self._scan_list._update_recos(self._raw, self._scan_id)
        self._update_data()

    def _update_recoid(self, event):
        w = event.widget
        index = int(w.curselection()[0])
        self._reco_id = self._raw._avail[self._scan_id][index]
        self._update_data()

    def _update_data(self):
        # update scan info of first image
        self._scan_info.load_data(self._raw, self._scan_id, self._reco_id)
        # update preview of first image
        self._preview.load_data(self._raw, self._scan_id, self._reco_id)

    def _set_convert_button(self):
        self._scan_list._updt_bt.config(state=tk.NORMAL)
        self._scan_list._conv_bt.config(state=tk.NORMAL)
        self._scan_list._updt_bt.config(command=self._set_output)
        self._scan_list._conv_bt.config(command=self._save_as)

    def _set_output(self):
        self._output = filedialog.askdirectory(initialdir=self._output,
                                               title="Select Output Sirectory")

    def _save_as(self):
        date = self._raw.get_scan_time()['date'].strftime("%y%m%d")
        pvobj = self._raw._pvobj
        filename = '{}_{}_{}_{}_{}_{}'.format(date,
                                              pvobj.subj_id,
                                              pvobj.session_id,
                                              pvobj.study_id,
                                              self._scan_id, self._reco_id)
        self._raw.save_as(self._scan_id, self._reco_id, filename, dir=self._output)
        from tkinter import messagebox
        messagebox.showinfo(title='File conversion',
                            message='{}/{}.nii.gz has converted'.format(self._output,
                                                                       filename))

if __name__ == '__main__':
    root = MainWindow()
    root.mainloop()
