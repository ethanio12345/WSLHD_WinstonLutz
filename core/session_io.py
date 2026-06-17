"""Per-machine output folder creation + paired-xltx copy utilities.

Extracted from ``core/excel_writer.py``'s ``_session_folder`` (design D1, D6)
so both the WL and CatPhan pages share the same canonical output path layout::

    <machine_output_root>/<MODULE>/<MACHINE>_<PREFIX>_<RUNFOLDER>/

e.g. ``/data/LA2/output/WL/LA2_WL_2026-06-16_143022``
     ``/data/LA2/output/CatPhan/LA2_CP_2026-06-16_143022``

Public API:
    - :data:`MODULE_DISPATCH`
    - :func:`build_session_folder`
    - :func:`copy_template_to_session`
"""

from __future__ import annotations

import shutil
from pathlib import Path

#: Maps a module id (the ``dicom_roots`` key) to its ``(module_dir, file_prefix)``
#: pair used in the output path and file naming. Future modules add entries here.
MODULE_DISPATCH: dict[str, tuple[str, str]] = {
    "winston_lutz": ("WL", "WL"),
    "catphan": ("CatPhan", "CP"),
    "field_profile": ("FP", "FP"),
}


def build_session_folder(
    output_root: str | Path,
    machine_id: str,
    module_dir: str,
    runfolder_name: str,
    file_prefix: str,
) -> Path:
    """Build (and create) the per-session output folder path.

    Structure::

        <output_root>/<module_dir>/<MACHINE>_<PREFIX>_<RUNFOLDER>

    e.g. ``/data/LA2/output/WL/LA2_WL_demo_clinical``
         ``/data/LA2/output/CatPhan/LA2_CP_2026-06-16_143022``

    Args:
        output_root: The machine's output root (``machine.output_root``).
        machine_id: Machine key (e.g. ``"LA2"``).
        module_dir: Literal module folder name (e.g. ``"WL"`` or ``"CatPhan"``).
        runfolder_name: The runfolder directory name.
        file_prefix: File-name prefix (e.g. ``"WL"`` or ``"CP"``).

    Returns:
        The created session folder path.
    """
    folder = Path(output_root) / module_dir / f"{machine_id}_{file_prefix}_{runfolder_name}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def copy_template_to_session(
    template_path: Path,
    session_folder: Path,
    output_stem: str,
) -> Path:
    """Copy the xltx template into the session folder, renamed to ``<stem>.xltx``.

    Args:
        template_path: Path to the source xltx template.
        session_folder: The session output folder (created by
            :func:`build_session_folder`).
        output_stem: The base file name without extension
            (e.g. ``"LA2_CP_2026-06-16_143022"``).

    Returns:
        The path to the copied ``<stem>.xltx`` file in the session folder.
    """
    dst = session_folder / f"{output_stem}.xltx"
    shutil.copy(str(template_path), str(dst))
    return dst


__all__ = [
    "MODULE_DISPATCH",
    "build_session_folder",
    "copy_template_to_session",
]
