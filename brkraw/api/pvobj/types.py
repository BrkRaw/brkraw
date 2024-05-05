from io import BufferedReader
from zipfile import ZipExtFile
from typing import Type
from typing import Union
from .pvscan import PvScan
from .pvstudy import PvStudy
from .pvreco import PvReco
from .pvfiles import PvFiles
from .parameters import Parameter


PvFileBuffer = Type[Union[BufferedReader, ZipExtFile]]

PvStudyType = Type[PvStudy]

PvScanType = Type[PvScan]

PvRecoType = Type[PvReco]

PvFilesType = Type[PvFiles]

ParameterType = Type[Parameter]

PvObjType = Type[Union[PvScan, PvReco, PvFiles]]