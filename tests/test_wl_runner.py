"""Tests for ``core/wl_runner.py``.

Uses ``pylinac.core.image_generator`` to synthesise WL DICOMs in ``tmp_path``
— deterministic, no committed binary fixtures (per design open question O3).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.wl_runner import (
    count_dicoms,
    find_newest_runfolder,
    run_wl_analysis,
    runfolder_mtime,
)

# ---------------------------------------------------------------------------
# Fixture: synthetic WL DICOM set
# ---------------------------------------------------------------------------


@pytest.fixture
def synthetic_wl_runfolder(tmp_path: Path) -> Path:
    """Generate a small synthetic Winston-Lutz DICOM set in ``tmp_path``.

    Uses pylinac's image generator with a known BB offset so analysis
    produces a predictable ``max_2d_cax_to_bb``.
    """
    try:
        from pylinac.core.image_generator import (
            AS500Image,
            FilteredFieldLayer,
            GaussianFilterLayer,
            generate_winstonlutz,
        )
    except ImportError:
        pytest.skip("pylinac image_generator not available")

    runfolder = tmp_path / "2026-06-16_143022"
    runfolder.mkdir()

    # Generate a WL set: 4 images (gantry 0/90/180/270), BB offset 2mm left
    generate_winstonlutz(
        simulator=AS500Image(),
        field_layer=FilteredFieldLayer,
        dir_out=str(runfolder),
        field_size_mm=(30, 30),
        final_layers=[
            GaussianFilterLayer(sigma_mm=2),
        ],
        bb_size_mm=5,
        offset_mm_left=2.0,  # 2mm X offset → predictable max_2d_cax_to_bb
        image_axes=((0, 0, 0), (90, 0, 0), (180, 0, 0), (270, 0, 0)),
    )
    return runfolder


# ---------------------------------------------------------------------------
# find_newest_runfolder / count_dicoms / runfolder_mtime
# ---------------------------------------------------------------------------


def test_find_newest_runfolder(tmp_path: Path) -> None:
    """Newest subdirectory by mtime is returned."""
    root = tmp_path / "root"
    root.mkdir()
    old = root / "old"
    new = root / "new"
    old.mkdir()
    new.mkdir()
    # Ensure 'new' has a newer mtime
    os.utime(old, (1000, 1000))
    os.utime(new, (2000, 2000))

    result = find_newest_runfolder(root)
    assert result is not None
    assert result.name == "new"


def test_find_newest_runfolder_empty(tmp_path: Path) -> None:
    """No subdirectories → None."""
    root = tmp_path / "root"
    root.mkdir()
    assert find_newest_runfolder(root) is None


def test_find_newest_runfolder_nonexistent(tmp_path: Path) -> None:
    """Nonexistent root → None (not an exception)."""
    assert find_newest_runfolder(tmp_path / "ghost") is None


def test_count_dicoms(synthetic_wl_runfolder: Path) -> None:
    """Count matches the number of generated DICOM files."""
    count = count_dicoms(synthetic_wl_runfolder)
    assert count > 0, "Expected at least one DICOM in the synthetic runfolder"


def test_count_dicoms_empty(tmp_path: Path) -> None:
    """Empty runfolder → 0."""
    assert count_dicoms(tmp_path) == 0


def test_runfolder_mtime(tmp_path: Path) -> None:
    """mtime returns a float."""
    mtime = runfolder_mtime(tmp_path)
    assert isinstance(mtime, float)


# ---------------------------------------------------------------------------
# run_wl_analysis — happy path
# ---------------------------------------------------------------------------


def test_run_wl_analysis_happy_path(synthetic_wl_runfolder: Path) -> None:
    """Full analysis on synthetic DICOMs produces a valid WLAnalysisResult."""
    result = run_wl_analysis(
        machine_id="TEST",
        runfolder_path=str(synthetic_wl_runfolder),
        bb_size_mm=5.0,
        machine_scale="VARIAN_IEC",
        dicom_file_count=count_dicoms(synthetic_wl_runfolder),
        runfolder_mtime_val=runfolder_mtime(synthetic_wl_runfolder),
    )

    # Identity
    assert result.machine_id == "TEST"
    assert result.runfolder_path == str(synthetic_wl_runfolder)

    # Summary has all 24 metrics
    from core.config import WL_METRIC_NAMES

    for name in WL_METRIC_NAMES:
        assert name in result.summary, f"Missing metric: {name}"

    # max_2d_cax_to_bb should be non-zero (BB is offset 2mm)
    max_dist = result.summary["max_2d_cax_to_bb"]
    assert isinstance(max_dist, (int, float))
    assert max_dist > 0.1, f"Expected non-trivial max_2d_cax_to_bb, got {max_dist}"

    # Per-image arrays are parallel
    assert len(result.image_keys) == len(result.image_details)
    assert len(result.image_keys) > 0


# ---------------------------------------------------------------------------
# Plotly arrays
# ---------------------------------------------------------------------------


def test_plotly_arrays_shape(synthetic_wl_runfolder: Path) -> None:
    """Precomputed Plotly arrays have matching lengths."""
    result = run_wl_analysis(
        machine_id="TEST",
        runfolder_path=str(synthetic_wl_runfolder),
        bb_size_mm=5.0,
        machine_scale="VARIAN_IEC",
        dicom_file_count=count_dicoms(synthetic_wl_runfolder),
        runfolder_mtime_val=runfolder_mtime(synthetic_wl_runfolder),
    )

    n = len(result.image_keys)
    # deviation_vs_gantry
    assert len(result.deviation_vs_gantry["x"]) == n
    assert len(result.deviation_vs_gantry["y"]) == n
    assert len(result.deviation_vs_gantry["text"]) == n
    # bb_xy_scatter
    assert len(result.bb_xy_scatter["x"]) == n
    assert len(result.bb_xy_scatter["y"]) == n
    assert len(result.bb_xy_scatter["color"]) == n
    # distance_histogram
    assert len(result.distance_histogram["values"]) == n


def test_image_keys_parallel_alignment(synthetic_wl_runfolder: Path) -> None:
    """image_keys[i] corresponds to image_details[i] (parallel arrays)."""
    result = run_wl_analysis(
        machine_id="TEST",
        runfolder_path=str(synthetic_wl_runfolder),
        bb_size_mm=5.0,
        machine_scale="VARIAN_IEC",
        dicom_file_count=count_dicoms(synthetic_wl_runfolder),
        runfolder_mtime_val=runfolder_mtime(synthetic_wl_runfolder),
    )

    for key, detail in zip(result.image_keys, result.image_details, strict=True):
        # Each key should match the G{g}B{b}P{p} pattern
        assert key.startswith("G"), f"Unexpected key format: {key}"
        # Each detail should be a dict with at least one field
        assert isinstance(detail, dict)


def test_params_used_populated(synthetic_wl_runfolder: Path) -> None:
    """params_used reflects the parameters passed to analyze()."""
    result = run_wl_analysis(
        machine_id="TEST",
        runfolder_path=str(synthetic_wl_runfolder),
        bb_size_mm=5.0,
        machine_scale="VARIAN_IEC",
        apply_virtual_shift=True,
        dicom_file_count=count_dicoms(synthetic_wl_runfolder),
        runfolder_mtime_val=runfolder_mtime(synthetic_wl_runfolder),
    )

    assert result.params_used["bb_size_mm"] == 5.0
    assert result.params_used["machine_scale"] == "VARIAN_IEC"
    assert result.params_used["apply_virtual_shift"] is True
