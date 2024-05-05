from typing import Type, Literal, Optional, Union
from .plugin import ToNiftiPlugin
from .scan import ScanToNifti
from .study import StudyToNifti


ToNiftiPluginType = Type[ToNiftiPlugin]

ScanToNiftiType = Type[ScanToNifti]

StudyToNiftiType = Type[StudyToNifti]

ToNiftiObject = Type[Union[ToNiftiPlugin, ScanToNifti, StudyToNifti]]

ScaleMode = Type[Optional[Literal['header', 'apply']]]

__all__ = ['ToNiftiPlugin', 'ScanToNifti', 'StudyToNifti']

