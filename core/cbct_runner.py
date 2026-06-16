"""Thin wrapper around ``pylinac.CatPhan504`` — the CatPhan 504 CBCT analysis runner.

This module **isolates all pylinac API calls** so that future pylinac major
versions require changes only here (mirroring :mod:`core.wl_runner`).

The pylinac ``CatPhan504.analyze()`` parameter names differ from the
spec/config names in two cases; the mapping is handled in
:func:`_build_analyze_kwargs`:

    - ``slice_thickness_tolerance`` (config) → ``thickness_tolerance`` (pylinac)
    - ``minimum_rois_seen`` (config)        → ``low_contrast_tolerance`` (pylinac)

Public API:
    - :func:`run_cbct_analysis`
    - :func:`load_cbct_object`  (lazy init for Advanced mode overlays)
    - :data:`ANALYZE_PARAMS`
"""

from __future__ import annotations

import logging
from typing import Any

from core.result_types import CatPhanAnalysisResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# pylinac wrapper
# ---------------------------------------------------------------------------

#: The 10 CatPhan ``analyze()`` parameters we expose in the UI (spec D4).
#: Note: the dict-typed ``expected_hu_values`` stays config-only (not in the sidebar).
ANALYZE_PARAMS: tuple[str, ...] = (
    "hu_tolerance",
    "scaling_tolerance",
    "slice_thickness_tolerance",
    "thickness_slice_straddle",
    "x_adjustment",
    "y_adjustment",
    "angle_adjustment",
    "roi_size_factor",
    "scaling_factor",
    "minimum_rois_seen",
)

#: Mapping from our canonical config/UI parameter names to pylinac's
#: ``analyze()`` parameter names. Only the mismatches are listed; names that
#: match pass through directly.
_PYLINAC_PARAM_MAP: dict[str, str] = {
    "slice_thickness_tolerance": "thickness_tolerance",
    "minimum_rois_seen": "low_contrast_tolerance",
}


def _build_analyze_kwargs(params: dict[str, Any]) -> dict[str, Any]:
    """Filter ``params`` to only the keys pylinac's ``analyze()`` accepts.

    Drops ``expected_hu_values`` if it is ``None`` (pylinac default).
    Maps our canonical config names to pylinac's actual parameter names via
    :data:`_PYLINAC_PARAM_MAP`.
    """
    kwargs: dict[str, Any] = {}
    for key in ANALYZE_PARAMS:
        if key not in params:
            continue
        val = params[key]
        if val is None:
            continue  # let pylinac use its default
        pylinac_key = _PYLINAC_PARAM_MAP.get(key, key)
        kwargs[pylinac_key] = val

    # expected_hu_values is config-only; pass through if present and not None
    ehv = params.get("expected_hu_values")
    if ehv is not None:
        kwargs["expected_hu_values"] = ehv

    return kwargs


# ---------------------------------------------------------------------------
# Summary mapping (the 18 metric named cells)
# ---------------------------------------------------------------------------


def _extract_mtf_value(mtf_lp_mm: dict[str, Any], percentage: int) -> float:
    """Extract a single MTF lp/mm value for a given percentage.

    pylinac serialises mtf_lp_mm with string keys (``"50"``, ``"90"``).
    """
    val = mtf_lp_mm.get(str(percentage), 0.0)
    return float(val)


