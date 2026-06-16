"""Excel helper utilities shared across module Excel writers.

Extracted verbatim from ``core/excel_writer.py`` (design D1) so both the WL
and CatPhan writers share the same named-cell writer and sheet-name sanitiser.

Public API:
    - :func:`set_named_cell`
    - :func:`sanitise_sheet_name`
"""

from __future__ import annotations

import re
from typing import Any

from openpyxl import Workbook

#: Characters Excel forbids in sheet names.
_FORBIDDEN_SHEET_CHARS = re.compile(r"[\\\/\?\*\[\]:]")

#: Excel's maximum sheet name length.
_MAX_SHEET_NAME_LEN = 31


def set_named_cell(wb: Workbook, name: str, value: Any) -> None:
    """Resolve a defined name to its target cell and set the value.

    Args:
        wb: An openpyxl ``Workbook`` with defined names.
        name: The defined name (e.g. ``"max_2d_cax_to_bb"``).
        value: The value to write.

    Raises:
        KeyError: If ``name`` is not a defined name in the workbook.
    """
    defined_names = wb.defined_names
    if name not in defined_names:
        raise KeyError(
            f"Defined name '{name}' not found in workbook. Ensure the xltx template defines it."
        )
    dn = defined_names[name]
    # ``destinations()`` yields (worksheet_title, cell_range) tuples
    for sheet_title, coord in dn.destinations:
        wb[sheet_title][coord] = value
        return  # only set the first destination
    raise KeyError(f"Defined name '{name}' has no destinations in the workbook.")


def sanitise_sheet_name(name: str) -> str:
    """Sanitise a string for use as an Excel sheet name.

    - Replace ``\\ / ? * [ ] :`` with ``_``
    - Truncate to 30 chars + ``…`` (total 31) if length exceeds 31

    Args:
        name: The raw sheet name candidate.

    Returns:
        A sheet-name-safe string of at most 31 characters.
    """
    cleaned = _FORBIDDEN_SHEET_CHARS.sub("_", name)
    if len(cleaned) <= _MAX_SHEET_NAME_LEN:
        return cleaned
    return cleaned[:30] + "…"


__all__ = [
    "sanitise_sheet_name",
    "set_named_cell",
]
