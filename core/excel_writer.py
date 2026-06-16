"""Excel writer — produces paired ``.xltx`` + ``.xlsx`` per Winston-Lutz session.

Implements the ``wl-result-export`` spec:
- Per-session output folder at ``<output_root>/<CATEGORY>/<DISPLAY>/<PYLINAC>/WL/<MACHINE>_WL_<RUNFOLDER>/``
- ``.xltx`` copied verbatim from ``templates/winston_lutz.xltx``
- ``.xlsx`` produced by loading the copy, populating 24 named cells +
  ``template_version``, and adding one per-image sheet per ``image_keys[i]``
- Sheet names sanitised to Excel constraints (≤31 chars, no forbidden chars)

The shared helpers (:func:`set_named_cell`, :func:`sanitise_sheet_name`,
:func:`build_session_folder`, :func:`copy_template_to_session`) now live in
:mod:`core.excel_helpers` and :mod:`core.session_io` respectively.

Public API:
    - :func:`set_named_cell`        (re-exported from core.excel_helpers)
    - :func:`sanitise_sheet_name`   (re-exported from core.excel_helpers)
    - :func:`write_session_output`
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from core.excel_helpers import sanitise_sheet_name, set_named_cell  # re-exported
from core.result_types import WLAnalysisResult
from core.session_io import build_session_folder, copy_template_to_session

logger = logging.getLogger(__name__)

#: Current template version stamp (should match the value in build_xltx_template.py).
TEMPLATE_VERSION = "2026-06"


# ---------------------------------------------------------------------------
# Session output writer
# ---------------------------------------------------------------------------


def _serialize_for_excel(val: Any) -> Any:
    """Convert a value to a type openpyxl can write.

    - Primitives (str/int/float/bool/None) pass through
    - Dicts/lists/tuples are JSON-serialised to a string
    - Anything else is str()'d
    """
    import json

    if val is None or isinstance(val, (str, int, float, bool)):
        return val
    if isinstance(val, (dict, list, tuple)):
        try:
            return json.dumps(val, default=str)
        except (TypeError, ValueError):
            return str(val)
    return str(val)


def write_session_output(
    result: WLAnalysisResult,
    output_root: Path,
    template_path: Path,
    machine_display_name: str,
    category: str = "Clinical QA",
    pylinac_subfolder: str = "Pylinac",
) -> Path:
    """Write paired ``.xltx`` + ``.xlsx`` for a Winston-Lutz session.

    Creates the session folder hierarchy if needed, copies the template as
    ``.xltx``, loads it, populates the 24 metric named cells +
    ``template_version``, adds one per-image sheet per ``image_keys[i]``,
    and saves the ``.xlsx``.

    Args:
        result: The analysis result to write.
        output_root: The output root (``config.output.root``).
        template_path: Path to ``templates/winston_lutz.xltx``.
        machine_display_name: Human-readable machine name for the folder path.
        category: Top-level category folder (default ``"Clinical QA"``).
        pylinac_subfolder: Tool subfolder (default ``"Pylinac"``).

    Returns:
        The path to the written ``.xlsx`` file.
    """
    runfolder_name = Path(result.runfolder_path).name
    base_name = f"{result.machine_id}_WL_{runfolder_name}"

    # 1. Build session folder + copy template as .xltx (verbatim)
    session_dir = build_session_folder(
        output_root=output_root,
        machine_id=result.machine_id,
        machine_display_name=machine_display_name,
        module_dir="WL",
        runfolder_name=runfolder_name,
        file_prefix="WL",
        category=category,
        pylinac_subfolder=pylinac_subfolder,
    )
    xltx_out = copy_template_to_session(template_path, session_dir, base_name)
    logger.info("Copied template to %s", xltx_out)

    # 2. Load the copy, populate named cells, add per-image sheets, save as .xlsx
    wb = load_workbook(str(xltx_out))

    # Populate the 24 metric named cells from result.summary
    from core.config import WL_METRIC_NAMES

    for canonical in WL_METRIC_NAMES:
        value = result.summary.get(canonical, 0.0)
        set_named_cell(wb, canonical, value)

    # Populate template_version
    set_named_cell(wb, "template_version", TEMPLATE_VERSION)

    # 3. Add per-image sheets (header-based table: field in A, value in B)
    # Fields to exclude from Excel output (internal noise, not clinical data)
    _EXCLUDE_FIELDS = {"warnings", "pylinac_version", "date_of_analysis"}
    for key, detail in zip(result.image_keys, result.image_details, strict=True):
        safe_name = sanitise_sheet_name(key)
        # Avoid duplicate sheet names (append index if collision)
        if safe_name in wb.sheetnames:
            idx = 1
            while f"{safe_name[:28]}_{idx}" in wb.sheetnames:
                idx += 1
            safe_name = f"{safe_name[:28]}_{idx}"
        ws = wb.create_sheet(title=safe_name)
        ws.column_dimensions["A"].width = 24
        ws.column_dimensions["B"].width = 28
        ws["A1"] = "Field"
        ws["B1"] = "Value"
        filtered = {k: v for k, v in detail.items() if k not in _EXCLUDE_FIELDS}
        for row_idx, (field, val) in enumerate(sorted(filtered.items()), start=2):
            ws.cell(row=row_idx, column=1, value=str(field))
            cell_val: Any = _serialize_for_excel(val)
            ws.cell(row=row_idx, column=2, value=cell_val)

    # 4. Save as .xlsx
    xlsx_out = session_dir / f"{base_name}.xlsx"
    wb.save(str(xlsx_out))
    logger.info("Wrote session output: %s", xlsx_out)

    # tolerance_mm is NOT written to the xlsx (per wl-result-export spec)
    return xlsx_out


__all__ = [
    "TEMPLATE_VERSION",
    "sanitise_sheet_name",
    "set_named_cell",
    "write_session_output",
]
