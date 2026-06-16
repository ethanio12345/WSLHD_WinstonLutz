"""Thin wrapper around ``pylinac.WinstonLutz``.

This module **isolates all pylinac API calls** so that future pylinac major
versions require changes only here (per design D6 and the container-deployment
spec's pylinac version-pinning requirement).

Runfolder discovery utilities (``find_newest_runfolder``, ``count_dicoms``,
``runfolder_mtime``, ``list_runfolders``) now live in :mod:`core.runfolder`
and are re-exported here for backward compatibility.

Public API:
    - :func:`find_newest_runfolder`  (re-exported from core.runfolder)
    - :func:`count_dicoms`           (re-exported from core.runfolder)
    - :func:`runfolder_mtime`        (re-exported from core.runfolder)
    - :func:`list_runfolders`        (re-exported from core.runfolder)
    - :func:`run_wl_analysis`
    - :func:`load_wl_object`  (lazy init for Advanced mode Detection overlay)
"""

from __future__ import annotations

import logging
from typing import Any

from core.result_types import WLAnalysisResult
from core.runfolder import (  # re-exported for backward compatibility
    count_dicoms,
    find_newest_runfolder,
    list_runfolders,
    runfolder_mtime,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# pylinac wrapper
# ---------------------------------------------------------------------------

#: The 9 pylinac ``analyze()`` parameters we expose (matches design D6).
ANALYZE_PARAMS: tuple[str, ...] = (
    "bb_size_mm",
    "machine_scale",
    "low_density_bb",
    "open_field",
    "apply_virtual_shift",
    "snap_tolerance",
    "gantry_reference",
    "collimator_reference",
    "couch_reference",
)

#: Mapping from our canonical summary keys to pylinac's ``results_data(as_dict=True)`` keys.
#: pylinac appends ``_mm`` / ``_deg`` to some keys; we normalise to the bare metric name
#: that matches the xltx named-cell contract. For ``bb_shift_*``, pylinac returns a single
#: ``bb_shift_vector`` dict — we extract the x/y/z components.
_PYLINAC_KEY_MAP: dict[str, tuple[str, ...]] = {
    "num_total_images": ("num_total_images", "num_images"),
    "max_2d_cax_to_bb": ("max_2d_cax_to_bb_mm", "max_2d_cax_to_bb"),
    "median_2d_cax_to_bb": ("median_2d_cax_to_bb_mm", "median_2d_cax_to_bb"),
    "mean_2d_cax_to_bb": ("mean_2d_cax_to_bb_mm", "mean_2d_cax_to_bb"),
    "gantry_3d_iso": ("gantry_3d_iso_diameter_mm", "gantry_3d_iso"),
    "coll_2d_iso": ("coll_2d_iso_diameter_mm", "coll_2d_iso"),
    "couch_2d_iso": ("couch_2d_iso_diameter_mm", "couch_2d_iso"),
    "max_2d_cax_to_epid": ("max_2d_cax_to_epid_mm", "max_2d_cax_to_epid"),
    "median_2d_cax_to_epid": ("median_2d_cax_to_epid_mm", "median_2d_cax_to_epid"),
    "mean_2d_cax_to_epid": ("mean_2d_cax_to_epid_mm", "mean_2d_cax_to_epid"),
    "gantry_coll_3d_iso": ("gantry_coll_3d_iso_diameter_mm", "gantry_coll_3d_iso"),
    "max_gantry_rms": ("max_gantry_rms_deviation_mm", "max_gantry_rms"),
    "max_coll_rms": (
        "max_collimator_rms_deviation_mm",
        "max_coll_rms_deviation_mm",
        "max_coll_rms",
    ),
    "max_couch_rms": ("max_couch_rms_deviation_mm", "max_couch_rms"),
    "max_epid_rms": ("max_epid_rms_deviation_mm", "max_epid_rms"),
    "num_gantry_images": ("num_gantry_images",),
    "num_coll_images": ("num_coll_images", "num_collimator_images"),
    "num_couch_images": ("num_couch_images",),
    "num_gantry_coll_images": ("num_gantry_coll_images",),
}


def _resolve_metric(data: dict[str, Any], canonical: str) -> float | int | str:
    """Resolve a canonical metric name from pylinac's dict, trying mapped aliases."""
    for alias in _PYLINAC_KEY_MAP.get(canonical, (canonical,)):
        if alias in data:
            value: float | int | str = data[alias]
            return value
    logger.warning("Metric '%s' not found in pylinac results_data; using 0.0", canonical)
    return 0.0


def _build_analyze_kwargs(params: dict[str, Any]) -> dict[str, Any]:
    """Filter ``params`` to only the keys pylinac's ``analyze()`` accepts.

    Drops ``tolerance_mm`` (UI-only) and any ``None`` values (pylinac defaults).
    Converts ``machine_scale`` string to the pylinac enum.
    """
    from pylinac.winston_lutz import MachineScale  # local import: heavy module

    kwargs: dict[str, Any] = {}
    for key in ANALYZE_PARAMS:
        if key not in params:
            continue
        val = params[key]
        if val is None:
            continue  # let pylinac use its default
        if key == "machine_scale":
            kwargs[key] = MachineScale[val] if isinstance(val, str) else val
        else:
            kwargs[key] = val
    return kwargs


def _parse_axis_from_key(key: str, axis: str) -> float:
    """Extract a single axis value from an image key like ``G0.0B0.0P0.0``.

    Args:
        key: Image key in ``G{gantry}B{coll}P{couch}`` format.
        axis: One of ``"G"``, ``"B"``, ``"P"``.

    Returns:
        The float value for that axis, or 0.0 if not parseable.
    """
    import re

    match = re.search(rf"{axis}(-?[\d.]+)", key)
    return float(match.group(1)) if match else 0.0


def _precompute_plotly_arrays(
    image_details: list[dict[str, Any]],
    image_keys: list[str],
) -> tuple[dict[str, list[Any]], dict[str, list[Any]], dict[str, list[Any]]]:
    """Build the three Plotly-ready arrays from per-image details.

    pylinac's ``keyed_image_details`` does not include ``gantry_angle`` /
    ``collimator_angle`` / ``couch_angle`` as separate fields — the angles are
    encoded in the image key (``G0.0B0.0P0.0``).  CAX→BB X/Y components live in
    the nested ``cax2bb_vector`` dict.

    Returns:
        ``(deviation_vs_gantry, bb_xy_scatter, distance_histogram)``
    """
    dev_x: list[Any] = []  # gantry angles
    dev_y: list[Any] = []  # cax2bb distances
    dev_text: list[Any] = []  # image keys

    scatter_x: list[Any] = []  # CAX→BB X component
    scatter_y: list[Any] = []  # CAX→BB Y component
    scatter_color: list[Any] = []  # variable axis label

    hist_values: list[Any] = []  # all cax2bb distances

    for detail, key in zip(image_details, image_keys, strict=False):
        gantry = _parse_axis_from_key(key, "G")
        cax2bb = detail.get("cax2bb_distance", 0.0)

        dev_x.append(gantry)
        dev_y.append(cax2bb)
        dev_text.append(key)

        # CAX→BB vector components (pylinac nested dict with x/y/z keys)
        vec = detail.get("cax2bb_vector", {})
        if isinstance(vec, dict):
            scatter_x.append(vec.get("x", 0.0))
            scatter_y.append(vec.get("y", 0.0))
        else:
            scatter_x.append(0.0)
            scatter_y.append(0.0)
        scatter_color.append(detail.get("variable_axis", "None"))

        hist_values.append(cax2bb)

    deviation_vs_gantry = {"x": dev_x, "y": dev_y, "text": dev_text}
    bb_xy_scatter = {"x": scatter_x, "y": scatter_y, "color": scatter_color}
    distance_histogram = {"values": hist_values}
    return deviation_vs_gantry, bb_xy_scatter, distance_histogram


def _extract_session_date(data: dict[str, Any], wl: Any) -> str:
    """Extract the session date from DICOM metadata or pylinac data.

    Tries DICOM ``AcquisitionDate`` from the first image, falls back to
    ``date_of_analysis`` from pylinac, then "unknown".
    """
    # Try pylinac's date_of_analysis first (always present)
    date_str = data.get("date_of_analysis", "")
    if date_str:
        # pylinac returns ISO datetime; extract date part
        return str(date_str)[:10]
    # Fall back to DICOM metadata if available
    try:
        if wl.images:
            img = wl.images[0]
            acquisition_date = getattr(img, "acquisition_date", None)
            if acquisition_date:
                return str(acquisition_date)
    except Exception:
        pass
    return "unknown"


def run_wl_analysis(
    machine_id: str,
    runfolder_path: str,
    bb_size_mm: float,
    machine_scale: str,
    low_density_bb: bool = False,
    open_field: bool = False,
    apply_virtual_shift: bool = False,
    snap_tolerance: float | None = None,
    gantry_reference: float | None = None,
    collimator_reference: float | None = None,
    couch_reference: float | None = None,
    dicom_file_count: int = 0,  # noqa: ARG001 — cache-key invalidation only
    runfolder_mtime_val: float = 0.0,  # noqa: ARG001 — cache-key invalidation only
) -> WLAnalysisResult:
    """Run pylinac Winston-Lutz analysis and return a :class:`WLAnalysisResult`.

    All pylinac API interaction is isolated here. The result is a frozen,
    picklable dataclass safe for ``@st.cache_data``.

    Args:
        machine_id: Machine key (e.g. ``"LA2"``).
        runfolder_path: Absolute path to the DICOM runfolder.
        bb_size_mm: BB diameter in mm.
        machine_scale: One of ``VARIAN_IEC``, ``VARIAN_STANDARD``, ``IEC61217``.
        low_density_bb: Pass to pylinac.
        open_field: Pass to pylinac.
        apply_virtual_shift: Pass to pylinac.
        snap_tolerance: Pass to pylinac (or ``None`` for default).
        gantry_reference: Pass to pylinac (or ``None`` for default).
        collimator_reference: Pass to pylinac (or ``None`` for default).
        couch_reference: Pass to pylinac (or ``None`` for default).
        dicom_file_count: Cache-key invalidation (not used in computation).
        runfolder_mtime_val: Cache-key invalidation (not used in computation).

    Returns:
        A :class:`WLAnalysisResult`.
    """
    from pylinac import WinstonLutz  # local import: heavy module

    params = {
        "bb_size_mm": bb_size_mm,
        "machine_scale": machine_scale,
        "low_density_bb": low_density_bb,
        "open_field": open_field,
        "apply_virtual_shift": apply_virtual_shift,
        "snap_tolerance": snap_tolerance,
        "gantry_reference": gantry_reference,
        "collimator_reference": collimator_reference,
        "couch_reference": couch_reference,
    }
    analyze_kwargs = _build_analyze_kwargs(params)

    logger.info(
        "Running Winston-Lutz analysis for %s on %s with %s",
        machine_id,
        runfolder_path,
        analyze_kwargs,
    )

    wl = WinstonLutz(runfolder_path)
    wl.analyze(**analyze_kwargs)

    # Extract results as dict for summary metrics
    data = wl.results_data(as_dict=True)

    # Map pylinac keys → our canonical 24 metric names
    from core.config import WL_METRIC_NAMES

    summary: dict[str, float | int | str] = {}
    for canonical in WL_METRIC_NAMES:
        if canonical == "machine_name":
            summary[canonical] = machine_id
        elif canonical == "session_date":
            summary[canonical] = _extract_session_date(data, wl)
        elif canonical in ("bb_shift_x", "bb_shift_y", "bb_shift_z"):
            vec = data.get("bb_shift_vector", {})
            if isinstance(vec, dict):
                axis = canonical[-1]  # 'x', 'y', or 'z'
                summary[canonical] = vec.get(axis, 0.0)
            else:
                summary[canonical] = 0.0
        else:
            summary[canonical] = _resolve_metric(data, canonical)
    summary["num_total_images"] = len(wl.images)

    # Extract per-image details via keyed_image_details
    keyed = data.get("keyed_image_details", {})
    if keyed:
        image_keys = list(keyed.keys())
        image_details = [dict(keyed[k]) for k in image_keys]
    else:
        # Fall back to wl.images iteration
        image_keys = []
        image_details = []
        for img in wl.images:
            img_data = img.results_data(as_dict=True) if hasattr(img, "results_data") else {}
            image_keys.append(_derive_image_key(img_data))
            image_details.append(img_data)

    # Precompute Plotly arrays
    dev, scatter, hist = _precompute_plotly_arrays(image_details, image_keys)

    return WLAnalysisResult(
        machine_id=machine_id,
        runfolder_path=runfolder_path,
        session_date=str(summary.get("session_date", "unknown")),
        summary=summary,
        image_details=image_details,
        image_keys=image_keys,
        deviation_vs_gantry=dev,
        bb_xy_scatter=scatter,
        distance_histogram=hist,
        params_used=params,
    )


def _derive_image_key(detail: dict[str, Any]) -> str:
    """Derive a ``G{gantry}B{coll}P{couch}`` key from image detail fields.

    Used as fallback when pylinac's ``keyed_image_details`` is not available.
    """
    g = detail.get("gantry_angle", 0)
    b = detail.get("collimator_angle", 0)
    p = detail.get("couch_angle", 0)
    return f"G{g}B{b}P{p}"


def load_wl_object(runfolder_path: str, params: dict[str, Any]) -> Any:
    """Load and analyse a pylinac ``WinstonLutz`` object for Advanced mode.

    Used by the Detection overlay tab (lazy init). Returns the live object
    (not picklable) so callers can call ``wl.images[i].plot()``.

    Args:
        runfolder_path: Absolute path to the DICOM runfolder.
        params: Dict of analyze parameters (from ``WLAnalysisResult.params_used``).
    """
    from pylinac import WinstonLutz

    wl = WinstonLutz(runfolder_path)
    wl.analyze(**_build_analyze_kwargs(params))
    return wl


__all__ = [
    "ANALYZE_PARAMS",
    "count_dicoms",
    "find_newest_runfolder",
    "list_runfolders",
    "load_wl_object",
    "run_wl_analysis",
    "runfolder_mtime",
]
