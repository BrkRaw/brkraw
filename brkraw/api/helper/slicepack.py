from __future__ import annotations
import contextlib
from typing import TYPE_CHECKING
from .base import BaseHelper, is_all_element_same
from .frame_group import FrameGroup
from .image import Image
if TYPE_CHECKING:
    from ..analyzer import ScanInfoAnalyzer

class SlicePack(BaseHelper):
    """
    Dependencies:
        FrameGroup
        Image
        visu_pars

    Args:
        BaseHelper (_type_): _description_
    """
    def __init__(self, analobj: 'ScanInfoAnalyzer'):
        super().__init__()
        visu_pars = analobj.visu_pars
        
        fg_info = analobj.get("info_frame_group") or FrameGroup(analobj).get_info()
        img_info = analobj.get("info_image") or Image(analobj).get_info()
        if fg_info is None or fg_info['type'] is None:
            num_slice_packs = 1
            num_slices_each_pack = [visu_pars.get("VisuCoreFrameCount")]
            slice_distances_each_pack = [visu_pars.get("VisuCoreFrameThickness")] \
                if img_info['dim'] > 1 else []
        else:
            if visu_pars["VisuVersion"] == 1:
                parser = self._parse_legacy
            else:
                parser = self._parse_6to360
            
            num_slice_packs, num_slices_each_pack, slice_distances_each_pack = parser(visu_pars, fg_info)
            if len(slice_distances_each_pack):
                for i, d in enumerate(slice_distances_each_pack):
                    if d == 0:
                        slice_distances_each_pack[i] = visu_pars["VisuCoreFrameThickness"]
            if not len(num_slices_each_pack):
                num_slices_each_pack = [1]
    
        self.num_slice_packs = num_slice_packs
        self.num_slices_each_pack = num_slices_each_pack
        self.slice_distances_each_pack = slice_distances_each_pack
        
        disk_slice_order = visu_pars.get("VisuCoreDiskSliceOrder") or 'normal'
        self.is_reverse = 'reverse' in disk_slice_order
        if visu_pars["VisuVersion"] not in (1, 3, 4, 5):
            self._warn(f'Parameters with current Visu Version has not been tested: v{visu_pars["VisuVersion"]}')
                    
    def _parse_legacy(self, visu_pars, fg_info):
        """
        Parses slice description for legacy cases, PV version < 6.
        This function calculates the number of slice packs, the number of slices in each pack,
        and the slice distances for legacy cases.
        """
        num_slice_packs = 1
        with contextlib.suppress(AttributeError):
            phase_enc_dir = visu_pars["VisuAcqImagePhaseEncDir"]
            phase_enc_dir = [phase_enc_dir[0]] if is_all_element_same(phase_enc_dir) else phase_enc_dir
            num_slice_packs = len(phase_enc_dir)

        shape = fg_info['shape']
        num_slices_each_pack = []
        with contextlib.suppress(ValueError):
            slice_fid = fg_info['id'].index('FG_SLICE')
            if num_slice_packs > 1:
                num_slices_each_pack = [int(shape[slice_fid]/num_slice_packs) for _ in range(num_slice_packs)]
            else:
                num_slices_each_pack = [shape[slice_fid]]

        slice_fg = [fg for fg in fg_info['id'] if 'slice' in fg.lower()]
        if len(slice_fg):
            if num_slice_packs > 1:
                num_slices_each_pack.extend(
                    int(shape[0] / num_slice_packs)
                    for _ in range(num_slice_packs)
                )
            else:
                num_slices_each_pack.append(shape[0])
        slice_distances_each_pack = [visu_pars["VisuCoreFrameThickness"] for _ in range(num_slice_packs)]
        return num_slice_packs, num_slices_each_pack, slice_distances_each_pack
    
    def _parse_6to360(self, visu_pars, fg_info):
        """
        Parses slice description for cases with PV version 6 to 360 slices.
        This function calculates the number of slice packs, the number of slices in each pack,
        and the slice distances for cases with 6 to 360 slices.
        """
        slice_packs_def = visu_pars.get("VisuCoreSlicePacksDef")
        num_slice_packs = slice_packs_def[0][1] if slice_packs_def else 1
        slices_desc_in_pack = visu_pars.get("VisuCoreSlicePacksSlices")
        slice_distance = visu_pars.get("VisuCoreSlicePacksSliceDist")
        slice_fg = [fg for fg in fg_info['id'] if 'slice' in fg.lower()]
        
        slice_distances_each_pack = []
        if len(slice_fg):
            if slices_desc_in_pack:
                num_slices_each_pack = [slices_desc_in_pack[0][1] for _ in range(num_slice_packs)]
            else:
                num_slices_each_pack = [1]
            if isinstance(slice_distance, list):
                slice_distances_each_pack.extend([slice_distance[0] for _ in range(num_slice_packs)])
            elif isinstance(slice_distance, (int, float)):
                slice_distances_each_pack.extend([slice_distance for _ in range(num_slice_packs)])
            else:
                self._warn("Not supported data type for Slice Distance")
        else:
            num_slices_each_pack = [1]
            slice_distances_each_pack = [visu_pars["VisuCoreFrameThickness"]]
        return num_slice_packs, num_slices_each_pack, slice_distances_each_pack

    def get_info(self):
        return {
            'num_slice_packs': self.num_slice_packs,
            'num_slices_each_pack': self.num_slices_each_pack,
            'slice_distances_each_pack': self.slice_distances_each_pack,
            'slice_distance_unit': 'mm',
            'reverse_slice_order': self.is_reverse,
            'warns': self.warns
        }       