# def test_loading(dataset):
#     scan_contents = ['method', 'acqp']
#     reco_contents = ['2dseq', 'visu_pars', 'reco']

#     for v, subset in dataset.items():
#         print(f'- v{v}:')
#         for fname, rawobj in subset.items():
#             print(f' + testing {fname}')
#             for scan_id in rawobj.avail:
#                 scanobj = rawobj.get_scan(scan_id)
#                 failed = sum([int(f in scan_contents) for f in scanobj._contents['files']]) < len(scan_contents)
#                 if failed:
#                     print(f'   - [{scan_id}] object does not contain all {scan_contents}')
#                 else:
#                     for reco_id in scanobj.avail:
#                         recoobj = scanobj.get_reco(reco_id)
#                         failed = sum([int(f in reco_contents) for f in recoobj.contents['files']]) < len(reco_contents)
#                         if failed:
#                             print(f'  - [{scan_id}][{reco_id}] object does not contain all {reco_contents}')
