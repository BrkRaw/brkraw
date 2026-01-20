import logging
from typing import cast
from brkraw.apps.loader.info import scan as resolve_scan
from brkraw.apps.loader.types import ScanLoader


class DummyVisuPars:
    def __init__(self, frame_type: str):
        self.VisuCoreFrameType = frame_type


class DummyReco:
    def __init__(self, reco_id: int, visu_pars: DummyVisuPars):
        self.reco_id = reco_id
        self.visu_pars = visu_pars


class MissingVisuReco:
    def __init__(self, reco_id: int):
        self.reco_id = reco_id

    @property
    def visu_pars(self):
        raise AttributeError("visu_pars")


class DummyScan:
    def __init__(self, recos):
        self.recos = recos
        self.scan_id = 99

    @property
    def avail(self):
        return self.recos

    def get_reco(self, reco_id: int):
        return self.recos[reco_id]


def test_resolve_skips_reco_without_visu_pars(caplog):
    scan = DummyScan(
        {
            1: DummyReco(1, DummyVisuPars("frame_type")),
            2: MissingVisuReco(2),
        }
    )

    caplog.set_level(logging.WARNING, logger="brkraw")
    result = resolve_scan(cast(ScanLoader, scan), spec={}, transforms={}, validate=False)

    assert result["Reco(s)"][1]["Type"] == "frame_type"
    assert 2 not in result["Reco(s)"]
    warnings = [record.message for record in caplog.records if record.levelno == logging.WARNING]
    assert any("visu_pars missing" in msg for msg in warnings)
