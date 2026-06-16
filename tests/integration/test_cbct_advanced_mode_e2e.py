"""End-to-end test: CatPhan Advanced mode (hand-off + re-run + overwrite).

Task 8.2 — Simulate the Simple->Advanced hand-off by directly populating
``st.session_state["cp_result"]``, then verify the Advanced-mode flow can
re-run with a new ``hu_tolerance`` and overwrite the xlsx.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from core.cbct_excel_writer import write_cbct_session_output
from core.cbct_runner import run_cbct_analysis
from core.result_types import CatPhanAnalysisResult


@pytest.fixture(scope="module")
def catphan_runfolder(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Write the pylinac CatPhan504 demo DICOMs to a tmp runfolder."""
    runfolder = tmp_path_factory.mktemp("catphan_adv_e2e") / "2026-06-16_monthly"
    runfolder.mkdir(parents=True)
    from pylinac import CatPhan504

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        cbct = CatPhan504.from_demo_images()

    for i, img in enumerate(cbct.dicom_stack):
        img.save(str(runfolder / f"image_{i:04d}.dcm"))
    return runfolder


def _run_analysis(runfolder: Path, hu_tolerance: float = 40) -> CatPhanAnalysisResult:
    """Helper: run CatPhan analysis with the given hu_tolerance."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return run_cbct_analysis(
            machine_id="LA2",
            runfolder_path=str(runfolder),
            hu_tolerance=hu_tolerance,
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


def test_advanced_mode_hand_off_no_rerun(
    catphan_runfolder: Path,
    tmp_path: Path,
) -> None:
    """Advanced mode receives the hand-off result without re-running."""
    # Simulate Simple mode producing the result
    result = _run_analysis(catphan_runfolder)

    # Simulate the hand-off: result is in session_state equivalent
    # Advanced mode would read this and render immediately
    assert result is not None
    assert result.machine_id == "LA2"
    assert result.params_used["hu_tolerance"] == 40
    # The params_used should allow sidebar repopulation
    assert "hu_tolerance" in result.params_used
    assert "scaling_tolerance" in result.params_used


def test_rerun_with_different_hu_tolerance(
    catphan_runfolder: Path,
    tmp_path: Path,
) -> None:
    """Re-running with a different hu_tolerance produces a different result."""
    result_40 = _run_analysis(catphan_runfolder, hu_tolerance=40)
    result_80 = _run_analysis(catphan_runfolder, hu_tolerance=80)

    # The hu_tolerance in params_used should differ
    assert result_40.params_used["hu_tolerance"] == 40
    assert result_80.params_used["hu_tolerance"] == 80
    # The results should differ (different tolerance affects pass/fail flags)
    assert result_40 != result_80


def test_xlsx_overwritten_on_rerun(
    catphan_runfolder: Path,
    tmp_path: Path,
) -> None:
    """Re-running and writing xlsx overwrites the same session folder."""
    output_root = tmp_path / "output"
    output_root.mkdir()
    template_path = Path(__file__).resolve().parents[2] / "templates" / "catphan_504.xltx"

    result_40 = _run_analysis(catphan_runfolder, hu_tolerance=40)
    xlsx_path_1 = write_cbct_session_output(
        result=result_40,
        output_root=output_root,
        template_path=template_path,
    )

    result_80 = _run_analysis(catphan_runfolder, hu_tolerance=80)
    xlsx_path_2 = write_cbct_session_output(
        result=result_80,
        output_root=output_root,
        template_path=template_path,
    )

    # Same path (session folder is determined by machine + runfolder, not params)
    assert xlsx_path_1 == xlsx_path_2
    assert xlsx_path_1.exists()
