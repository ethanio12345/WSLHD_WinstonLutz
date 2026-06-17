"""Thin wrapper around ``pylinac.FieldAnalysis`` — the field profile analysis runner.

This module **isolates all pylinac API calls** so that future pylinac major
versions require changes only here (mirroring :mod:`core.wl_runner` and
:mod:`core.cbct_runner`).

Two key differences from WL/CatPhan runners:

    1. Field Analysis operates on a **single DICOM image**, not a runfolder of
       images. The image path is the input.
    2. FFF mode is **auto-detected** from DICOM metadata (3-strategy priority,
       design D2) and passed to pylinac's ``is_FFF`` flag.

The pylinac ``analyze()`` parameter ``edge_detection_method`` accepts enum
members or enum values, but config stores NAME-style strings (e.g.
``"INFLECTION_DERIVATIVE"``). These are converted to enum members via
:func:`_enum_by_name` before being passed to pylinac.

Public API:
    - :func:`run_fp_analysis`
    - :func:`load_fp_object`  (lazy init for Advanced mode plots)
    - :func:`extract_dicom_info`
    - :func:`detect_fff`
    - :data:`ANALYZE_PARAMS`
"""

from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path
from typing import Any

from core.result_types import FieldAnalysisResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# pylinac wrapper
# ---------------------------------------------------------------------------

#: The FieldAnalysis ``analyze()`` parameters we expose in the UI (spec D6).
#: Note: ``is_FFF`` is auto-detected per image but exposed in the Advanced
#: sidebar as an override checkbox.
ANALYZE_PARAMS: tuple[str, ...] = (
    "protocol",
    "centering",
    "vert_position",
    "horiz_position",
    "vert_width",
    "horiz_width",
    "in_field_ratio",
    "slope_exclusion_ratio",
    "is_FFF",
    "penumbra",
    "interpolation",
    "edge_detection_method",
    "edge_smoothing_ratio",
    "hill_window_ratio",
)

#: Config/UI strings that need conversion to pylinac enum members by NAME.
_ENUM_PARAMS: tuple[str, ...] = ("protocol", "centering", "interpolation", "edge_detection_method")


def _enum_by_name(enum_cls: type[Enum], name: str | Enum) -> Enum:
    """Resolve a NAME-style config string to a pylinac enum member.

    pylinac's ``convert_to_enum`` looks up by VALUE (e.g.
    ``"Inflection Derivative"``), but config stores NAME-style strings (e.g.
    ``"INFLECTION_DERIVATIVE"``). This helper looks up by NAME instead. If the
    value is already an enum member, it passes through.
    """
    if isinstance(name, Enum):
        return name
    try:
        return enum_cls[str(name)]  # lookup by name
    except KeyError as exc:
        allowed = ", ".join(e.name for e in enum_cls)
        raise ValueError(
            f"'{name}' is not a valid {enum_cls.__name__} name. Allowed: {allowed}"
        ) from exc


def _build_analyze_kwargs(params: dict[str, Any]) -> dict[str, Any]:
    """Filter ``params`` to only the keys pylinac's ``analyze()`` accepts.

    Maps NAME-style config strings to pylinac enum members for the enum-typed
    parameters (``protocol``, ``centering``, ``interpolation``,
    ``edge_detection_method``).
    """
    import pylinac

    kwargs: dict[str, Any] = {}
    for key in ANALYZE_PARAMS:
        if key not in params:
            continue
        val = params[key]
        if val is None:
            continue  # let pylinac use its default

        if key in _ENUM_PARAMS:
            enum_cls = {
                "protocol": pylinac.Protocol,
                "centering": pylinac.Centering,
                "interpolation": pylinac.Interpolation,
                "edge_detection_method": pylinac.Edge,
            }[key]
            kwargs[key] = _enum_by_name(enum_cls, val)
        elif key == "penumbra":
            # pylinac accepts a tuple; config stores a list. Normalise.
            kwargs[key] = tuple(val) if isinstance(val, (list, tuple)) else val
        else:
            kwargs[key] = val

    return kwargs


