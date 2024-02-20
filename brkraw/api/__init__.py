import pvobj

__all__ = ['pvobj', 'BrukerLoader']

class BrukerLoader:
    def __init__(self, path):
        self._pvobj = pvobj.PvDataset(path)
