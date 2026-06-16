"""Tests for ``core/cbct_runner.py`` — the CatPhan 504 analysis wrapper.

Uses ``CatPhan504.from_demo_images()`` to get a deterministic synthetic dataset
(per design D8 open question 4 — no committed binary fixtures needed).
"""

from __future__ import annotations

import pickle
import warnings
from pathlib import Path

import pytest

from core.config import CATPHAN_SUMMARY_NAMES
from core.result_types import CatPhanAnalysisResult

# ---------------------------------------------------------------------------
# Fixtures — write the pylinac demo CatPhan DICOMs to a tmp runfolder
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def catphan_runfolder(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Write the pylinac CatPhan504 demo images to a tmp runfolder.

    ``CatPhan504.from_demo_images()`` downloads the demo zip (cached) and
    returns an un-analysed object. We write its underlying DICOM stack to disk
    so ``run_cbct_analysis`` can load it like a real runfolder.
    """
    runfolder = tmp_path_factory.mktemp("catphan_demo")
    from pylinac import CatPhan504

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        cbct = CatPhan504.from_demo_images()

    # Write the demo DICOMs to the runfolder so run_cbct_analysis can load them
    for i, img in enumerate(cbct.dicom_stack):
        img.save(str(runfolder / f"image_{i:04d}.dcm"))
    return runfolder


@pytest.fixture
def analysis_result(catphan_runfolder: Path) -> CatPhanAnalysisResult:
    """Run the analysis once and return the result."""
    from core.cbct_runner import run_cbct_analysis

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return run_cbct_analysis(
            machine_id="TEST",
            runfolder_path=str(catphan_runfolder),
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


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_run_cbct_analysis_happy_path(analysis_result: CatPhanAnalysisResult) -> None:
    """Analysis runs and returns a CatPhanAnalysisResult with identity fields."""
    assert analysis_result.machine_id == "TEST"
    assert analysis_result.runfolder_path != ""
    assert analysis_result.session_date != ""


# ---------------------------------------------------------------------------
# Per-CTP-module dict population
# ---------------------------------------------------------------------------


def test_ctp404_dict_populated(analysis_result: CatPhanAnalysisResult) -> None:
    """CTP404 detail dict contains the expected keys."""
    assert "hu_rois" in analysis_result.ctp404
    assert "avg_line_distance_mm" in analysis_result.ctp404
    assert "measured_slice_thickness_mm" in analysis_result.ctp404
    assert "hu_linearity_passed" in analysis_result.ctp404


def test_ctp486_dict_populated(analysis_result: CatPhanAnalysisResult) -> None:
    """CTP486 detail dict contains the expected keys."""
    assert "rois" in analysis_result.ctp486
    assert "uniformity_index" in analysis_result.ctp486
    assert "nps_avg_power" in analysis_result.ctp486


def test_ctp528_dict_populated(analysis_result: CatPhanAnalysisResult) -> None:
    """CTP528 detail dict contains the expected keys."""
    assert "mtf_lp_mm" in analysis_result.ctp528
    mtf = analysis_result.ctp528["mtf_lp_mm"]
    assert "50" in mtf
    assert "90" in mtf


def test_ctp515_dict_populated(analysis_result: CatPhanAnalysisResult) -> None:
    """CTP515 detail dict contains the expected keys."""
    assert "num_rois_seen" in analysis_result.ctp515
    assert "roi_results" in analysis_result.ctp515


# ---------------------------------------------------------------------------
# 19-cell summary mapping completeness
# ---------------------------------------------------------------------------


def test_summary_mapping_completeness(analysis_result: CatPhanAnalysisResult) -> None:
    """Every one of the 18 named-cell metrics is present in the summary dict."""
    for name in CATPHAN_SUMMARY_NAMES:
        assert name in analysis_result.summary, f"Missing summary key: {name}"


def test_summary_pass_fail_flags_are_bool(analysis_result: CatPhanAnalysisResult) -> None:
    """The four pass/fail flags are booleans."""
    flags = [
        "hu_linearity_passed",
        "geometry_passed",
        "uniformity_passed",
        "thickness_passed",
    ]
    for flag in flags:
        assert isinstance(analysis_result.summary[flag], bool), f"{flag} should be bool"


def test_summary_mtf_values_match_ctp528(analysis_result: CatPhanAnalysisResult) -> None:
    """mtf_50_lp_mm and mtf_90_lp_mm match the CTP528 mtf_lp_mm values."""
    mtf_lp_mm = analysis_result.ctp528["mtf_lp_mm"]
    assert analysis_result.summary["mtf_50_lp_mm"] == pytest.approx(float(mtf_lp_mm["50"]))
    assert analysis_result.summary["mtf_90_lp_mm"] == pytest.approx(float(mtf_lp_mm["90"]))


# ---------------------------------------------------------------------------
# Plotly arrays shape/values
# ---------------------------------------------------------------------------


def test_mtf_curve_shape(analysis_result: CatPhanAnalysisResult) -> None:
    """MTF curve has 9 points (10%-90% in steps of 10)."""
    curve = analysis_result.mtf_curve
    assert len(curve["x"]) == 9
    assert len(curve["y"]) == 9
    assert curve["x"] == [10, 20, 30, 40, 50, 60, 70, 80, 90]


def test_hu_linearity_scatter_shape(analysis_result: CatPhanAnalysisResult) -> None:
    """HU linearity scatter has 7 materials (Air, PMP, LDPE, Poly, Acrylic, Delrin, Teflon)."""
    scatter = analysis_result.hu_linearity_scatter
    assert len(scatter["names"]) == 7
    assert len(scatter["nominal"]) == 7
    assert len(scatter["measured"]) == 7
    assert "Air" in scatter["names"]
    assert "Teflon" in scatter["names"]


# ---------------------------------------------------------------------------
# Picklability
# ---------------------------------------------------------------------------


def test_result_is_picklable(analysis_result: CatPhanAnalysisResult) -> None:
    """CatPhanAnalysisResult survives pickle round-trip (required for st.cache_data)."""
    data = pickle.dumps(analysis_result)
    restored: CatPhanAnalysisResult = pickle.loads(data)
    assert restored.machine_id == analysis_result.machine_id
    assert restored.summary == analysis_result.summary
    assert restored.ctp404 == analysis_result.ctp404
    assert restored.mtf_curve == analysis_result.mtf_curve


def test_result_frozen(analysis_result: CatPhanAnalysisResult) -> None:
    """The dataclass is frozen (immutable)."""
    with pytest.raises((AttributeError, Exception)):
        analysis_result.machine_id = "OTHER"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Cache key components
# ---------------------------------------------------------------------------


def test_cache_key_components() -> None:
    """The run_cbct_analysis signature includes all params needed for cache-key."""
    import inspect

    from core.cbct_runner import run_cbct_analysis

    sig = inspect.signature(run_cbct_analysis)
    expected_params = {
        "machine_id",
        "runfolder_path",
        "hu_tolerance",
        "scaling_tolerance",
        "slice_thickness_tolerance",
        "thickness_slice_straddle",
        "x_adjustment",
        "y_adjustment",
        "angle_adjustment",
        "roi_size_factor",
        "scaling_factor",
        "minimum_rois_seen",
        "dicom_file_count",
        "runfolder_mtime",
    }
    actual_params = set(sig.parameters.keys())
    assert expected_params.issubset(actual_params), (
        f"Missing cache-key params: {expected_params - actual_params}"
    )
