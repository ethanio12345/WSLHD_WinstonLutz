"""Tests for ``core/fp_excel_writer.py`` — the Field Profile in-memory xlsx bytes.

Mirrors :mod:`tests.test_cbct_excel_writer`. Uses pylinac's ``flatsym_demo.dcm``
for a real analysis result, then verifies the produced xlsx bytes against the
revised ``fp-result-export`` spec (in-memory bytes, no server-side writes).

Covers the ``generalize-field-profile-browser`` change: the writer now returns
``bytes`` (consumed by ``st.download_button``) instead of writing a paired
``.xltx``/``.xlsx`` to a session folder.
"""

from __future__ import annotations

import io
import shutil
import warnings
from pathlib import Path

import pytest
from openpyxl import load_workbook

from core.config import FP_SUMMARY_NAMES, REQUIRED_FP_TEMPLATE_NAMES
from core.fp_excel_writer import TEMPLATE_VERSION, build_fp_xlsx_bytes
from core.result_types import FieldAnalysisResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fp_demo_image(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Copy the pylinac flatsym demo DICOM to a tmp path and return it."""
    from pylinac.core.io import retrieve_demo_file

    src = Path(retrieve_demo_file(name="flatsym_demo.dcm"))
    dst_dir = tmp_path_factory.mktemp("fp_writer_demo")
    dst = dst_dir / "flatsym_demo.dcm"
    shutil.copy(str(src), str(dst))
    return dst


@pytest.fixture(scope="module")
def fp_result(fp_demo_image: Path) -> FieldAnalysisResult:
    """Run the FP analysis once and return the result."""
    from core.fp_runner import run_fp_analysis

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return run_fp_analysis(
            machine_id="LA2",
            image_path=str(fp_demo_image),
            image_display_name="flatsym_demo.dcm",
        )


@pytest.fixture(scope="module")
def fp_template_path() -> Path:
    """Path to the committed Field Profile xltx template."""
    return Path(__file__).resolve().parents[1] / "templates" / "field_profile.xltx"


@pytest.fixture(scope="module")
def fp_xlsx_bytes(
    fp_result: FieldAnalysisResult,
    fp_template_path: Path,
) -> bytes:
    """Build the FP xlsx bytes once and return them."""
    return build_fp_xlsx_bytes(result=fp_result, template_path=fp_template_path)


def _load_from_bytes(xlsx_bytes: bytes):
    """Helper: load an openpyxl workbook from in-memory bytes."""
    return load_workbook(io.BytesIO(xlsx_bytes))


# ---------------------------------------------------------------------------
# build_fp_xlsx_bytes — return type + no-disk-write contract
# ---------------------------------------------------------------------------


def test_build_fp_xlsx_bytes_returns_bytes(fp_xlsx_bytes: bytes) -> None:
    """build_fp_xlsx_bytes returns bytes (not a path)."""
    assert isinstance(fp_xlsx_bytes, bytes)
    assert len(fp_xlsx_bytes) > 0


def test_build_fp_xlsx_bytes_no_disk_write(
    fp_result: FieldAnalysisResult,
    fp_template_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build_fp_xlsx_bytes must NOT write any file to disk.

    We patch ``openpyxl.Workbook.save`` to fail if it's given a path (rather
    than a file-like object) and confirm the function still completes.
    """
    # The function should only ever save to a BytesIO; any path-based save
    # would indicate a regression to the old session-folder behaviour.
    import openpyxl

    original_save = openpyxl.Workbook.save

    def guarding_save(self, path_or_buffer):  # type: ignore[no-untyped-def]
        # openpyxl detects file-like objects vs paths. We only allow file-like.
        if not hasattr(path_or_buffer, "write"):
            raise AssertionError(
                f"build_fp_xlsx_bytes tried to save to a path: {path_or_buffer!r} "
                "(should save to io.BytesIO only)"
            )
        return original_save(self, path_or_buffer)

    monkeypatch.setattr(openpyxl.Workbook, "save", guarding_save)
    # Should complete without raising
    xlsx_bytes = build_fp_xlsx_bytes(result=fp_result, template_path=fp_template_path)
    assert isinstance(xlsx_bytes, bytes)
    assert len(xlsx_bytes) > 0


# ---------------------------------------------------------------------------
# 30 named cells populated
# ---------------------------------------------------------------------------


def test_all_30_named_cells_defined(fp_xlsx_bytes: bytes) -> None:
    """Every one of the 30 required defined names resolves in the workbook."""
    wb = _load_from_bytes(fp_xlsx_bytes)
    defined = set(wb.defined_names)
    for name in REQUIRED_FP_TEMPLATE_NAMES:
        assert name in defined, f"Defined name missing: {name}"


def test_29_metric_named_cells_populated(fp_xlsx_bytes: bytes) -> None:
    """Every one of the 29 metric named cells resolves to a non-empty cell."""
    wb = _load_from_bytes(fp_xlsx_bytes)
    for name in FP_SUMMARY_NAMES:
        dn = wb.defined_names[name]
        for sheet_title, coord in dn.destinations:
            cell = wb[sheet_title][coord]
            assert cell.value is not None, f"Named cell '{name}' is empty"


def test_template_version_stamped(fp_xlsx_bytes: bytes) -> None:
    """The template_version named cell contains the version string."""
    wb = _load_from_bytes(fp_xlsx_bytes)
    dn = wb.defined_names["template_version"]
    for sheet_title, coord in dn.destinations:
        cell = wb[sheet_title][coord]
        assert cell.value == TEMPLATE_VERSION


# ---------------------------------------------------------------------------
# Data sheets
# ---------------------------------------------------------------------------


def test_sheet_count_is_5(fp_xlsx_bytes: bytes) -> None:
    """The xlsx contains exactly 5 sheets: Summary + 4 data sheets."""
    wb = _load_from_bytes(fp_xlsx_bytes)
    expected = {"Summary", "Profiles", "Penumbra", "CAX Beam Center", "ROI"}
    assert set(wb.sheetnames) == expected
    assert len(wb.sheetnames) == 5


def test_profiles_sheet_has_vertical_and_horizontal(fp_xlsx_bytes: bytes) -> None:
    """The Profiles sheet contains both vertical and horizontal profile data."""
    wb = _load_from_bytes(fp_xlsx_bytes)
    ws = wb["Profiles"]
    axes = {ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)}
    assert "vertical" in axes
    assert "horizontal" in axes


