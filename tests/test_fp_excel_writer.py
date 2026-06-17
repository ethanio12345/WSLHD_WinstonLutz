"""Tests for ``core/fp_excel_writer.py`` — the Field Profile Excel output.

Mirrors :mod:`tests.test_cbct_excel_writer`. Uses pylinac's ``flatsym_demo.dcm``
for a real analysis result, then verifies the written xlsx structure against
the ``fp-result-export`` spec.
"""

from __future__ import annotations

import shutil
import warnings
from pathlib import Path

import pytest
from openpyxl import load_workbook

from core.config import FP_SUMMARY_NAMES, REQUIRED_FP_TEMPLATE_NAMES
from core.fp_excel_writer import TEMPLATE_VERSION, write_fp_session_output
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
def written_xlsx(
    fp_result: FieldAnalysisResult,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """Write the FP session output once and return the xlsx path."""
    output_root = tmp_path_factory.mktemp("fp_output")
    template_path = Path(__file__).resolve().parents[1] / "templates" / "field_profile.xltx"
    return write_fp_session_output(
        result=fp_result,
        output_root=output_root,
        template_path=template_path,
    )


# ---------------------------------------------------------------------------
# Paired xltx/xlsx output
# ---------------------------------------------------------------------------


def test_session_folder_created(written_xlsx: Path) -> None:
    """Session folder at <output_root>/FP/LA2_FP_<image_stem>/."""
    session_dir = written_xlsx.parent
    assert session_dir.name == "LA2_FP_flatsym_demo"
    assert session_dir.parent.name == "FP"


def test_paired_xltx_exists(written_xlsx: Path) -> None:
    """The .xltx template copy exists alongside the .xlsx."""
    xltx = written_xlsx.with_suffix(".xltx")
    assert xltx.exists(), f"Paired xltx missing: {xltx}"


def test_xlsx_exists(written_xlsx: Path) -> None:
    """The .xlsx file exists with the expected name."""
    assert written_xlsx.exists()
    assert written_xlsx.name == "LA2_FP_flatsym_demo.xlsx"


def test_output_path_layout(written_xlsx: Path) -> None:
    """Full path layout matches <output>/FP/LA2_FP_flatsym_demo/LA2_FP_flatsym_demo.xlsx."""
    parts = written_xlsx.parts
    # parts[-1] = xlsx filename, parts[-2] = session folder, parts[-3] = FP module dir
    assert parts[-3] == "FP"
    assert parts[-2] == "LA2_FP_flatsym_demo"
    assert parts[-1] == "LA2_FP_flatsym_demo.xlsx"


# ---------------------------------------------------------------------------
# 30 named cells populated
# ---------------------------------------------------------------------------


def test_all_30_named_cells_defined(written_xlsx: Path) -> None:
    """Every one of the 30 required defined names resolves in the workbook."""
    wb = load_workbook(str(written_xlsx))
    defined = set(wb.defined_names)
    for name in REQUIRED_FP_TEMPLATE_NAMES:
        assert name in defined, f"Defined name missing: {name}"


def test_29_metric_named_cells_populated(written_xlsx: Path) -> None:
    """Every one of the 29 metric named cells resolves to a non-empty cell."""
    wb = load_workbook(str(written_xlsx))
    for name in FP_SUMMARY_NAMES:
        dn = wb.defined_names[name]
        for sheet_title, coord in dn.destinations:
            cell = wb[sheet_title][coord]
            assert cell.value is not None, f"Named cell '{name}' is empty"


def test_template_version_stamped(written_xlsx: Path) -> None:
    """The template_version named cell contains the version string."""
    wb = load_workbook(str(written_xlsx))
    dn = wb.defined_names["template_version"]
    for sheet_title, coord in dn.destinations:
        cell = wb[sheet_title][coord]
        assert cell.value == TEMPLATE_VERSION


# ---------------------------------------------------------------------------
# Data sheets
# ---------------------------------------------------------------------------


def test_sheet_count_is_5(written_xlsx: Path) -> None:
    """The xlsx contains exactly 5 sheets: Summary + 4 data sheets."""
    wb = load_workbook(str(written_xlsx))
    expected = {"Summary", "Profiles", "Penumbra", "CAX Beam Center", "ROI"}
    assert set(wb.sheetnames) == expected
    assert len(wb.sheetnames) == 5


def test_profiles_sheet_has_vertical_and_horizontal(written_xlsx: Path) -> None:
    """The Profiles sheet contains both vertical and horizontal profile data."""
    wb = load_workbook(str(written_xlsx))
    ws = wb["Profiles"]
    axes = {ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)}
    assert "vertical" in axes
    assert "horizontal" in axes


def test_penumbra_sheet_has_4_sides(written_xlsx: Path) -> None:
    """The Penumbra sheet has 4 data rows (Top, Bottom, Left, Right)."""
    wb = load_workbook(str(written_xlsx))
    ws = wb["Penumbra"]
    sides = {ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)}
    assert sides == {"Top", "Bottom", "Left", "Right"}


def test_cax_beam_center_sheet_content(written_xlsx: Path) -> None:
    """The CAX Beam Center sheet has the three metric rows."""
    wb = load_workbook(str(written_xlsx))
    ws = wb["CAX Beam Center"]
    metrics = {ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)}
    assert "CAX offset (mm)" in metrics
    assert "Beam center offset (mm)" in metrics
    assert "Slope (%/mm)" in metrics


def test_roi_sheet_has_4_stats(written_xlsx: Path) -> None:
    """The ROI sheet has Mean/Max/Min/Std rows."""
    wb = load_workbook(str(written_xlsx))
    ws = wb["ROI"]
    stats = {ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)}
    assert stats == {"Mean", "Max", "Min", "Std"}


# ---------------------------------------------------------------------------
# Re-run overwrites same session
# ---------------------------------------------------------------------------


def test_rerun_overwrites_session(
    fp_result: FieldAnalysisResult,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """A second write to the same session overwrites the .xlsx in place."""
    output_root = tmp_path_factory.mktemp("fp_rerun_output")
    template_path = Path(__file__).resolve().parents[1] / "templates" / "field_profile.xltx"

    first = write_fp_session_output(
        result=fp_result, output_root=output_root, template_path=template_path
    )

    # Second write (simulating a re-run with different params → same image stem)
    second = write_fp_session_output(
        result=fp_result, output_root=output_root, template_path=template_path
    )
    assert second == first
    assert second.exists()
    # The file was overwritten (path identical)
    assert second.parent == first.parent