# ---------------------------------------------------------------------------
# Summary mapping (the 29 metric named cells)
# ---------------------------------------------------------------------------


def _build_summary(
    machine_id: str,
    session_date: str,
    image_display_name: str,
    data: dict[str, Any],
) -> dict[str, float | int | str]:
    """Build the flat summary dict keyed by named-cell name.

    Pulls the 29 metric values from pylinac's flat ``results_data`` dict plus
    the nested ``protocol_results`` sub-dict. The 30th cell
    (``template_version``) is added by the excel writer.
    """
    protocol_results = data.get("protocol_results", {})

    summary: dict[str, float | int | str] = {
        # Session metadata (3)
        "machine_name": machine_id,
        "session_date": session_date,
        "image_name": image_display_name,
        # Protocol metrics (4)
        "flatness_vertical": float(protocol_results.get("flatness_vertical", 0.0)),
        "flatness_horizontal": float(protocol_results.get("flatness_horizontal", 0.0)),
        "symmetry_vertical": float(protocol_results.get("symmetry_vertical", 0.0)),
        "symmetry_horizontal": float(protocol_results.get("symmetry_horizontal", 0.0)),
        # Field geometry (2)
        "field_size_vertical_mm": float(data.get("field_size_vertical_mm", 0.0)),
        "field_size_horizontal_mm": float(data.get("field_size_horizontal_mm", 0.0)),
        # Penumbra (4)
        "top_penumbra_mm": float(data.get("top_penumbra_mm", 0.0)),
        "bottom_penumbra_mm": float(data.get("bottom_penumbra_mm", 0.0)),
        "left_penumbra_mm": float(data.get("left_penumbra_mm", 0.0)),
        "right_penumbra_mm": float(data.get("right_penumbra_mm", 0.0)),
        # CAX offsets (4)
        "cax_to_top_mm": float(data.get("cax_to_top_mm", 0.0)),
        "cax_to_bottom_mm": float(data.get("cax_to_bottom_mm", 0.0)),
        "cax_to_left_mm": float(data.get("cax_to_left_mm", 0.0)),
        "cax_to_right_mm": float(data.get("cax_to_right_mm", 0.0)),
        # Beam center offsets (4)
        "beam_center_to_top_mm": float(data.get("beam_center_to_top_mm", 0.0)),
        "beam_center_to_bottom_mm": float(data.get("beam_center_to_bottom_mm", 0.0)),
        "beam_center_to_left_mm": float(data.get("beam_center_to_left_mm", 0.0)),
        "beam_center_to_right_mm": float(data.get("beam_center_to_right_mm", 0.0)),
        # Slopes (4)
        "top_slope_percent_mm": float(data.get("top_slope_percent_mm", 0.0)),
        "bottom_slope_percent_mm": float(data.get("bottom_slope_percent_mm", 0.0)),
        "left_slope_percent_mm": float(data.get("left_slope_percent_mm", 0.0)),
        "right_slope_percent_mm": float(data.get("right_slope_percent_mm", 0.0)),
        # Central ROI (4)
        "central_roi_mean": float(data.get("central_roi_mean", 0.0)),
        "central_roi_max": float(data.get("central_roi_max", 0.0)),
        "central_roi_min": float(data.get("central_roi_min", 0.0)),
        "central_roi_std": float(data.get("central_roi_std", 0.0)),
    }
    return summary


# ---------------------------------------------------------------------------
# FFF auto-detection (3-strategy priority, design D2)
# ---------------------------------------------------------------------------

#: DICOM tag (group, element) for Radiation Energy (Varian RT Image).
_RADIATION_ENERGY_TAG: tuple[int, int] = (0x3002, 0x0060)

# NOTE: Design D2 originally specified a 3rd "shape heuristic" strategy
# (central_roi_mean / edge_mean > 1.05). This was dropped during implementation
# because no fixed-radius "periphery" sample reliably distinguishes FFF from
# flat without first knowing the field boundary — comparing the centre to the
# dose-free background outside the field flags every portal image as FFF.
# Strategies 1+2 cover all standard Varian RT images (which carry tag 3002,0060).
# A flat-beam analysis run on an FFF image may fail; the user re-runs or uses
# the Advanced-mode FFF override checkbox. See design D2 (revised).


