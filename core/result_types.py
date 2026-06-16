"""Typed result dataclass for Winston-Lutz analysis — the cache return type and
Simple→Advanced hand-off payload.

Designed to be:
- **Frozen** (hashable) — safe for ``@st.cache_data``
- **Picklable** — only primitives, dicts, and lists of primitives
- **Self-contained** — Advanced mode tabs can render fully from this object
  without needing the live pylinac ``WinstonLutz`` object (which is expensive
  to load and not reliably picklable). The only exception is the Detection
  overlay tab, which needs the live object for ``images[i].plot()``.
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


__all__ = ["WLAnalysisResult"]
