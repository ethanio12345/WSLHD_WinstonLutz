"""One-time script: generate ``templates/catphan_504.xltx``.

Creates a summary sheet with the 19 required defined names (18 metrics +
``template_version``) plus four empty per-CTP-module sheets (CTP404, CTP486,
CTP528, CTP515) with header rows. Applies basic formatting (column widths,
bold headers).

Usage::

    uv run python scripts/build_catphan_xltx_template.py

After running, the template validator (``core.config.validate_catphan_template``)
is invoked to confirm all 19 names are present.
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
    REQUIRED_CATPHAN_TEMPLATE_NAMES,
    validate_catphan_template,
)

TEMPLATE_VERSION = "2026-06-cp"
SUMMARY_SHEET = "Summary"

#: Per-CTP-module sheet definitions: (sheet_name, header_row_columns).
_MODULE_SHEETS: list[tuple[str, list[str]]] = [
    ("CTP404", ["Material", "Nominal HU", "Measured HU", "Difference", "Stdev", "Passed"]),
    ("CTP486", ["Region", "Value (HU)", "Nominal", "Difference", "Stdev", "Passed"]),
    ("CTP528", ["MTF (%)", "lp/mm"]),
    ("CTP515", ["ROI", "Size", "Contrast", "CNR", "SNR", "Visibility", "Threshold", "Passed"]),
]


def _build_template() -> Workbook:
    wb = Workbook()

    # --- Summary sheet ---
    ws = wb.active
    ws.title = SUMMARY_SHEET

    header_font = Font(bold=True)
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 22

    ws["A1"] = "CatPhan 504 QA Summary"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Template version: {TEMPLATE_VERSION}"

    # Layout the 18 metric named cells in groups with section headers.
    # Group definitions (label, list of cell names).
    groups: list[tuple[str, list[str]]] = [
        ("Session Metadata", ["machine_name", "session_date", "num_images"]),
        (
            "Pass/Fail Flags",
            [
                "hu_linearity_passed",
                "geometry_passed",
                "uniformity_passed",
                "thickness_passed",
            ],
        ),
        ("Geometry", ["measured_slice_thickness_mm", "avg_line_distance_mm"]),
        ("Uniformity", ["uniformity_index", "integral_non_uniformity"]),
        ("Contrast", ["low_contrast_visibility", "num_rois_seen"]),
        ("Resolution", ["mtf_50_lp_mm", "mtf_90_lp_mm"]),
        ("NPS", ["nps_avg_power", "nps_max_freq"]),
        ("Orientation", ["catphan_roll_deg"]),
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

    # --- Per-CTP-module sheets (header rows only) ---
    for sheet_name, headers in _MODULE_SHEETS:
        ms = wb.create_sheet(title=sheet_name)
        for col_idx, header in enumerate(headers, start=1):
            cell = ms.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
        ms.column_dimensions["A"].width = 20

    return wb


def main() -> int:
    out_path = Path(__file__).resolve().parent.parent / "templates" / "catphan_504.xltx"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    wb = _build_template()
    wb.save(str(out_path))
    print(f"Template written: {out_path}")

    # Self-check: validate all 19 names are defined
    validate_catphan_template(out_path)
    print(f"Validation passed: all {len(REQUIRED_CATPHAN_TEMPLATE_NAMES)} required names present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
