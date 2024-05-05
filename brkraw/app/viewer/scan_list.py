import tkinter as tk
from .config import font


class ScanList(tk.Frame):
    def __init__(self, *args, **kwargs):
        super(ScanList, self).__init__(*args, **kwargs)
        self._init_scanlist()
        self._init_recolist()
        self._init_buttons()

    def _init_scanlist(self):
        self._scanlist_label = tk.Label(self, text='Scan ID / Protocol')
        self._scanlist_label.pack(side=tk.TOP, fill=tk.X, pady=5)
        self._scanlist_frame = tk.Frame(self)
        self._scanlist_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10)
        self._scanlist= tk.Listbox(self._scanlist_frame, width=30,
                                   exportselection=False)
        self._scanlist.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._set_scollbar(self._scanlist_frame, self._scanlist)
        self._scanlist.config(font=font, state=tk.DISABLED)
        self._scanlist_label.config(font=font)

    def _init_recolist(self):
        self._recolist_label = tk.Label(self, text='Reco ID / DataType')
        self._recolist_label.pack(side=tk.TOP, fill=tk.X, pady=5)
        self._recolist_frame = tk.Frame(self, height=5)
        self._recolist_frame.pack(side=tk.TOP, fill=tk.BOTH, padx=10)
        self._recolist = tk.Listbox(self._recolist_frame, width=30, height=5,
                                    exportselection=False)
        self._recolist.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._set_scollbar(self._recolist_frame, self._recolist)
        self._recolist.config(font=font, state = tk.DISABLED)
        self._recolist_label.config(font=font)

    def _init_buttons(self):
        self._button_fm = tk.Frame(self)
        self._button_fm.pack(side=tk.TOP, fill=tk.X)
        self._updt_bt = tk.Button(self._button_fm, text='SetOutput')
        self._conv_bt = tk.Button(self._button_fm, text='Convert')
        self._updt_bt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._conv_bt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._updt_bt.config(state=tk.DISABLED, font=font)
        self._conv_bt.config(state=tk.DISABLED, font=font)

    @staticmethod
    def _set_scollbar(frame, listbox_obj):
        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL)
        scrollbar.config(command=listbox_obj.yview)
        scrollbar.pack(side=tk.RIGHT, fill="y")
        listbox_obj.config(yscrollcommand=scrollbar.set)

    def load_data(self, brkraw_obj):
        from brkraw.lib.utils import get_value
        self._scanlist.config(state=tk.NORMAL)
        for scan_id, recos in brkraw_obj._avail.items():
            visu_pars = brkraw_obj._get_visu_pars(scan_id, recos[0])
            protocol_name = get_value(visu_pars, 'VisuAcquisitionProtocol')
            self._scanlist.insert(tk.END, '{}::{}'.format(str(scan_id).zfill(3),
                                                          protocol_name))
        self._scanlist.select_set(0)

    def _update_recos(self, brkraw_obj, scan_id):
        from brkraw.lib.utils import get_value
        self._recolist.config(state=tk.NORMAL)
        recos = brkraw_obj._avail[scan_id]
        self._recolist.delete(0, tk.END)
        for reco_id in recos:
            visu_pars = brkraw_obj._get_visu_pars(scan_id, reco_id)
            frame_type = get_value(visu_pars, 'VisuCoreFrameType')
            self._recolist.insert(tk.END, '{}::{}'.format(str(reco_id).zfill(3),
                                                          frame_type))
        self._recolist.select_set(0)
