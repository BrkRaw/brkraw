from __future__ import annotations

from typing import Any, cast, TYPE_CHECKING, Dict, Optional, Union
from pathlib import Path
import logging
from ....specs.remapper import load_spec, map_parameters
from ....specs.remapper.validator import validate_spec
from ....resolver.helpers import get_file, get_reco, strip_comment
from ....resolver.shape import resolve_frame_group


if TYPE_CHECKING:
    from ..types import ScanLoader

logger = logging.getLogger(__name__)


def frame_axes(scan: "ScanLoader", reco_id: int) -> Optional[str]:
    """Frame axes of a reco as "name(size), ..." (e.g. "echo(2), cycle(3)"), or None.

    Names follow brkraw's shape rule: the ParaVision frame group id without
    "<>" and "FG_", lowercased (FG_ECHO -> echo). The slice group is not a
    frame axis (it becomes the third spatial axis) and is left out.
    """
    try:
        visu_pars = get_file(get_reco(scan, reco_id), "visu_pars")
        fg_info = resolve_frame_group(visu_pars)
    except Exception:
        return None
    if not fg_info:
        return None
    parts = []
    for raw_id, size in zip(fg_info.get("id", []), fg_info.get("shape", [])):
        name = strip_comment(raw_id).replace("FG_", "").strip().lower()
        if name == "slice":
            continue
        parts.append(f"{name}({int(size)})")
    return ", ".join(parts) if parts else None


def resolve(
    scan: "ScanLoader",
    *,
    spec: Optional[Dict[str, Any]] = None,
    transforms: Optional[Dict[str, Any]] = None,
    spec_source: Optional[Union[str, Path]] = None,
    spec_filename: Optional[str] = None,
    validate: bool = True,
) -> Dict[str, Any]:
    """Resolve scan-level metadata using a remapper spec.

    The spec/transform sources are resolved in the following priority order:
    1) ``spec``/``transforms`` mappings passed directly.
    2) ``spec_source``.
    3) Package default ``scan.yaml``, optionally overridden by ``spec_filename``.

    Args:
        scan: ScanLoader instance to resolve metadata from.
        spec: Spec mapping to use directly (highest priority).
        transforms: Transform mapping to use with ``spec``.
        spec_source: Path for a YAML spec.
        spec_filename: Package-relative spec filename (default ``scan.yaml``).
        validate: When True, validate the spec before mapping.

    Returns:
        A dictionary of resolved scan metadata.
    """
    scan = cast("ScanLoader", scan)

    if spec is not None:
        spec_data = spec
        transforms_data = transforms or {}
        if validate:
            validate_spec(spec_data)
    elif spec_source is not None:
        spec_data, transforms_data = load_spec(
            spec_source,
            validate=validate,
        )
    else:
        spec_file = Path(__file__).with_name(spec_filename or "scan.yaml")
        spec_data, transforms_data = load_spec(
            spec_file,
            validate=validate,
        )
    results = map_parameters(scan, spec_data, transforms_data)
    if len(scan.avail):
        results['Reco(s)'] = {}
        for reco_id in scan.avail.keys():
            reco_spec = {
                "Type": {
                    "sources": [
                        {
                            "file": "visu_pars",
                            "key": "VisuCoreFrameType",
                            "reco_id": reco_id,
                        }
                    ]
                }
            }
            try:
                results["Reco(s)"][reco_id] = map_parameters(scan, reco_spec)
                axes = frame_axes(scan, reco_id)
                if axes:
                    results["Reco(s)"][reco_id]["Frame axes"] = axes
            except (FileNotFoundError, AttributeError) as exc:
                logger.warning(
                    "visu_pars missing for scan %s reco %s; skipping reco entry: %s",
                    getattr(scan, "scan_id", "unknown"),
                    reco_id,
                    exc,
                )
    return results