def detect_fff(dicom_path: str | Path) -> bool:
    """Detect whether ``dicom_path`` is an FFF beam (design D2, revised).

    Two-strategy priority:
        1. **Radiation Energy tag** ``(3002,0060)`` — Varian stores ``"6FFF"``,
           ``"10FFF"``. If ``"FFF"`` substring is present → ``True``.
        2. **String tag scan** — scan all string-valued DICOM tags for the
           ``"FFF"`` substring (catches non-standard placements like
           SeriesDescription).

    If neither strategy matches, ``False`` is returned (flat beam assumed). A
    flat-beam analysis run on an actual FFF image may fail or give incorrect
    symmetry; the user can override via the Advanced-mode FFF checkbox and
    re-run.

    Args:
        dicom_path: Path to the DICOM image.

    Returns:
        ``True`` if FFF is detected, ``False`` otherwise.
    """
    info = _extract_dicom_info_raw(dicom_path)
    # Strategy 1: Radiation Energy tag
    energy = info.get("energy", "")
    if energy and "FFF" in str(energy).upper():
        logger.info("FFF detected via Radiation Energy tag: %s", energy)
        return True

    # Strategy 2: string tag scan
    for _tag, value in info.get("string_values", []):
        if "FFF" in str(value).upper():
            logger.info("FFF detected via string tag scan: %s=%s", _tag, value)
            return True

    return False


# ---------------------------------------------------------------------------
# DICOM metadata extraction
# ---------------------------------------------------------------------------


def _extract_dicom_info_raw(dicom_path: str | Path) -> dict[str, Any]:
    """Read raw DICOM metadata for FFF detection and display (no pylinac).

    Returns a dict with: ``energy``, ``rt_image_label``, ``rows``, ``cols``,
    ``pixel_spacing``, ``string_values`` (list of (tag, value) for string
    tags), and ``acquisition_date``.
    """
    from pydicom import dcmread

    ds = dcmread(str(dicom_path), stop_before_pixels=True)

    # Strategy 1 source: Radiation Energy tag (3002,0060)
    energy_elem = ds.get(_RADIATION_ENERGY_TAG, None)
    energy = str(energy_elem.value) if energy_elem is not None else ""

    # RT Image Label (3002,0002) — useful for display
    rt_label_elem = ds.get((0x3002, 0x0002), None)
    rt_label = str(rt_label_elem.value) if rt_label_elem is not None else ""

    # Dimensions
    rows = int(getattr(ds, "Rows", 0) or 0)
    cols = int(getattr(ds, "Columns", 0) or 0)

    # Pixel spacing (Image Plane Pixel Spacing for RT images, or PixelSpacing)
    spacing_elem = ds.get((0x3002, 0x0011), None) or ds.get((0x0028, 0x0030), None)
    if spacing_elem is not None and spacing_elem.value:
        spacing = "x".join(f"{float(s):.3f}" for s in spacing_elem.value)
    else:
        spacing = "?"

    # Strategy 2 source: collect all string-valued tags
    string_values: list[tuple[str, str]] = []
    for elem in ds.iterall():
        if elem.VR in ("LO", "SH", "CS", "ST", "LT", "UT") and elem.value:
            string_values.append((str(elem.tag), str(elem.value)))

    # Acquisition date
    acquisition_date = str(getattr(ds, "AcquisitionDate", "") or "")

    return {
        "energy": energy,
        "rt_image_label": rt_label,
        "rows": rows,
        "cols": cols,
        "pixel_spacing": spacing,
        "string_values": string_values,
        "acquisition_date": acquisition_date,
    }


