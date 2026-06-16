"""One-time script: generate ``templates/winston_lutz.xltx``.

Creates a summary sheet with the 25 required defined names (24 metrics +
``template_version``) laid out as a session-metadata row followed by a metric
table. Applies basic formatting (column widths, bold headers).

Usage::

    uv run python scripts/build_xltx_template.py

After running, the template validator (``core.config.validate_template``) is
invoked to confirm all 25 names are present.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow ``from core.config import ...`` when running the script directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.workbook.defined_name import DefinedName

from core.config import REQUIRED_TEMPLATE_NAMES, WL_METRIC_NAMES, validate_template

TEMPLATE_VERSION = "2026-06"
SUMMARY_SHEET = "Summary"


def _build_template() -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = SUMMARY_SHEET

    header_font = Font(bold=True)
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 18

    # Header row
    ws["A1"] = "Winston-Lutz QA Summary"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Template version: {TEMPLATE_VERSION}"

    # Session metadata section (rows 4-6)
    ws["A4"] = "Session Metadata"
    ws["A4"].font = header_font
    meta_fields = ["machine_name", "session_date", "num_total_images"]
    for i, name in enumerate(meta_fields, start=5):
        ws.cell(row=i, column=1, value=name.replace("_", " ").title())
        # Define the named cell pointing at column B of this row
        coord = f"B{i}"
        ws.cell(row=i, column=2, value="")
        wb.defined_names[name] = DefinedName(
            name, attr_text=f"'{SUMMARY_SHEET}'!${coord[0]}${coord[1:]}"
        )

    # Clinical + secondary metrics section (rows 9 onward)
    ws["A9"] = "Metrics"
    ws["A9"].font = header_font
    ws["A10"] = "Metric"
    ws["A10"].font = header_font
    ws["B10"] = "Value"
    ws["B10"].font = header_font

    metric_names = [n for n in WL_METRIC_NAMES if n not in meta_fields]
    for i, name in enumerate(metric_names, start=11):
        ws.cell(row=i, column=1, value=name)
        coord = f"B{i}"
        ws.cell(row=i, column=2, value="")
        wb.defined_names[name] = DefinedName(
            name, attr_text=f"'{SUMMARY_SHEET}'!${coord[0]}${coord[1:]}"
        )

    # template_version named cell (points at B2 where we wrote it)
    wb.defined_names["template_version"] = DefinedName(
        "template_version", attr_text=f"'{SUMMARY_SHEET}'!$B$2"
    )

    return wb


def main() -> int:
    out_path = Path(__file__).resolve().parent.parent / "templates" / "winston_lutz.xltx"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    wb = _build_template()
    wb.save(str(out_path))
    print(f"Template written: {out_path}")

    # Self-check: validate all 25 names are defined
    validate_template(out_path)
    print(f"Validation passed: all {len(REQUIRED_TEMPLATE_NAMES)} required names present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