def _build_summary(
    machine_id: str,
    session_date: str,
    data: dict[str, Any],
) -> dict[str, float | int | str | bool]:
    """Build the flat summary dict keyed by named-cell name.

    Pulls the 18 metric values from the appropriate nested dicts:
    ``ctp404.measured_slice_thickness_mm``, ``ctp486.uniformity_index``, etc.
    The 19th cell (``template_version``) is added by the excel writer.
    """
    ctp404 = data.get("ctp404", {})
    ctp486 = data.get("ctp486", {})
    ctp528 = data.get("ctp528", {})
    ctp515 = data.get("ctp515", {})
    mtf_lp_mm = ctp528.get("mtf_lp_mm", {})

    summary: dict[str, float | int | str | bool] = {
        # Session metadata (3)
        "machine_name": machine_id,
        "session_date": session_date,
        "num_images": data.get("num_images", 0),
        # Pass/fail flags (4)
        "hu_linearity_passed": bool(ctp404.get("hu_linearity_passed", False)),
        "geometry_passed": bool(ctp404.get("geometry_passed", False)),
        "uniformity_passed": bool(ctp486.get("passed", False)),
        "thickness_passed": bool(ctp404.get("thickness_passed", False)),
        # Geometry (2)
        "measured_slice_thickness_mm": float(ctp404.get("measured_slice_thickness_mm", 0.0)),
        "avg_line_distance_mm": float(ctp404.get("avg_line_distance_mm", 0.0)),
        # Uniformity (2)
        "uniformity_index": float(ctp486.get("uniformity_index", 0.0)),
        "integral_non_uniformity": float(ctp486.get("integral_non_uniformity", 0.0)),
        # Contrast (2)
        "low_contrast_visibility": float(ctp404.get("low_contrast_visibility", 0.0)),
        "num_rois_seen": int(ctp515.get("num_rois_seen", 0)),
        # Resolution (2)
        "mtf_50_lp_mm": _extract_mtf_value(mtf_lp_mm, 50),
        "mtf_90_lp_mm": _extract_mtf_value(mtf_lp_mm, 90),
        # NPS (2)
        "nps_avg_power": float(ctp486.get("nps_avg_power", 0.0)),
        "nps_max_freq": float(ctp486.get("nps_max_freq", 0.0)),
        # Orientation (1)
        "catphan_roll_deg": float(data.get("catphan_roll_deg", 0.0)),
    }
    return summary


# ---------------------------------------------------------------------------
# Plotly-ready array precomputation
# ---------------------------------------------------------------------------


def _precompute_mtf_curve(ctp528: dict[str, Any]) -> dict[str, list[Any]]:
    """Build the Plotly-ready MTF curve from ``ctp528.mtf_lp_mm``.

    Returns:
        ``{"x": [10, 20, ..., 90], "y": [lp/mm values]}``
    """
    mtf_lp_mm = ctp528.get("mtf_lp_mm", {})
    x: list[Any] = []
    y: list[Any] = []
    for pct in range(10, 91, 10):
        x.append(pct)
        y.append(_extract_mtf_value(mtf_lp_mm, pct))
    return {"x": x, "y": y}


def _precompute_hu_linearity_scatter(ctp404: dict[str, Any]) -> dict[str, list[Any]]:
    """Build the Plotly-ready HU linearity scatter from ``ctp404.hu_rois``.

    Returns:
        ``{"nominal": [...], "measured": [...], "names": [...]}``
    """
    hu_rois = ctp404.get("hu_rois", {})
    names: list[Any] = []
    nominal: list[Any] = []
    measured: list[Any] = []
    for _name, roi in hu_rois.items():
        names.append(roi.get("name", _name))
        nominal.append(float(roi.get("nominal_value", 0.0)))
        measured.append(float(roi.get("value", 0.0)))
    return {"nominal": nominal, "measured": measured, "names": names}


# ---------------------------------------------------------------------------
# Session date extraction
# ---------------------------------------------------------------------------


