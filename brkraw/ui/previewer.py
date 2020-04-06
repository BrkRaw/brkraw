import tkinter as tk
from PIL import Image, ImageTk
import numpy as np
from .config import viewer_width, viewer_height


class Previewer(tk.Frame):
    def __init__(self, *args, **kwargs):
        super(Previewer, self).__init__(*args, **kwargs)
        # variables
        self._dataobj = None
        self._imgobj = None
        self._is_tripilot = False
        self._current_slice = 0
        self._current_frame = 0

        self.tkimg = None
        self.slice_axis = tk.IntVar()
        self.slice_axis.set(99)

        self._set_axisbuttons()
        self._set_canvas()
        self._set_sliders()

    def _set_canvas(self):
        self._canvas = tk.Canvas(self,
                                 width=viewer_width,
                                 height=viewer_height)
        self._canvas.place(x=50, y=30)

    def _set_axisbuttons(self):
        self._axis_buttons = []

        tk.Label(self, text='Slice Axis::').place(x=50, y=5)
        for i, axis in enumerate(['x', 'y', 'z']):
            button = tk.Radiobutton(self,
                                    text=axis,
                                    padx=10,
                                    variable=self.slice_axis,
                                    command=self._change_sliceaxis,
                                    value=i)
            button.place(x=150 + i*50, y=5)

            if self.slice_axis.get() == 99:
                button['state'] = 'disabled'
            self._axis_buttons.append(button)

    def _set_sliders(self, n_slice=0, n_frame=0):

        tk.Label(self, text='Slice').place(x=70, y=455)
        tk.Label(self, text='Frame').place(x=70, y=495)
        self.slice_slider = tk.Scale(self, from_=0, to=n_slice - 1,
                                     orient=tk.HORIZONTAL,
                                     command=self._change_slice, length=300)

        self.frame_slider = tk.Scale(self, from_=0, to=n_frame - 1,
                                     orient=tk.HORIZONTAL,
                                     command=self._change_frame, length=300)

        self.slice_slider.set(self._current_slice)
        self.frame_slider.set(self._current_frame)
        self.slice_slider.place(x=130, y=440)
        self.frame_slider.place(x=130, y=480)

        if n_slice == 0:
            self.slice_slider.config(state=tk.DISABLED)
        if n_frame == 0:
            self.frame_slider.config(state=tk.DISABLED)

    def update_image(self):
        self._canvas.create_image((int(viewer_width / 2), int(viewer_height / 2)),
                                  image=self.tkimg)

    def _load_image(self, brkraw_obj, scan_id, reco_id):
        # update image when scan_id and reco_id is changed
        visu_pars = brkraw_obj._get_visu_pars(scan_id, reco_id)
        dataobj = brkraw_obj._get_dataobj(scan_id, reco_id)
        shape = brkraw_obj._get_matrix_size(visu_pars, dataobj)
        self._dataobj = dataobj.reshape(shape[::-1]).T[:,:,::-1, ...]
        n_slicepacks = brkraw_obj._get_slice_info(visu_pars)['num_slice_packs']
        spatial_info = brkraw_obj._get_spatial_info(visu_pars)

        self._resol = spatial_info['spatial_resol']
        self._matrix_size = spatial_info['matrix_size']

        if n_slicepacks > 1:
            self._is_tripilot = True
        else:
            self._is_tripilot = False

    def _change_sliceaxis(self):
        if self.slice_axis.get() in range(3):
            self._imgobj = np.swapaxes(self._dataobj, axis1=self.slice_axis.get(), axis2=2)
            shape = self._imgobj.shape
            n_slice = shape[2]

            self._current_slice = int(n_slice / 2)
            self._current_frame = 0

            shape = self._imgobj.shape
            if len(shape) > 3:
                n_frame = shape[3]
            else:
                n_frame = 0
            n_slice = shape[2]

            self._current_slice = int(n_slice / 2)
            self._current_frame = 0

            self._set_sliders(n_slice, n_frame)

    def _convert_image(self):
        if len(self._imgobj.shape) > 3:
            img = self._imgobj[:,:,self._current_slice,self._current_frame]
        else:
            img = self._imgobj[:,:,self._current_slice]

        slice_axis = self.slice_axis.get()
        if slice_axis in range(3):
            axis_ref = np.array([0, 1, 2])
            axis_ref[slice_axis], axis_ref[2] = axis_ref[2], axis_ref[slice_axis]

            self._img_resol = np.array(self._resol[0])[axis_ref]
            self._img_size = np.array(self._matrix_size[0])[axis_ref]
        else:
            self._img_resol = np.array(self._resol[0])
            self._img_size = np.array(self._matrix_size[0])

        img_fov = self._img_resol.astype(float) * self._img_size.astype(float)
        max_val = img_fov[:2].max()
        img_fov /= max_val
        img_fov *= 400

        # check resolution
        img_width, img_height = int(img_fov[0]), int(img_fov[1])

        self.tkimg = self.convert_pil2tk(self.convert_npy2pil(img),
                                         img_width, img_height)

    def _change_slice(self, event):
        self._current_slice = self.slice_slider.get()
        self._convert_image()
        self.update_image()

    def _change_frame(self, event):
        self._current_frame = self.frame_slider.get()
        self._convert_image()
        self.update_image()

    def load_data(self, brkraw_obj, scan_id, reco_id):
        # load image from dataset
        self._load_image(brkraw_obj, scan_id, reco_id)
        shape = self._dataobj.shape
        if len(shape) > 3:
            n_frame = shape[3]
        else:
            n_frame = 0
        n_slice = shape[2]

        self._current_slice = int(n_slice/2)
        self._current_frame = 0

        if self._is_tripilot:
            self.slice_axis.set(99)
            for button in self._axis_buttons:
                button['state'] = 'disabled'
        else:
            for button in self._axis_buttons:
                button['state'] = 'normal'
            self.slice_axis.set(2)
        self._set_sliders(n_slice, n_frame)
        self._imgobj = self._dataobj
        self._convert_image()
        self.update_image()

    @staticmethod
    def convert_npy2pil(data, mode=None, rescale=True):
        """ convert 2D numpy.array to PIL.Image object

        Args:
            data: 2D array data
            mode: mode of image object
                link=https://pillow.readthedocs.io/en/latest/handbook/concepts.html#modes
            rescale: rescale value to 0~255

        Returns: PIL.Image object

        """
        if rescale == True:
            rescaled_data = data / data.max() * 255
        else:
            rescaled_data = data
        rescaled_data = rescaled_data.astype('uint8')
        return Image.fromarray(rescaled_data.T, mode=mode)

    @staticmethod
    def convert_pil2tk(pilobj, width, height, method='nearest'):
        """ convert PIL.Image object to tkinter.PhotoImage object
        This will allow plotting image on Tk.Canvas

        Args:
            pilobj: 2D image object
            width: width of the image
            height: height of the image
            method: Method for interpolation

        Returns: TkImage object

        """
        if method == 'nearest':
            method = Image.NEAREST
        else:
            method = Image.ANTIALIAS
        return ImageTk.PhotoImage(pilobj.resize((width, height), method))