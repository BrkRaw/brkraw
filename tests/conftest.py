import os
import pytest
import subprocess
from pathlib import Path
from brkraw.api.pvobj import PvStudy
from brkraw import setup_logging

def pytest_configure(config):
    setup_logging(path=Path(__file__).parent / 'logging.yaml')

# temporary dataset function
def get_dataset(local: bool):
    dataset = {}
    dset_idx = 0
    if local:
        dset_path = Path(__file__).parents[2] / 'brkraw-dataset_local'
    else:
        subprocess.check_call(["git", "clone", "https://github.com/BrkRaw/brkraw-dataset.git"])
        dset_path = Path(__file__).parent / 'brkraw-dataset'
    for path, _, files in os.walk(dset_path):
        for f in files:
            if f.endswith('.zip'):
                pvobj = PvStudy(Path(path) / f)
                dataset[dset_idx] = pvobj
                dset_idx += 1
    return dataset

@pytest.fixture(scope='package')
def dataset():
    return get_dataset(True)