def extract_dicom_info(dicom_path: str | Path) -> dict[str, Any]:
    """Extract DICOM metadata for the image dropdown display.

    Returns a dict with: ``energy``, ``rt_label``, ``dimensions`` (e.g.
    ``"1024x768"``), ``pixel_spacing`` (e.g. ``"0.392x0.392"``),
    ``display_string`` (the full dropdown label), ``is_fff`` (bool),
    ``filename``.

    Missing tags are rendered as ``"?"`` — no crash for missing metadata
    (fp-simple-mode spec scenario: DICOM metadata missing).
    """
    raw = _extract_dicom_info_raw(dicom_path)
    rows, cols = raw["rows"], raw["cols"]
    dimensions = f"{cols}x{rows}" if rows and cols else "?"
    is_fff = detect_fff(dicom_path)

    parts: list[str] = []
    energy = raw["energy"] or "?"
    parts.append(energy if energy != "?" else "?")
    rt_label = raw["rt_image_label"] or "?"
    parts.append(rt_label)
    parts.append(dimensions)
    parts.append(f"{raw['pixel_spacing']}mm/px" if raw["pixel_spacing"] != "?" else "?")

    filename = Path(dicom_path).name
    display_string = f"{parts[0]}  {parts[1]}  {parts[2]}  {parts[3]}  ({filename})"

    return {
        "energy": energy,
        "rt_label": rt_label,
        "dimensions": dimensions,
        "pixel_spacing": raw["pixel_spacing"],
        "display_string": display_string,
        "is_fff": is_fff,
        "filename": filename,
        "acquisition_date": raw["acquisition_date"],
    }


# ---------------------------------------------------------------------------
# Profile downsampling (for Plotly performance, design risks)
# ---------------------------------------------------------------------------

#: Target number of points for Plotly profile rendering.
_PROFILE_TARGET_POINTS = 500


def _downsample(values: list[float] | Any, target: int = _PROFILE_TARGET_POINTS) -> list[float]:
    """Downsample a 1-D array to at most ``target`` evenly-spaced points.

    pylinac profile ``.values`` arrays are 3000+ points; Plotly rendering is
    smoother and faster with ~500. If the input has fewer points than the
    target, it is returned unchanged (as plain floats).
    """
    import numpy as np

    arr = np.asarray(values, dtype=float).ravel()
    if arr.size <= target:
        return [float(v) for v in arr]
    indices = np.linspace(0, arr.size - 1, num=target, dtype=int)
    return [float(v) for v in arr[indices]]


# ---------------------------------------------------------------------------
# Session date extraction
# ---------------------------------------------------------------------------


