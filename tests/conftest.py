# import pytest
# import re
# from pathlib import Path
# from brkraw.api.pvobj import PvStudy
# from pprint import pprint

# # test functions
# def get_version(raw):
#     ptrn = r'^[a-zA-Z]*[ -]?(?P<version>\d+\.\d+(?:\.\d+)?)'
#     for scan_id in raw.avail:
#         pvscan = raw.get_scan(scan_id)
#         if version := pvscan.acqp.get('ACQ_sw_version'):
#             if matched := re.match(ptrn, version):
#                 return matched.groupdict()['version']

# def check_contents(path: Path):
#     if path.is_dir():
#         if any([e.is_dir() and e.name.isdigit() for e in path.iterdir()]):
#             return PvStudy(path)
#         for e in path.iterdir():
#             return check_contents(e)
#     elif path.is_file():
#         if path.name.endswith('.zip'):
#             return PvStudy(path)

# @pytest.fixture
# def dataset():
#     return get_dataset()

# def get_dataset():
#     dataset_path = Path('/mnt/nfs/active/Xoani_Lee_Package-dev/playground/brkraw_dev')
    
#     dataset = {}
#     for contents in dataset_path.iterdir():
#         if raw := check_contents(contents):
#             if version := get_version(raw):
#                 if version not in dataset.keys():
#                     dataset[version] = {}
#                 dataset[version][raw.path.name] = raw
#     return dataset