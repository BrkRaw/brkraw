import tkinter as tk
from .config import font


class ScanInfo(tk.Frame):
    def __init__(self, *args, **kwargs):
        super(ScanInfo, self).__init__(*args, **kwargs)
        self.title = tk.Label(self, text='Selected Scan Info')
        self.title.pack(side=tk.TOP, fill=tk.X)
        self.textbox = tk.Text(self, width=30)
        self.textbox.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.textbox.configure(font=font)

    def load_data(self, brkraw_obj, scan_id, reco_id):
        from brkraw.lib.utils import get_value, is_all_element_same
        visu_pars = brkraw_obj._get_visu_pars(scan_id, reco_id)
        self.textbox.config(state=tk.NORMAL)
        self.textbox.delete('1.0', tk.END)

        # RepetitionTime
        tr = get_value(visu_pars, 'VisuAcqRepetitionTime')
        tr = ','.join(map(str, tr)) if isinstance(tr, list) else tr
        # EchoTime
        te = get_value(visu_pars, 'VisuAcqEchoTime')
        te = 0 if te is None else te
        te = ','.join(map(str, te)) if isinstance(te, list) else te
        # PixelBandwidth
        pixel_bw = get_value(visu_pars, 'VisuAcqPixelBandwidth')
        # FlipAngle
        flip_angle = get_value(visu_pars, 'VisuAcqFlipAngle')
        # Sequence and Protocol names
        sequence_name = get_value(visu_pars, 'VisuAcqSequenceName')
        protocol_name = get_value(visu_pars, 'VisuAcquisitionProtocol')
        acqpars  = brkraw_obj.get_acqp(int(scan_id))
        scan_name = acqpars._parameters['ACQ_scan_name']
        # Dimension
        dim = brkraw_obj._get_dim_info(visu_pars)[0]
        # MatrixSize
        size = brkraw_obj._get_matrix_size(visu_pars)
        size = ' x '.join(map(str, size))
        # FOV size and resolution
        spatial_info = brkraw_obj._get_spatial_info(visu_pars)
        temp_info = brkraw_obj._get_temp_info(visu_pars)
        s_resol = spatial_info['spatial_resol']
        fov_size = spatial_info['fov_size']
        fov_size = ' x '.join(map(str, fov_size))
        s_unit = spatial_info['unit']
        t_resol = '{0:.3f}'.format(temp_info['temporal_resol'])
        t_unit = temp_info['unit']
        s_resol = list(s_resol[0]) if is_all_element_same(s_resol) else s_resol
        s_resol = ' x '.join(['{0:.3f}'.format(r) for r in s_resol])
        # Number of slice packs
        n_slicepacks = brkraw_obj._get_slice_info(visu_pars)['num_slice_packs']

        # Printing out
        self.textbox.insert(tk.END, 'Sequence:\n - {}\n'.format(sequence_name))
        self.textbox.insert(tk.END, 'Protocol:\n - {}\n'.format(protocol_name))
        self.textbox.insert(tk.END, 'Scan Name:\n - {}\n'.format(scan_name))
        self.textbox.insert(tk.END, 'RepetitionTime:\n - {} msec\n'.format(tr))
        self.textbox.insert(tk.END, 'EchoTime:\n - {} msec\n'.format(te))
        self.textbox.insert(tk.END, 'FlipAngle:\n - {} degree\n\n'.format(flip_angle))
        if isinstance(pixel_bw, float):
            self.textbox.insert(tk.END, 'PixelBandwidth:\n - {0:.3f} Hz\n'.format(pixel_bw))
        else:
            self.textbox.insert(tk.END, 'PixelBandwidth:\n - {} Hz\n'.format(pixel_bw))
        self.textbox.insert(tk.END, 'Dimension:\n - {}D\n'.format(dim))
        self.textbox.insert(tk.END, 'Matrix size:\n - {}\n'.format(size))
        self.textbox.insert(tk.END, 'Number of SlicePacks:\n - {}\n'.format(n_slicepacks))
        self.textbox.insert(tk.END, 'FOV size:\n - {} (mm)\n\n'.format(fov_size))
        self.textbox.insert(tk.END, 'Spatial resolution:\n - {} ({})\n'.format(s_resol, s_unit))
        self.textbox.insert(tk.END, 'Temporal resolution:\n - {} ({})\n'.format(t_resol, t_unit))
        self.textbox.config(state=tk.DISABLED)