def _extract_session_date(data: dict[str, Any], cbct: Any) -> str:
    """Extract the session date from pylinac data or DICOM metadata.

    Tries DICOM ``AcquisitionDate`` from the first image, falls back to
    ``date_of_analysis`` from pylinac, then "unknown".
    """
    date_str = data.get("date_of_analysis", "")
    if date_str:
        return str(date_str)[:10]
    try:
        if hasattr(cbct, "dicom_stack") and cbct.dicom_stack is not None:
            metadata = cbct.dicom_stack.metadata
            acquisition_date = metadata.get("AcquisitionDate", "")
            if acquisition_date:
                return str(acquisition_date)
    except Exception:
        pass
    return "unknown"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_cbct_analysis(
    machine_id: str,
    runfolder_path: str,
    hu_tolerance: float,
    scaling_tolerance: float,
    slice_thickness_tolerance: float,
    thickness_slice_straddle: str | int,
    x_adjustment: float,
    y_adjustment: float,
    angle_adjustment: float,
    roi_size_factor: float,
    scaling_factor: float,
    minimum_rois_seen: int,
    dicom_file_count: int = 0,  # noqa: ARG001 — cache-key invalidation only
    runfolder_mtime: float = 0.0,  # noqa: ARG001 — cache-key invalidation only
    expected_hu_values: dict[str, float] | None = None,
) -> CatPhanAnalysisResult:
    """Run pylinac CatPhan 504 analysis and return a :class:`CatPhanAnalysisResult`.

    All pylinac API interaction is isolated here. The result is a frozen,
    picklable dataclass safe for ``@st.cache_data``.

    Args:
        machine_id: Machine key (e.g. ``"LA2"``).
        runfolder_path: Absolute path to the DICOM runfolder.
        hu_tolerance: HU tolerance for both HU uniformity and linearity.
        scaling_tolerance: Scaling tolerance in mm (geometric nodes).
        slice_thickness_tolerance: Thickness tolerance in mm (mapped to
            pylinac's ``thickness_tolerance``).
        thickness_slice_straddle: ``'auto'`` or an integer.
        x_adjustment: Fine-tuning x-coordinate offset in mm.
        y_adjustment: Fine-tuning y-coordinate offset in mm.
        angle_adjustment: Fine-tuning angle offset in degrees.
        roi_size_factor: ROI size scaling factor.
        scaling_factor: Phantom magnification scaling factor.
        minimum_rois_seen: Number of low-contrast ROIs needed to pass (mapped
            to pylinac's ``low_contrast_tolerance``).
        dicom_file_count: Cache-key invalidation (not used in computation).
        runfolder_mtime: Cache-key invalidation (not used in computation).
        expected_hu_values: Optional dict of expected HU values (config-only).

    Returns:
        A :class:`CatPhanAnalysisResult`.
    """
    from pylinac import CatPhan504

    params = {
        "hu_tolerance": hu_tolerance,
        "scaling_tolerance": scaling_tolerance,
        "slice_thickness_tolerance": slice_thickness_tolerance,
        "thickness_slice_straddle": thickness_slice_straddle,
        "x_adjustment": x_adjustment,
        "y_adjustment": y_adjustment,
        "angle_adjustment": angle_adjustment,
        "roi_size_factor": roi_size_factor,
        "scaling_factor": scaling_factor,
        "minimum_rois_seen": minimum_rois_seen,
        "expected_hu_values": expected_hu_values,
    }
    analyze_kwargs = _build_analyze_kwargs(params)

    logger.info(
        "Running CatPhan 504 analysis for %s on %s with %s",
        machine_id,
        runfolder_path,
        analyze_kwargs,
    )

    cbct = CatPhan504(runfolder_path)
    cbct.analyze(**analyze_kwargs)

    # Extract results as dict
    data = cbct.results_data(as_dict=True)

    # Build the flat summary dict
    session_date = _extract_session_date(data, cbct)
    summary = _build_summary(machine_id, session_date, data)

    # Extract per-CTP-module detail dicts
    ctp404 = dict(data.get("ctp404", {}))
    ctp486 = dict(data.get("ctp486", {}))
    ctp528 = dict(data.get("ctp528", {}))
    ctp515 = dict(data.get("ctp515", {}))

    # Precompute Plotly-ready arrays
    mtf_curve = _precompute_mtf_curve(ctp528)
    hu_linearity_scatter = _precompute_hu_linearity_scatter(ctp404)

    return CatPhanAnalysisResult(
        machine_id=machine_id,
        runfolder_path=runfolder_path,
        session_date=session_date,
        summary=summary,
        ctp404=ctp404,
        ctp486=ctp486,
        ctp528=ctp528,
        ctp515=ctp515,
        mtf_curve=mtf_curve,
        hu_linearity_scatter=hu_linearity_scatter,
        params_used=params,
    )


def load_cbct_object(runfolder_path: str, params: dict[str, Any]) -> Any:
    """Load and analyse a pylinac ``CatPhan504`` object for Advanced mode.

    Used by the per-CTP tabs (lazy init). Returns the live object (not
    picklable) so callers can call ``cbct.plot_analyzed_subimage(...)``.

    Args:
        runfolder_path: Absolute path to the DICOM runfolder.
        params: Dict of analyze parameters (from
            ``CatPhanAnalysisResult.params_used``).
    """
    from pylinac import CatPhan504

    cbct = CatPhan504(runfolder_path)
    cbct.analyze(**_build_analyze_kwargs(params))
    return cbct


__all__ = [
    "ANALYZE_PARAMS",
    "load_cbct_object",
    "run_cbct_analysis",
]
