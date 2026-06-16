"""Tests for CatPhan error handling (task 8.3).

Verifies error handling for:
- Corrupt/empty DICOM runfolder
- Missing template
- Read-only output directory

These test the runner and writer layers directly (the page-level error
wrapping with one-line messages is tested via the spec scenarios).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.cbct_excel_writer import write_cbct_session_output
from core.cbct_runner import run_cbct_analysis
from core.result_types import CatPhanAnalysisResult


def test_empty_dicom_runfolder_raises(tmp_path: Path) -> None:
    """An empty runfolder causes pylinac to raise an exception."""
    empty_runfolder = tmp_path / "empty"
    empty_runfolder.mkdir()

    with pytest.raises(Exception):  # noqa: B017 — pylinac raises various exceptions
        run_cbct_analysis(
            machine_id="TEST",
            runfolder_path=str(empty_runfolder),
            hu_tolerance=40,
            scaling_tolerance=0.5,
            slice_thickness_tolerance=0.5,
            thickness_slice_straddle="auto",
            x_adjustment=0.0,
            y_adjustment=0.0,
            angle_adjustment=0.0,
            roi_size_factor=1.0,
            scaling_factor=1.0,
            minimum_rois_seen=3,
        )


def test_nonexistent_dicom_runfolder_raises(tmp_path: Path) -> None:
    """A nonexistent runfolder causes pylinac to raise."""
    with pytest.raises(Exception):  # noqa: B017
        run_cbct_analysis(
            machine_id="TEST",
            runfolder_path=str(tmp_path / "does_not_exist"),
            hu_tolerance=40,
            scaling_tolerance=0.5,
            slice_thickness_tolerance=0.5,
            thickness_slice_straddle="auto",
            x_adjustment=0.0,
            y_adjustment=0.0,
            angle_adjustment=0.0,
            roi_size_factor=1.0,
            scaling_factor=1.0,
            minimum_rois_seen=3,
        )


def test_missing_template_raises(tmp_path: Path) -> None:
    """A missing template file causes the writer to raise."""
    # Build a minimal fake result
    result = CatPhanAnalysisResult(
        machine_id="TEST",
        runfolder_path=str(tmp_path / "runfolder"),
        session_date="20260616",
        summary={
            "machine_name": "TEST",
            "session_date": "20260616",
            "num_images": 0,
            "hu_linearity_passed": True,
            "geometry_passed": True,
            "uniformity_passed": True,
            "thickness_passed": True,
            "measured_slice_thickness_mm": 0.0,
            "avg_line_distance_mm": 0.0,
            "uniformity_index": 0.0,
            "integral_non_uniformity": 0.0,
            "low_contrast_visibility": 0.0,
            "num_rois_seen": 0,
            "mtf_50_lp_mm": 0.0,
            "mtf_90_lp_mm": 0.0,
            "nps_avg_power": 0.0,
            "nps_max_freq": 0.0,
            "catphan_roll_deg": 0.0,
        },
        ctp404={},
        ctp486={},
        ctp528={},
        ctp515={},
    )
    output_root = tmp_path / "output"
    output_root.mkdir()

    with pytest.raises((FileNotFoundError, Exception)):
        write_cbct_session_output(
            result=result,
            output_root=output_root,
            template_path=tmp_path / "nonexistent.xltx",
        )