def _extract_session_date(data: dict[str, Any], dicom_info: dict[str, Any]) -> str:
    """Extract the session date from DICOM metadata or pylinac's analysis date.

    Tries DICOM ``AcquisitionDate`` (from the dropdown extraction), falls back
    to ``date_of_analysis`` from pylinac, then ``"unknown"``.
    """
    acquisition_date = dicom_info.get("acquisition_date", "")
    if acquisition_date:
        return str(acquisition_date)
    date_str = data.get("date_of_analysis", "")
    if date_str:
        return str(date_str)[:10]
    return "unknown"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_fp_analysis(
    machine_id: str,
    image_path: str,
    image_display_name: str,
    protocol: str = "VARIAN",
    centering: str = "BEAM_CENTER",
    vert_position: float = 0.5,
    horiz_position: float = 0.5,
    vert_width: float = 0.0,
    horiz_width: float = 0.0,
    in_field_ratio: float = 0.8,
    slope_exclusion_ratio: float = 0.2,
    is_FFF: bool | None = None,
    penumbra: list[float] | tuple[float, float] = (20.0, 80.0),
    interpolation: str = "LINEAR",
    edge_detection_method: str = "INFLECTION_DERIVATIVE",
    edge_smoothing_ratio: float = 0.003,
    hill_window_ratio: float = 0.15,
) -> FieldAnalysisResult:
    """Run pylinac FieldAnalysis and return a :class:`FieldAnalysisResult`.

    All pylinac API interaction is isolated here. The result is a frozen,
    picklable dataclass safe for ``@st.cache_data``.

    Args:
        machine_id: Machine key (e.g. ``"LA2"``).
        image_path: Absolute path to the DICOM image to analyse.
        image_display_name: The dropdown display string for the image.
        protocol: Protocol name (``"VARIAN"``, ``"SIEMENS"``, ``"ELEKTA"``).
        centering: Centering method name.
        vert_position: Vertical profile position (0-1).
        horiz_position: Horizontal profile position (0-1).
        vert_width: Vertical profile width.
        horiz_width: Horizontal profile width.
        in_field_ratio: In-field ratio for analysis.
        slope_exclusion_ratio: Slope exclusion ratio.
        is_FFF: ``True``/``False`` to force; ``None`` to auto-detect from DICOM.
        penumbra: ``(lower, upper)`` penumbra percentages.
        interpolation: Interpolation method name.
        edge_detection_method: Edge detection method name.
        edge_smoothing_ratio: Edge smoothing ratio.
        hill_window_ratio: Hill window ratio.

    Returns:
        A :class:`FieldAnalysisResult`.
    """
    from pylinac import FieldAnalysis

    # FFF auto-detection if not explicitly forced
    is_fff = detect_fff(image_path) if is_FFF is None else bool(is_FFF)

    params: dict[str, Any] = {
        "protocol": protocol,
        "centering": centering,
        "vert_position": vert_position,
        "horiz_position": horiz_position,
        "vert_width": vert_width,
        "horiz_width": horiz_width,
        "in_field_ratio": in_field_ratio,
        "slope_exclusion_ratio": slope_exclusion_ratio,
        "is_FFF": is_fff,
        "penumbra": list(penumbra),
        "interpolation": interpolation,
        "edge_detection_method": edge_detection_method,
        "edge_smoothing_ratio": edge_smoothing_ratio,
        "hill_window_ratio": hill_window_ratio,
    }
    analyze_kwargs = _build_analyze_kwargs(params)

    logger.info(
        "Running FieldAnalysis for %s on %s with is_FFF=%s, %s",
        machine_id,
        image_path,
        is_fff,
        {k: v for k, v in analyze_kwargs.items() if k != "is_FFF"},
    )

    fa = FieldAnalysis(image_path)
    fa.analyze(**analyze_kwargs)

    # Extract results as dict
    data = fa.results_data(as_dict=True)

    # Build the flat summary dict
    dicom_info = extract_dicom_info(image_path)
    session_date = _extract_session_date(data, dicom_info)
    summary = _build_summary(machine_id, session_date, image_display_name, data)

    # Protocol results sub-dict (flatness/symmetry)
    protocol_results = {k: float(v) for k, v in dict(data.get("protocol_results", {})).items()}

    # Profile values (downsampled for Plotly)
    vert_profile_values = _downsample(fa.vert_profile.values)
    horiz_profile_values = _downsample(fa.horiz_profile.values)

    return FieldAnalysisResult(
        machine_id=machine_id,
        image_path=image_path,
        image_display_name=image_display_name,
        session_date=session_date,
        is_fff=is_fff,
        summary=summary,
        vert_profile_values=vert_profile_values,
        horiz_profile_values=horiz_profile_values,
        protocol_results=protocol_results,
        params_used=params,
    )


def load_fp_object(image_path: str, params: dict[str, Any]) -> Any:
    """Load and analyse a pylinac ``FieldAnalysis`` object for Advanced mode.

    Used by the Field Map tab (lazy init). Returns the live object (not
    picklable) so callers can call ``fa.plot_analyzed_image()``.

    Args:
        image_path: Absolute path to the DICOM image.
        params: Dict of analyze parameters (from
            :attr:`FieldAnalysisResult.params_used`).
    """
    from pylinac import FieldAnalysis

    fa = FieldAnalysis(image_path)
    fa.analyze(**_build_analyze_kwargs(params))
    return fa


__all__ = [
    "ANALYZE_PARAMS",
    "detect_fff",
    "extract_dicom_info",
    "load_fp_object",
    "run_fp_analysis",
]
