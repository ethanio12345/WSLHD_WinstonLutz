"""Excel writer — produces in-memory xlsx bytes for Field Profile downloads.

Implements the ``fp-result-export`` spec (as revised by the
``generalize-field-profile-browser`` change):

- Loads ``templates/field_profile.xltx`` from disk
- Populates the 29 metric named cells + ``template_version``
- Writes 4 data sheets (Profiles, Penumbra, CAX Beam Center, ROI)
- Saves to an in-memory ``io.BytesIO`` and returns the bytes

**No ``output_root``, no session folder, no machine key, no ``.xltx`` disk
copy.** The page serves the returned bytes directly to the user's browser via
``st.download_button``. The 30 named cells (the MyQA contract) are preserved
inside the downloaded xlsx.

Public API:
    - :func:`build_fp_xlsx_bytes`
    - :data:`TEMPLATE_VERSION`
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.styles import Font

from core.config import FP_SUMMARY_NAMES
from core.excel_helpers import set_named_cell
from core.result_types import FieldAnalysisResult

logger = logging.getLogger(__name__)

#: Current Field Profile template version stamp
#: (should match build_fp_xltx_template.py).
TEMPLATE_VERSION = "2026-06-fp"


def build_fp_xlsx_bytes(result: FieldAnalysisResult, template_path: Path) -> bytes:
    """Build an in-memory xlsx from the template + result, returning bytes.

    Loads the ``.xltx`` template, populates the 29 metric named cells +
    ``template_version``, writes the 4 data sheets (Profiles, Penumbra, CAX
    Beam Center, ROI), saves to an in-memory buffer, and returns the bytes.

    **No files are written to disk by this function.**

    Args:
        result: The Field Profile analysis result.
        template_path: Path to ``templates/field_profile.xltx``.

    Returns:
        The xlsx workbook as ``bytes`` (suitable for ``st.download_button``).
    """
    # 1. Load the template from disk (read-only — never copied)
    wb = load_workbook(str(template_path))

    # 2. Populate the 29 metric named cells from result.summary
    for name in FP_SUMMARY_NAMES:
        value = result.summary.get(name, 0.0)
        set_named_cell(wb, name, value)

    # 3. Populate template_version
    set_named_cell(wb, "template_version", TEMPLATE_VERSION)

    # 4. Write the 4 data sheets
    _write_profiles_sheet(wb, result.vert_profile_values, result.horiz_profile_values)
    _write_penumbra_sheet(wb, result.summary)
    _write_cax_beam_center_sheet(wb, result.summary)
    _write_roi_sheet(wb, result.summary)

    # 5. Save to an in-memory buffer and return the bytes
    buffer = io.BytesIO()
    wb.save(buffer)
    xlsx_bytes = buffer.getvalue()
    logger.info(
        "Built Field Profile xlsx bytes for image %s (%d bytes)",
        Path(result.image_path).name,
        len(xlsx_bytes),
    )
    return xlsx_bytes


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
    "build_fp_xlsx_bytes",
]
