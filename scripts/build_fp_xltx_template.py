"""One-time script: generate ``templates/field_profile.xltx``.

Creates a Summary sheet with the 30 required defined names (29 metrics +
``template_version``) plus four data sheets (Profiles, Penumbra, CAX Beam
Center, ROI) with header rows. Applies basic formatting (column widths, bold
headers).

Usage::

    uv run python scripts/build_fp_xltx_template.py

After running, the template validator (``core.config.validate_fp_template``)
is invoked to confirm all 30 names are present.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow ``from core.config import ...`` when running the script directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.workbook.defined_name import DefinedName

from core.config import (
    REQUIRED_FP_TEMPLATE_NAMES,
    validate_fp_template,
)

TEMPLATE_VERSION = "2026-06-fp"
SUMMARY_SHEET = "Summary"

#: Data-sheet definitions: (sheet_name, header_columns).
_DATA_SHEETS: list[tuple[str, list[str]]] = [
    ("Profiles", ["Axis", "Position (mm)", "Normalized Dose"]),
    ("Penumbra", ["Side", "Penumbra (mm)", "Penumbra (%/mm)"]),
    ("CAX Beam Center", ["Metric", "Top", "Bottom", "Left", "Right"]),
    ("ROI", ["Statistic", "Value"]),
]


def _build_template() -> Workbook:
    wb = Workbook()

    # --- Summary sheet ---
    ws = wb.active
    ws.title = SUMMARY_SHEET

    header_font = Font(bold=True)
    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 22

    ws["A1"] = "Field Profile QA Summary"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Template version: {TEMPLATE_VERSION}"

    # Layout the 29 metric named cells in groups with section headers.
    # Group definitions (label, list of cell names).
    groups: list[tuple[str, list[str]]] = [
        ("Session Metadata", ["machine_name", "session_date", "image_name"]),
        (
            "Protocol Metrics",
            [
                "flatness_vertical",
                "flatness_horizontal",
                "symmetry_vertical",
                "symmetry_horizontal",
            ],
        ),
        ("Field Geometry", ["field_size_vertical_mm", "field_size_horizontal_mm"]),
        (
            "Penumbra",
            [
                "top_penumbra_mm",
                "bottom_penumbra_mm",
                "left_penumbra_mm",
                "right_penumbra_mm",
            ],
        ),
        (
            "CAX Offsets",
            [
                "cax_to_top_mm",
                "cax_to_bottom_mm",
                "cax_to_left_mm",
                "cax_to_right_mm",
            ],
        ),
        (
            "Beam Center Offsets",
            [
                "beam_center_to_top_mm",
                "beam_center_to_bottom_mm",
                "beam_center_to_left_mm",
                "beam_center_to_right_mm",
            ],
        ),
        (
            "Slopes",
            [
                "top_slope_percent_mm",
                "bottom_slope_percent_mm",
                "left_slope_percent_mm",
                "right_slope_percent_mm",
            ],
        ),
        (
            "Central ROI",
            ["central_roi_mean", "central_roi_max", "central_roi_min", "central_roi_std"],
        ),
    ]

    row = 4
    for group_label, names in groups:
        ws.cell(row=row, column=1, value=group_label).font = header_font
        row += 1
        for name in names:
            ws.cell(row=row, column=1, value=name.replace("_", " ").title())
            coord = f"B{row}"
            ws.cell(row=row, column=2, value="")
            wb.defined_names[name] = DefinedName(
                name, attr_text=f"'{SUMMARY_SHEET}'!${coord[0]}${coord[1:]}"
            )
            row += 1
        row += 1  # blank row between groups

    # template_version named cell (points at B2 where we wrote the version)
    wb.defined_names["template_version"] = DefinedName(
        "template_version", attr_text=f"'{SUMMARY_SHEET}'!$B$2"
    )

    # --- Data sheets (header rows only) ---
    for sheet_name, headers in _DATA_SHEETS:
        ms = wb.create_sheet(title=sheet_name)
        for col_idx, header in enumerate(headers, start=1):
            cell = ms.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
        ms.column_dimensions["A"].width = 20

    return wb


def main() -> int:
    out_path = Path(__file__).resolve().parent.parent / "templates" / "field_profile.xltx"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    wb = _build_template()
    wb.save(str(out_path))
    print(f"Template written: {out_path}")

    # Self-check: validate all 30 names are defined
    validate_fp_template(out_path)
    print(f"Validation passed: all {len(REQUIRED_FP_TEMPLATE_NAMES)} required names present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
