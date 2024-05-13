import logging

def test_loaddata(dataset):
    logging.info('test')
    for i, pvobj in dataset.items():
        assert len(pvobj.avail) > 0
        for scan_id in pvobj.avail:
            try:
                pvscan = pvobj.get_scan(scan_id)
                logging.info("Scan loaded for %s", pvscan.path[1])
            except:
                raise AssertionError