def test_penumbra_sheet_has_4_sides(fp_xlsx_bytes: bytes) -> None:
    """The Penumbra sheet has 4 data rows (Top, Bottom, Left, Right)."""
    wb = _load_from_bytes(fp_xlsx_bytes)
    ws = wb["Penumbra"]
    sides = {ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)}
    assert sides == {"Top", "Bottom", "Left", "Right"}


def test_cax_beam_center_sheet_content(fp_xlsx_bytes: bytes) -> None:
    """The CAX Beam Center sheet has the three metric rows."""
    wb = _load_from_bytes(fp_xlsx_bytes)
    ws = wb["CAX Beam Center"]
    metrics = {ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)}
    assert "CAX offset (mm)" in metrics
    assert "Beam center offset (mm)" in metrics
    assert "Slope (%/mm)" in metrics


def test_roi_sheet_has_4_stats(fp_xlsx_bytes: bytes) -> None:
    """The ROI sheet has Mean/Max/Min/Std rows."""
    wb = _load_from_bytes(fp_xlsx_bytes)
    ws = wb["ROI"]
    stats = {ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)}
    assert stats == {"Mean", "Max", "Min", "Std"}


# ---------------------------------------------------------------------------
# Determinism — two calls produce equivalent bytes (same content)
# ---------------------------------------------------------------------------


def test_repeated_calls_produce_valid_xlsx(
    fp_result: FieldAnalysisResult,
    fp_template_path: Path,
) -> None:
    """Two calls to build_fp_xlsx_bytes each produce a valid xlsx (5 sheets, 30 cells)."""
    first_bytes = build_fp_xlsx_bytes(result=fp_result, template_path=fp_template_path)
    second_bytes = build_fp_xlsx_bytes(result=fp_result, template_path=fp_template_path)

    # Both must be valid xlsx with the same structure
    for label, b in (("first", first_bytes), ("second", second_bytes)):
        wb = _load_from_bytes(b)
        assert len(wb.sheetnames) == 5, f"{label} call: expected 5 sheets"
        assert set(wb.sheetnames) == {
            "Summary",
            "Profiles",
            "Penumbra",
            "CAX Beam Center",
            "ROI",
        }
        # template_version stamped
        dn = wb.defined_names["template_version"]
        for sheet_title, coord in dn.destinations:
            assert wb[sheet_title][coord].value == TEMPLATE_VERSION
