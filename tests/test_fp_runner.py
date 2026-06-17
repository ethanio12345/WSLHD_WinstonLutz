"""Tests for ``core/fp_runner.py`` — the FieldAnalysis wrapper.

Uses pylinac's ``flatsym_demo.dcm`` demo image (cached locally by pylinac's
``retrieve_demo_file``) for a deterministic synthetic dataset, mirroring the
CatPhan runner test pattern.
"""

from __future__ import annotations

import pickle
import shutil
import warnings
from pathlib import Path

import pytest

from core.config import FP_SUMMARY_NAMES
from core.result_types import FieldAnalysisResult

# ---------------------------------------------------------------------------
# Fixtures — copy the pylinac demo DICOM to a tmp path
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fp_demo_image(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Copy the pylinac flatsym demo DICOM to a tmp path and return it."""
    from pylinac.core.io import retrieve_demo_file

    src = Path(retrieve_demo_file(name="flatsym_demo.dcm"))
    dst_dir = tmp_path_factory.mktemp("fp_demo")
    dst = dst_dir / "flatsym_demo.dcm"
    shutil.copy(str(src), str(dst))
    return dst


@pytest.fixture
def analysis_result(fp_demo_image: Path) -> FieldAnalysisResult:
    """Run the analysis once and return the result."""
    from core.fp_runner import run_fp_analysis

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return run_fp_analysis(
            machine_id="TEST",
            image_path=str(fp_demo_image),
            image_display_name="flatsym_demo.dcm",
        )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_run_fp_analysis_happy_path(analysis_result: FieldAnalysisResult) -> None:
    """Analysis runs and returns a FieldAnalysisResult with identity fields."""
    assert analysis_result.machine_id == "TEST"
    assert analysis_result.image_path != ""
    assert analysis_result.image_display_name == "flatsym_demo.dcm"
    assert analysis_result.session_date != ""


# ---------------------------------------------------------------------------
# 29-cell summary mapping completeness
# ---------------------------------------------------------------------------


def test_summary_mapping_completeness(analysis_result: FieldAnalysisResult) -> None:
    """Every one of the 29 named-cell metrics is present in the summary dict."""
    for name in FP_SUMMARY_NAMES:
        assert name in analysis_result.summary, f"Missing summary key: {name}"


def test_summary_protocol_metrics_match_protocol_results(
    analysis_result: FieldAnalysisResult,
) -> None:
    """The four protocol named cells match the protocol_results sub-dict."""
    pr = analysis_result.protocol_results
    assert analysis_result.summary["flatness_vertical"] == pytest.approx(pr["flatness_vertical"])
    assert analysis_result.summary["flatness_horizontal"] == pytest.approx(
        pr["flatness_horizontal"]
    )
    assert analysis_result.summary["symmetry_vertical"] == pytest.approx(pr["symmetry_vertical"])
    assert analysis_result.summary["symmetry_horizontal"] == pytest.approx(
        pr["symmetry_horizontal"]
    )


def test_summary_geometry_populated(analysis_result: FieldAnalysisResult) -> None:
    """Field size vertical/horizontal are non-zero for the demo image."""
    assert analysis_result.summary["field_size_vertical_mm"] > 0
    assert analysis_result.summary["field_size_horizontal_mm"] > 0


def test_summary_central_roi_populated(analysis_result: FieldAnalysisResult) -> None:
    """Central ROI mean/max/min/std are populated."""
    assert analysis_result.summary["central_roi_mean"] > 0
    assert analysis_result.summary["central_roi_max"] >= analysis_result.summary["central_roi_min"]


# ---------------------------------------------------------------------------
# Profile data arrays populated (and downsampled)
# ---------------------------------------------------------------------------


def test_vert_profile_values_populated(analysis_result: FieldAnalysisResult) -> None:
    """Vertical profile values array is populated and downsampled."""
    vals = analysis_result.vert_profile_values
    assert len(vals) > 0
    assert len(vals) <= 500  # downsampled target
    assert all(isinstance(v, float) for v in vals[:5])


def test_horiz_profile_values_populated(analysis_result: FieldAnalysisResult) -> None:
    """Horizontal profile values array is populated and downsampled."""
    vals = analysis_result.horiz_profile_values
    assert len(vals) > 0
    assert len(vals) <= 500
    assert all(isinstance(v, float) for v in vals[:5])


# ---------------------------------------------------------------------------
# FFF detection
# ---------------------------------------------------------------------------


def test_detect_fff_flat_beam(fp_demo_image: Path) -> None:
    """The demo image is a flat beam (no FFF energy/string tags) → detect_fff returns False."""
    from core.fp_runner import detect_fff

    # The flatsym_demo has no Radiation Energy tag and no 'FFF' in any string
    # tag, so detection defaults to flat (False). Strategy 3 (shape heuristic)
    # was dropped during implementation — see design D2 (revised).
    result = detect_fff(fp_demo_image)
    assert result is False


def test_detect_fff_energy_tag_strategy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strategy 1: Radiation Energy tag with 'FFF' substring → True."""
    from core import fp_runner

    monkeypatch.setattr(
        fp_runner, "_extract_dicom_info_raw", lambda _p: {"energy": "6FFF", "string_values": []}
    )
    assert fp_runner.detect_fff("/fake/path.dcm") is True


def test_detect_fff_string_scan_strategy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strategy 2: string tag scan finds 'FFF' → True."""
    from core import fp_runner

    monkeypatch.setattr(
        fp_runner,
        "_extract_dicom_info_raw",
        lambda _p: {
            "energy": "",
            "string_values": [(0x0008103E, "6MV FFF field")],
        },
    )
    assert fp_runner.detect_fff("/fake/path.dcm") is True


def test_detect_fff_no_tags_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """No energy tag and no 'FFF' string → defaults to flat (False)."""
    from core import fp_runner

    monkeypatch.setattr(
        fp_runner,
        "_extract_dicom_info_raw",
        lambda _p: {
            "energy": "6",
            "string_values": [(0x0008103E, "6MV flat field")],
        },
    )
    assert fp_runner.detect_fff("/fake/path.dcm") is False


# ---------------------------------------------------------------------------
# is_FFF override propagation
# ---------------------------------------------------------------------------


def test_is_fff_override_true(fp_demo_image: Path) -> None:
    """Passing is_FFF=True forces FFF mode regardless of detection."""
    from core.fp_runner import run_fp_analysis

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = run_fp_analysis(
            machine_id="TEST",
            image_path=str(fp_demo_image),
            image_display_name="override.dcm",
            is_FFF=True,
        )
    assert result.is_fff is True


def test_is_fff_override_false(fp_demo_image: Path) -> None:
    """Passing is_FFF=False forces flat mode regardless of detection."""
    from core.fp_runner import run_fp_analysis

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = run_fp_analysis(
            machine_id="TEST",
            image_path=str(fp_demo_image),
            image_display_name="override.dcm",
            is_FFF=False,
        )
    assert result.is_fff is False


# ---------------------------------------------------------------------------
# DICOM info extraction
# ---------------------------------------------------------------------------


def test_extract_dicom_info_populated(fp_demo_image: Path) -> None:
    """extract_dicom_info returns a display string and is_fff flag."""
    from core.fp_runner import extract_dicom_info

    info = extract_dicom_info(fp_demo_image)
    assert "display_string" in info
    assert info["filename"] == "flatsym_demo.dcm"
    assert "is_fff" in info
    assert isinstance(info["is_fff"], bool)
    assert fp_demo_image.name in info["display_string"]


# ---------------------------------------------------------------------------
# Picklability
# ---------------------------------------------------------------------------


def test_result_is_picklable(analysis_result: FieldAnalysisResult) -> None:
    """FieldAnalysisResult survives pickle round-trip (required for st.cache_data)."""
    data = pickle.dumps(analysis_result)
    restored: FieldAnalysisResult = pickle.loads(data)
    assert restored.machine_id == analysis_result.machine_id
    assert restored.summary == analysis_result.summary
    assert restored.vert_profile_values == analysis_result.vert_profile_values
    assert restored.protocol_results == analysis_result.protocol_results


def test_result_frozen(analysis_result: FieldAnalysisResult) -> None:
    """The dataclass is frozen (immutable)."""
    with pytest.raises((AttributeError, Exception)):
        analysis_result.machine_id = "OTHER"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Cache key components
# ---------------------------------------------------------------------------


def test_cache_key_components() -> None:
    """The run_fp_analysis signature includes all params needed for cache-key."""
    import inspect

    from core.fp_runner import run_fp_analysis

    sig = inspect.signature(run_fp_analysis)
    expected_params = {
        "machine_id",
        "image_path",
        "image_display_name",
        "protocol",
        "centering",
        "vert_position",
        "horiz_position",
        "vert_width",
        "horiz_width",
        "in_field_ratio",
        "slope_exclusion_ratio",
        "is_FFF",
        "penumbra",
        "interpolation",
        "edge_detection_method",
        "edge_smoothing_ratio",
        "hill_window_ratio",
    }
    actual_params = set(sig.parameters.keys())
    assert expected_params.issubset(actual_params), (
        f"Missing cache-key params: {expected_params - actual_params}"
    )
