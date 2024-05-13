import logging
from brkraw.api.data import Study

def test_data_init(dataset):
    for i, pvobj in dataset.items():
        # if i == 0:
        studyobj = Study(pvobj.path)
        logging.info(studyobj.info['header']['date'])