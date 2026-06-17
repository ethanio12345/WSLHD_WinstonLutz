"""Excel writer — produces paired ``.xltx`` + ``.xlsx`` per Field Profile session.

Implements the ``fp-result-export`` spec:
- Per-session output folder at
  ``<output_root>/FP/<MACHINE>_FP_<IMAGE_STEM>/``
- ``.xltx`` copied verbatim from ``templates/field_profile.xltx``
- ``.xlsx`` produced by loading the copy, populating 29 metric named cells +
  ``template_version``, and writing 4 data sheets (Profiles, Penumbra,
  CAX Beam Center, ROI)

Public API:
    - :func:`write_fp_session_output`
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.styles import Font

from core.config import FP_SUMMARY_NAMES
from core.excel_helpers import set_named_cell
from core.result_types import FieldAnalysisResult
from core.session_io import build_session_folder, copy_template_to_session

logger = logging.getLogger(__name__)

#: Current Field Profile template version stamp
#: (should match build_fp_xltx_template.py).
TEMPLATE_VERSION = "2026-06-fp"


def write_fp_session_output(
    result: FieldAnalysisResult,
    output_root: Path,
    template_path: Path,
) -> Path:
    """Write paired ``.xltx`` + ``.xlsx`` for a Field Profile session.

    Creates the session folder hierarchy if needed, copies the template as
    ``.xltx``, loads it, populates the 29 metric named cells +
    ``template_version``, writes 4 data sheets, and saves the ``.xlsx``.

    The session folder is keyed on the **image stem** (not the runfolder),
    matching the single-image input model (design D1, D5)::

        <output_root>/FP/<MACHINE>_FP_<IMAGE_STEM>/<MACHINE>_FP_<IMAGE_STEM>.xlsx

    Args:
        result: The Field Profile analysis result to write.
        output_root: The machine's output root (``machine.output_root``).
        template_path: Path to ``templates/field_profile.xltx``.

    Returns:
        The path to the written ``.xlsx`` file.
    """
    image_stem = Path(result.image_path).stem
    base_name = f"{result.machine_id}_FP_{image_stem}"

    # 1. Build session folder + copy template as .xltx
    session_dir = build_session_folder(
        output_root=output_root,
        machine_id=result.machine_id,
        module_dir="FP",
        runfolder_name=image_stem,
        file_prefix="FP",
    )
    xltx_out = copy_template_to_session(template_path, session_dir, base_name)
    logger.info("Copied Field Profile template to %s", xltx_out)

    # 2. Load the copy, populate named cells + data sheets, save as .xlsx
    wb = load_workbook(str(xltx_out))

    # Populate the 29 metric named cells from result.summary
    for name in FP_SUMMARY_NAMES:
        value = result.summary.get(name, 0.0)
        set_named_cell(wb, name, value)

    # Populate template_version
    set_named_cell(wb, "template_version", TEMPLATE_VERSION)

    # 3. Write the 4 data sheets
    _write_profiles_sheet(wb, result.vert_profile_values, result.horiz_profile_values)
    _write_penumbra_sheet(wb, result.summary)
    _write_cax_beam_center_sheet(wb, result.summary)
    _write_roi_sheet(wb, result.summary)

    # 4. Save as .xlsx
    xlsx_out = session_dir / f"{base_name}.xlsx"
    wb.save(str(xlsx_out))
    logger.info("Wrote Field Profile session output: %s", xlsx_out)

    return xlsx_out


# ---------------------------------------------------------------------------
# Data-sheet writers
# ---------------------------------------------------------------------------

_HEADER_FONT = Font(bold=True)


def _write_header(ws: Any, headers: list[str], row: int = 1) -> None:
    """Write a header row with bold formatting."""
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col_idx, value=header)
        cell.font = _HEADER_FONT


def _write_profiles_sheet(wb: Any, vert_values: list[float], horiz_values: list[float]) -> None:
    """Write the Profiles sheet: vertical + horizontal profile tabular data.

    Each profile is written as two columns (index/position placeholder +
    normalized dose). The position column is left as an index (1-based) since
    the precise mm mapping depends on pixel spacing + profile geometry; the
    dose column is the normalized dose from pylinac's ``profile.values``.
    """
    if "Profiles" not in wb.sheetnames:
        wb.create_sheet(title="Profiles")
    ws = wb["Profiles"]

    _write_header(ws, ["Axis", "Position (mm)", "Normalized Dose"])

    row = 2
    # Vertical profile rows
    for i, val in enumerate(vert_values):
        ws.cell(row=row, column=1, value="vertical")
        ws.cell(row=row, column=2, value=float(i))
        ws.cell(row=row, column=3, value=float(val))
        row += 1
    # Horizontal profile rows
    for i, val in enumerate(horiz_values):
        ws.cell(row=row, column=1, value="horizontal")
        ws.cell(row=row, column=2, value=float(i))
        ws.cell(row=row, column=3, value=float(val))
        row += 1


def _write_penumbra_sheet(wb: Any, summary: dict[str, Any]) -> None:
    """Write the Penumbra sheet: 4 rows (Top, Bottom, Left, Right)."""
    if "Penumbra" not in wb.sheetnames:
        wb.create_sheet(title="Penumbra")
    ws = wb["Penumbra"]

    _write_header(ws, ["Side", "Penumbra (mm)", "Penumbra (%/mm)"])
    # pylinac reports *_penumbra_percent_mm as 0.0 in results_data for the demo;
    # we surface it from the summary if present, else blank.
    rows = [
        ("Top", "top_penumbra_mm", "top_penumbra_percent_mm"),
        ("Bottom", "bottom_penumbra_mm", "bottom_penumbra_percent_mm"),
        ("Left", "left_penumbra_mm", "left_penumbra_percent_mm"),
        ("Right", "right_penumbra_mm", "right_penumbra_percent_mm"),
    ]
    for r_idx, (label, mm_key, pct_key) in enumerate(rows, start=2):
        ws.cell(row=r_idx, column=1, value=label)
        ws.cell(row=r_idx, column=2, value=float(summary.get(mm_key, 0.0)))
        ws.cell(row=r_idx, column=3, value=float(summary.get(pct_key, 0.0)))


def _write_cax_beam_center_sheet(wb: Any, summary: dict[str, Any]) -> None:
    """Write the CAX Beam Center sheet: offsets from CAX and beam center."""
    if "CAX Beam Center" not in wb.sheetnames:
        wb.create_sheet(title="CAX Beam Center")
    ws = wb["CAX Beam Center"]

    _write_header(ws, ["Metric", "Top", "Bottom", "Left", "Right"])
    ws.cell(row=2, column=1, value="CAX offset (mm)")
    ws.cell(row=2, column=2, value=float(summary.get("cax_to_top_mm", 0.0)))
    ws.cell(row=2, column=3, value=float(summary.get("cax_to_bottom_mm", 0.0)))
    ws.cell(row=2, column=4, value=float(summary.get("cax_to_left_mm", 0.0)))
    ws.cell(row=2, column=5, value=float(summary.get("cax_to_right_mm", 0.0)))

    ws.cell(row=3, column=1, value="Beam center offset (mm)")
    ws.cell(row=3, column=2, value=float(summary.get("beam_center_to_top_mm", 0.0)))
    ws.cell(row=3, column=3, value=float(summary.get("beam_center_to_bottom_mm", 0.0)))
    ws.cell(row=3, column=4, value=float(summary.get("beam_center_to_left_mm", 0.0)))
    ws.cell(row=3, column=5, value=float(summary.get("beam_center_to_right_mm", 0.0)))

    ws.cell(row=4, column=1, value="Slope (%/mm)")
    ws.cell(row=4, column=2, value=float(summary.get("top_slope_percent_mm", 0.0)))
    ws.cell(row=4, column=3, value=float(summary.get("bottom_slope_percent_mm", 0.0)))
    ws.cell(row=4, column=4, value=float(summary.get("left_slope_percent_mm", 0.0)))
    ws.cell(row=4, column=5, value=float(summary.get("right_slope_percent_mm", 0.0)))


def _write_roi_sheet(wb: Any, summary: dict[str, Any]) -> None:
    """Write the ROI sheet: central ROI mean/max/min/std."""
    if "ROI" not in wb.sheetnames:
        wb.create_sheet(title="ROI")
    ws = wb["ROI"]

    _write_header(ws, ["Statistic", "Value"])
    stats = [
        ("Mean", "central_roi_mean"),
        ("Max", "central_roi_max"),
        ("Min", "central_roi_min"),
        ("Std", "central_roi_std"),
    ]
    for r_idx, (label, key) in enumerate(stats, start=2):
        ws.cell(row=r_idx, column=1, value=label)
        ws.cell(row=r_idx, column=2, value=float(summary.get(key, 0.0)))


__all__ = [
    "TEMPLATE_VERSION",
    "write_fp_session_output",
]
