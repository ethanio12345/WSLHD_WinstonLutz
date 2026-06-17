"""Unit tests for the Field Profile page's pure helper functions.

The page itself (``pages/3_Field_Profile.py``) can't be imported as a normal
module (the filename starts with a digit), so we load it via ``importlib`` and
test the pure helpers that enforce the ``fp-simple-mode`` spec invariants:

- ``_list_subdirs`` — the cascading-folder-browser sandbox guarantee (only
  immediate subdirectories are returned; files and ``..`` are never listed,
  so the browser cannot navigate above ``browse_root``).
- ``_list_dicom_images`` — image discovery from the selected folder.

These cover the ``fp-simple-mode`` spec scenarios:
- "Browser is sandboxed to browse_root" (the sandbox invariant)
- "browse_root missing or empty" (empty-state handling — ``_list_subdirs``
  returns an empty list for a non-existent root, which the page surfaces as
  an inline info message via ``_resolve_browse_root``)
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load the page module via importlib (filename starts with a digit)
# ---------------------------------------------------------------------------

_PAGE_PATH = Path(__file__).resolve().parents[1] / "pages" / "3_Field_Profile.py"


@pytest.fixture(scope="module")
def fp_page_module():  # type: ignore[no-untyped-def]
    """Load pages/3_Field_Profile.py as a module via importlib."""
    spec = importlib.util.spec_from_file_location("fp_page", str(_PAGE_PATH))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# _list_subdirs — the sandbox invariant
# ---------------------------------------------------------------------------


def test_list_subdirs_returns_only_immediate_subdirs(
    fp_page_module,
    tmp_path: Path,  # type: ignore[no-untyped-def]
) -> None:
    """_list_subdirs returns immediate subdirectories, sorted by name."""
    (tmp_path / "bravo").mkdir()
    (tmp_path / "alpha").mkdir()
    (tmp_path / "charlie").mkdir()
    # A file in the root — must NOT appear in the subdirs list
    (tmp_path / "readme.txt").write_text("not a dir", encoding="utf-8")
    # A nested subdir — must NOT appear (only immediate children)
    (tmp_path / "alpha" / "nested").mkdir()

    result = fp_page_module._list_subdirs(tmp_path)

    assert result == [tmp_path / "alpha", tmp_path / "bravo", tmp_path / "charlie"]


def test_list_subdirs_excludes_files(fp_page_module, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """Files are never listed by _list_subdirs (the sandbox invariant)."""
    (tmp_path / "subdir").mkdir()
    (tmp_path / "image.dcm").write_text("dicom", encoding="utf-8")
    (tmp_path / "notes.md").write_text("notes", encoding="utf-8")

    result = fp_page_module._list_subdirs(tmp_path)

    assert result == [tmp_path / "subdir"]
    # No file paths leak through
    assert all(p.is_dir() for p in result)


def test_list_subdirs_never_offers_parent_navigation(
    fp_page_module,
    tmp_path: Path,  # type: ignore[no-untyped-def]
) -> None:
    """_list_subdirs never returns '..' or parent paths (sandbox to browse_root).

    This is the core sandbox guarantee for the cascading folder browser: the
    physicist cannot navigate above ``browse_root`` because ``..`` is never
    listed as an option.
    """
    (tmp_path / "child").mkdir()

    result = fp_page_module._list_subdirs(tmp_path)

    # No '..' entry, no absolute parent path
    for p in result:
        assert p.name != ".."
        assert tmp_path in p.parents or p == tmp_path / "child"


def test_list_subdirs_nonexistent_root_returns_empty(fp_page_module, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """_list_subdirs on a non-existent root returns [] (no crash).

    This backs the spec scenario 'browse_root missing or empty': the page's
    ``_resolve_browse_root`` shows an inline info message and the browser
    never enumerates a non-existent path.
    """
    bogus = tmp_path / "does" / "not" / "exist"
    assert fp_page_module._list_subdirs(bogus) == []


def test_list_subdirs_empty_folder_returns_empty(fp_page_module, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """_list_subdirs on an empty folder returns [] (no subdirs to drill into)."""
    assert fp_page_module._list_subdirs(tmp_path) == []


# ---------------------------------------------------------------------------
# _list_dicom_images — image discovery
# ---------------------------------------------------------------------------


def test_list_dicom_images_finds_dcm_files(fp_page_module, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """_list_dicom_images lists .dcm/.dicom/.DCM files, sorted by name."""
    (tmp_path / "10MV_10x10.dcm").write_text("a", encoding="utf-8")
    (tmp_path / "6MV_10x10.dcm").write_text("b", encoding="utf-8")
    (tmp_path / "6MV_FFF.dicom").write_text("c", encoding="utf-8")
    # Non-DICOM file — excluded
    (tmp_path / "notes.txt").write_text("notes", encoding="utf-8")

    result = fp_page_module._list_dicom_images(tmp_path)

    names = [p.name for p in result]
    assert names == ["10MV_10x10.dcm", "6MV_10x10.dcm", "6MV_FFF.dicom"]


def test_list_dicom_images_empty_folder_returns_empty(
    fp_page_module,
    tmp_path: Path,  # type: ignore[no-untyped-def]
) -> None:
    """_list_dicom_images on a folder with no DICOMs returns []."""
    (tmp_path / "notes.txt").write_text("notes", encoding="utf-8")
    assert fp_page_module._list_dicom_images(tmp_path) == []


def test_list_dicom_images_nonexistent_folder_returns_empty(
    fp_page_module,
    tmp_path: Path,  # type: ignore[no-untyped-def]
) -> None:
    """_list_dicom_images on a non-existent folder returns [] (no crash)."""
    bogus = tmp_path / "ghost"
    assert fp_page_module._list_dicom_images(bogus) == []
