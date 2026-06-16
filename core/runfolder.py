"""Runfolder discovery utilities shared across module pages.

Extracted from ``core/wl_runner.py`` (design D1) so that the CatPhan page
(and future FieldProfile page) can reuse the same newest-subdirectory-by-mtime
discovery and DICOM-counting logic without duplicating it.

Public API:
    - :data:`DICOM_GLOBS`
    - :func:`list_runfolders`
    - :func:`find_newest_runfolder`
    - :func:`count_dicoms`
    - :func:`runfolder_mtime`
"""

from __future__ import annotations

from pathlib import Path

#: Glob patterns for DICOM files.  pylinac accepts any extension but the
#: standard is ``.dcm``.  We also count extensionless files if they parse
#: as DICOM (some treatment machines export without an extension).
DICOM_GLOBS: tuple[str, ...] = ("*.dcm", "*.dicom", "*.DCM")


def list_runfolders(dicom_root: Path) -> list[Path]:
    """Return all immediate subdirectories of ``dicom_root`` sorted newest-first.

    Args:
        dicom_root: A machine's module DICOM root directory.

    Returns:
        Subdirectories sorted by mtime (newest first). Empty list if the root
        does not exist or contains no subdirectories.
    """
    if not dicom_root.exists():
        return []
    subdirs = [p for p in dicom_root.iterdir() if p.is_dir()]
    return sorted(subdirs, key=lambda p: p.stat().st_mtime, reverse=True)


def find_newest_runfolder(dicom_root: Path) -> Path | None:
    """Return the immediate subdirectory of ``dicom_root`` with the newest mtime.

    Args:
        dicom_root: A machine's module DICOM root directory.

    Returns:
        The newest subdirectory by mtime, or ``None`` if no subdirs exist.
    """
    folders = list_runfolders(dicom_root)
    return folders[0] if folders else None


def count_dicoms(runfolder: Path) -> int:
    """Count DICOM files in ``runfolder`` (any of the standard extensions)."""
    if not runfolder.exists():
        return 0
    total = 0
    for pattern in DICOM_GLOBS:
        total += sum(1 for _ in runfolder.glob(pattern))
    return total


def runfolder_mtime(runfolder: Path) -> float:
    """Return the mtime of ``runfolder`` (for cache-key invalidation)."""
    return runfolder.stat().st_mtime


__all__ = [
    "DICOM_GLOBS",
    "count_dicoms",
    "find_newest_runfolder",
    "list_runfolders",
    "runfolder_mtime",
]
