"""Typed result dataclasses for Winston-Lutz and CatPhan analysis — the cache
return types and Simple→Advanced hand-off payloads.

Designed to be:
- **Frozen** (immutable) — safe for ``@st.cache_data``
- **Picklable** — only primitives, dicts, and lists of primitives
- **Self-contained** — Advanced mode tabs can render fully from these objects
  without needing the live pylinac object (which is expensive to load and not
  reliably picklable). The only exception is plot overlays which need the live
  object for ``images[i].plot()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class WLAnalysisResult:
    """Immutable Winston-Lutz analysis result.

    Attributes:
        machine_id: Machine key (e.g. ``"LA2"``).
        runfolder_path: Absolute path to the analysed DICOM runfolder.
        session_date: ISO 8601 date string (from DICOM ``AcquisitionDate``).
        summary: Dict of the 24 named-cell metric values (flat).
        image_details: List of per-image dicts (from pylinac's ``image_details``).
        image_keys: Parallel list of pylinac axis keys (e.g. ``["G0B0P0", ...]``).
        deviation_vs_gantry: Precomputed Plotly-ready scatter data:
            ``{"x": [...], "y": [...], "text": [...]}``.
        bb_xy_scatter: Precomputed Plotly-ready scatter data:
            ``{"x": [...], "y": [...], "color": [...]}``.
        distance_histogram: Precomputed Plotly-ready histogram data:
            ``{"values": [...]}``.
        params_used: Dict of the pylinac ``analyze()`` params used for this run
            (for "Analysed with: ..." display and sidebar repopulation).
    """

    # Identity
    machine_id: str
    runfolder_path: str
    session_date: str
    # Summary (the 24 named-cell values)
    summary: dict[str, float | int | str]
    # Per-image data (parallel arrays)
    image_details: list[dict[str, Any]]
    image_keys: list[str]
    # Plotly-ready arrays (precomputed once, reused on every render)
    deviation_vs_gantry: dict[str, list[Any]] = field(default_factory=dict)
    bb_xy_scatter: dict[str, list[Any]] = field(default_factory=dict)
    distance_histogram: dict[str, list[Any]] = field(default_factory=dict)
    # Parameters used (for display + sidebar repopulation)
    params_used: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CatPhanAnalysisResult:
    """Immutable CatPhan 504 analysis result (design D5).

    Mirrors :class:`WLAnalysisResult` in structure: identity fields, a flat
    summary dict (the 19 named-cell values), per-CTP-module detail dicts, and
    precomputed Plotly-ready arrays.

    Attributes:
        machine_id: Machine key (e.g. ``"LA2"``).
        runfolder_path: Absolute path to the analysed DICOM runfolder.
        session_date: ISO 8601 date string (from DICOM ``AcquisitionDate``).
        summary: Dict of the 18 named-cell metric values (flat, keyed by
            named-cell name).
        ctp404: Per-module detail dict from pylinac (HU linearity, geometry,
            thickness).
        ctp486: Per-module detail dict (uniformity ROIs, indices, NPS).
        ctp528: Per-module detail dict (MTF table, ROI settings).
        ctp515: Per-module detail dict (low contrast ROIs, num_rois_seen).
        mtf_curve: Precomputed Plotly-ready MTF data:
            ``{"x": [10, 20, ..., 90], "y": [lp/mm values]}``.
        hu_linearity_scatter: Precomputed Plotly-ready scatter data:
            ``{"nominal": [...], "measured": [...], "names": [...]}``.
        params_used: Dict of the pylinac ``analyze()`` params used for this run.
    """

    # Identity
    machine_id: str
    runfolder_path: str
    session_date: str
    # Summary (the 18 named-cell values, flat)
    summary: dict[str, float | int | str | bool]
    # Per-CTP-module detail dicts (from results_data(as_dict=True))
    ctp404: dict[str, Any]
    ctp486: dict[str, Any]
    ctp528: dict[str, Any]
    ctp515: dict[str, Any]
    # Plotly-ready arrays (precomputed)
    mtf_curve: dict[str, list[Any]] = field(default_factory=dict)
    hu_linearity_scatter: dict[str, list[Any]] = field(default_factory=dict)
    # Parameters used (for display + sidebar repopulation)
    params_used: dict[str, Any] = field(default_factory=dict)


__all__ = ["CatPhanAnalysisResult", "WLAnalysisResult"]
