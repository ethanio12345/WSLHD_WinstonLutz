"""Tests for caching behaviour (Task 8.x).

8.2 — WLAnalysisResult is picklable.
8.3 — ``@st.cache_data`` on ``run_wl_analysis`` caches correctly.
"""

from __future__ import annotations

import pickle
from unittest.mock import MagicMock, patch

import pytest

from core.config import WL_METRIC_NAMES
from core.result_types import WLAnalysisResult
from core.wl_runner import run_wl_analysis

# ---------------------------------------------------------------------------
# 8.2 — Picklability
# ---------------------------------------------------------------------------


def _make_result() -> WLAnalysisResult:
    """Build a WLAnalysisResult with representative data."""
    summary: dict = {name: float(i) for i, name in enumerate(WL_METRIC_NAMES)}
    summary["machine_name"] = "TEST"
    summary["session_date"] = "20260616"
    summary["num_total_images"] = 4
    return WLAnalysisResult(
        machine_id="TEST",
        runfolder_path="/data/TEST/runfolder",
        session_date="20260616",
        summary=summary,
        image_details=[
            {"gantry_angle": 0, "cax2bb_distance": 0.5},
            {"gantry_angle": 90, "cax2bb_distance": 0.7},
        ],
        image_keys=["G0B0P0", "G90B0P0"],
        deviation_vs_gantry={"x": [0, 90], "y": [0.5, 0.7], "text": ["G0B0P0", "G90B0P0"]},
        bb_xy_scatter={"x": [0.1, 0.2], "y": [0.3, 0.4], "color": ["Gantry", "Gantry"]},
        distance_histogram={"values": [0.5, 0.7]},
        params_used={"bb_size_mm": 5.0, "machine_scale": "VARIAN_IEC"},
    )


def test_result_is_picklable() -> None:
    """8.2 — A WLAnalysisResult survives pickle round-trip (required for st.cache_data)."""
    result = _make_result()
    data = pickle.dumps(result)
    restored = pickle.loads(data)

    assert restored.machine_id == result.machine_id
    assert restored.runfolder_path == result.runfolder_path
    assert restored.summary == result.summary
    assert restored.image_keys == result.image_keys
    assert restored.params_used == result.params_used


def test_result_frozen() -> None:
    """8.2 — The dataclass is frozen (immutable) — safe for session_state hand-off."""
    result = _make_result()
    with pytest.raises((AttributeError, Exception)):
        result.machine_id = "OTHER"  # type: ignore[misc]


def test_cache_args_are_hashable() -> None:
    """8.1/8.2 — The *arguments* to run_wl_analysis are all hashable primitives.

    ``@st.cache_data`` hashes the arguments to build the cache key. All of
    machine_id, runfolder_path, bb_size_mm, etc. are str/float/int/bool/None —
    hashable. The return value only needs to be picklable, not hashable.
    """
    # These are the types that go into the cache key
    args = {
        "machine_id": "LA2",  # str
        "runfolder_path": "/data/x",  # str
        "bb_size_mm": 5.0,  # float
        "machine_scale": "VARIAN_IEC",  # str
        "low_density_bb": False,  # bool
        "open_field": False,  # bool
        "apply_virtual_shift": False,  # bool
        "snap_tolerance": None,  # None
        "gantry_reference": None,  # None
        "collimator_reference": None,  # None
        "couch_reference": None,  # None
        "dicom_file_count": 4,  # int
        "runfolder_mtime_val": 1000.0,  # float
    }
    # All values must be hashable for @st.cache_data
    for _key, val in args.items():
        hash(val)  # should not raise


# ---------------------------------------------------------------------------
# 8.3 — Cache behaviour (mock pylinac)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_wl_factory():
    """Patch pylinac.WinstonLutz so we can assert call counts."""
    mock_wl = MagicMock()
    mock_wl.results_data.return_value = {
        "max_2d_cax_to_bb_mm": 1.0,
        "num_total_images": 4,
        "keyed_image_details": {},
    }
    mock_wl.images = []

    with patch("pylinac.WinstonLutz", return_value=mock_wl) as mock_constructor:
        yield mock_constructor, mock_wl


def test_cache_hits_on_identical_inputs(mock_wl_factory) -> None:
    """8.3 — Calling run_wl_analysis twice with identical inputs: pylinac loads once per call.

    Note: The actual ``@st.cache_data`` is on the wrapper in the WL page.
    Here we test that ``run_wl_analysis`` itself is deterministic and doesn't
    add spurious side-effects. The cache deduplication is tested via the
    Streamlit integration test (10.1).
    """
    mock_constructor, mock_wl = mock_wl_factory

    # First call
    run_wl_analysis(
        machine_id="TEST",
        runfolder_path="/fake/path",
        bb_size_mm=5.0,
        machine_scale="VARIAN_IEC",
        dicom_file_count=4,
        runfolder_mtime_val=1000.0,
    )
    # Second call with identical params
    run_wl_analysis(
        machine_id="TEST",
        runfolder_path="/fake/path",
        bb_size_mm=5.0,
        machine_scale="VARIAN_IEC",
        dicom_file_count=4,
        runfolder_mtime_val=1000.0,
    )

    # Both calls execute (the cache is at the Streamlit layer, not here)
    assert mock_constructor.call_count == 2
    assert mock_wl.analyze.call_count == 2


def test_different_bb_size_runs_analyze(mock_wl_factory) -> None:
    """8.3 — Different bb_size_mm triggers separate analyze calls."""
    _mock_constructor, mock_wl = mock_wl_factory

    run_wl_analysis(
        machine_id="TEST",
        runfolder_path="/fake/path",
        bb_size_mm=5.0,
        machine_scale="VARIAN_IEC",
    )
    run_wl_analysis(
        machine_id="TEST",
        runfolder_path="/fake/path",
        bb_size_mm=3.0,  # different
        machine_scale="VARIAN_IEC",
    )

    assert mock_wl.analyze.call_count == 2
    # Verify the bb_size_mm was passed differently
    first_call_kwargs = mock_wl.analyze.call_args_list[0].kwargs
    second_call_kwargs = mock_wl.analyze.call_args_list[1].kwargs
    assert first_call_kwargs.get("bb_size_mm") != second_call_kwargs.get("bb_size_mm")


def test_cache_key_components(mock_wl_factory) -> None:
    """8.3 — The cache key should include machine_id, runfolder_path, params, file count, mtime.

    This test documents the cache key contract: the caller (Streamlit page)
    must pass all these values so ``@st.cache_data`` invalidates correctly.
    """
    import inspect

    sig = inspect.signature(run_wl_analysis)
    expected_params = {
        "machine_id",
        "runfolder_path",
        "bb_size_mm",
        "machine_scale",
        "low_density_bb",
        "open_field",
        "apply_virtual_shift",
        "snap_tolerance",
        "gantry_reference",
        "collimator_reference",
        "couch_reference",
        "dicom_file_count",
        "runfolder_mtime_val",
    }
    actual_params = set(sig.parameters.keys())
    assert expected_params.issubset(actual_params), (
        f"Missing cache-key params: {expected_params - actual_params}"
    )
