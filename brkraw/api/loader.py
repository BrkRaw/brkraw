from .pvobj import PvDataset
from ..config import ConfigManager

class BrukerLoader:
    def __init__(self, path):
        self._pvobj = PvDataset(path, **ConfigManager().get('spec'))
