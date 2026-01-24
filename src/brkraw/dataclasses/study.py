
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Mapping, Optional, Union

from ..core.fs import DatasetFS
from .node import DatasetNode
from .scan import Scan

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..apps.loader.types import ScanLoader


@dataclass
class LazyScan:
    """Lightweight lazy Scan proxy.

    This defers `Scan.from_fs(...)` until the scan is actually accessed.
    It implements attribute forwarding so it can be used where a Scan is expected.
    """

    fs: DatasetFS
    scan_id: int
    scan_root: str
    _scan: Optional[Scan] = field(default=None, init=False, repr=False)

    def materialize(self) -> Scan:
        if self._scan is None:
            logger.debug(
                "Materializing Scan.from_fs for scan_id=%s scan_root=%s",
                self.scan_id,
                self.scan_root,
            )
            self._scan = Scan.from_fs(self.fs, self.scan_id, self.scan_root)
        return self._scan

    def __getattr__(self, name: str):
        # Delegate unknown attributes to the underlying Scan.
        return getattr(self.materialize(), name)

    def __repr__(self) -> str:
        if self._scan is None:
            return f"LazyScan(id={self.scan_id} root='{self.scan_root}')"
        return repr(self._scan)


@dataclass
class Study(DatasetNode):
    fs: DatasetFS
    relroot: str = ""
    scans: Dict[int, Union[Scan, LazyScan, "ScanLoader"]] = field(default_factory=dict)
    _cache: Dict[str, object] = field(default_factory=dict, init=False, repr=False)

    @classmethod
    def from_path(cls, path: Union[str, Path]) -> "Study":
        """Load a study rooted at path, preferring bottom-up discovery."""
        fs = DatasetFS.from_path(path)
        found = cls.discover(fs)
        if not found:
            raise ValueError(f"No Paravision study found under {path}")

        anchor = fs.anchor
        if anchor:
            for study in found:
                if study.relroot == anchor:
                    return study

        if len(found) == 1:
            return found[0]

        raise ValueError(
            f"Multiple studies found under {path}; "
            f"cannot choose automatically ({[s.relroot for s in found]})"
        )

    @classmethod
    def discover(cls, fs: DatasetFS) -> List["Study"]:
        """Bottom-up discovery using reco markers (2dseq + visu_pars).

        Notes:
            Discovery is I/O bound on large studies or slow filesystems.
            We minimize filesystem calls by:
            - disabling per-directory sorting in fs.walk
            - avoiding per-directory set() allocations
            - caching scan-level existence checks (method/acqp)
        """
        studies: Dict[str, Study] = {}
        scan_ok_cache: Dict[str, bool] = {}

        # Order does not matter for discovery; avoid sorting costs in the walker.
        for dirpath, _dirnames, filenames in fs.walk(sort_entries=False):
            rel = fs.strip_anchor(dirpath)

            # Fast membership checks without allocating set(filenames).
            if "2dseq" not in filenames or "visu_pars" not in filenames:
                continue

            parts = [p for p in rel.split("/") if p]
            if "pdata" not in parts:
                continue
            pdata_idx = parts.index("pdata")
            if pdata_idx < 1 or pdata_idx + 1 >= len(parts):
                continue

            scan_id_part = parts[pdata_idx - 1]
            if not scan_id_part.isdigit():
                continue
            scan_id = int(scan_id_part)

            reco_id_part = parts[pdata_idx + 1]
            if not reco_id_part.isdigit():
                continue

            scan_root = "/".join(parts[:pdata_idx])
            study_root = "/".join(parts[:pdata_idx - 1])

            # Validate scan-level markers once per scan_root.
            ok = scan_ok_cache.get(scan_root)
            if ok is None:
                ok = fs.exists(f"{scan_root}/method") and fs.exists(f"{scan_root}/acqp")
                scan_ok_cache[scan_root] = ok
            if not ok:
                continue

            # Validate reco file. In most PV layouts, `reco` lives in the same pdata/<reco_id> dir.
            # Prefer checking the listing we already have, fall back to exists() for safety.
            if "reco" not in filenames and not fs.exists(f"{rel}/reco"):
                continue

            study = studies.get(study_root)
            if study is None:
                study = cls(fs=fs, relroot=study_root, scans={})
                studies[study_root] = study

            if scan_id not in study.scans:
                # Defer Scan.from_fs(...) until the scan is actually accessed.
                study.scans[scan_id] = LazyScan(fs=fs, scan_id=scan_id, scan_root=scan_root)

        return [studies[k] for k in sorted(studies.keys())]

    @property
    def avail(self) -> Mapping[int, Union[Scan, LazyScan, "ScanLoader"]]:
        return {k: self.scans[k] for k in sorted(self.scans)}

    def get_scan(self, scan_id: int) -> Scan:
        obj = self.scans[scan_id]
        if isinstance(obj, LazyScan):
            # Materialize once, but keep the proxy stored in `self.scans`.
            # BrukerLoader binds helper methods (convert/get_affine/etc.) to the object
            # stored in `self.scans`. Replacing it with a raw Scan can drop those bindings.
            logger.debug("Accessing scan_id=%s via LazyScan proxy", scan_id)
            obj.materialize()
            return obj  # type: ignore[return-value]
        if isinstance(obj, Scan):
            return obj

        logger.debug("Accessing scan_id=%s with unexpected type=%r", scan_id, type(obj))
        try:
            scan = obj  # type: ignore[assignment]
            if isinstance(scan, Scan):
                return scan
        except Exception:
            logger.exception("Failed to resolve scan_id=%s to Scan", scan_id)

        raise TypeError(f"Scan {scan_id} is not loaded as a Scan (got {type(obj)!r})")

    @property
    def has_subject(self) -> bool:
        target = f"{self.relroot}/subject" if self.relroot else "subject"
        return self.fs.exists(target)

    def __repr__(self) -> str:
        root_label = self.relroot or self.fs.root.name
        mode = getattr(self.fs, "_mode", "dir")

        subject_part = ""
        try:
            subj = getattr(self, "subject")
            from ..core.parameters import Parameters  # local import to avoid cycle

            if isinstance(subj, Parameters):
                sid = getattr(subj, "SUBJECT_id", None)
                name = getattr(subj, "SUBJECT_name_string", None)
                study_name = getattr(subj, "SUBJECT_study_name", None)
                study_nr = getattr(subj, "SUBJECT_study_nr", None)
                bits = []
                if name is not None:
                    bits.append(f"name={name!r}")
                if sid is not None:
                    bits.append(f"id={sid}")
                if study_name is not None:
                    bits.append(f"study={study_name!r}")
                if study_nr is not None:
                    bits.append(f"nr={study_nr}")
                if bits:
                    subject_part = " subject(" + " ".join(bits) + ")"
        except Exception:
            subject_part = ""

        return f"Study(root='{root_label}' mode={mode}{subject_part})"
