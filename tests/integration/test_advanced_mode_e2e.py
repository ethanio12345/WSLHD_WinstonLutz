"""End-to-end test: Advanced mode re-run with different parameters.

Task 10.2 — synthesize DICOMs, simulate Simple→Advanced hand-off by calling
the underlying functions directly, re-run with new bb_size_mm, verify the
result updates and the xlsx is overwritten.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import load_workbook

from core.excel_writer import write_session_output
from core.wl_runner import count_dicoms, run_wl_analysis, runfolder_mtime


@pytest.fixture
def advanced_setup(tmp_path: Path):
    """Set up synthetic DICOMs for Advanced-mode testing."""
    try:
        from pylinac.core.image_generator import (
            AS500Image,
            FilteredFieldLayer,
            GaussianFilterLayer,
            generate_winstonlutz,
        )
    except ImportError:
        pytest.skip("pylinac image_generator not available")

    dicom_root = tmp_path / "dicom" / "LA2" / "WinstonLutz"
    runfolder = dicom_root / "2026-06-16_143022"
    runfolder.mkdir(parents=True)

    generate_winstonlutz(
        simulator=AS500Image(),
        field_layer=FilteredFieldLayer,
        dir_out=str(runfolder),
        field_size_mm=(30, 30),
        final_layers=[GaussianFilterLayer(sigma_mm=2)],
        bb_size_mm=5,
        offset_mm_left=2.0,
        image_axes=((0, 0, 0), (90, 0, 0), (180, 0, 0), (270, 0, 0)),
    )

    output_root = tmp_path / "out"
    output_root.mkdir()

    return {
        "runfolder": runfolder,
        "output_root": output_root,
    }


def test_advanced_rerun_overwrites_xlsx(advanced_setup) -> None:
    """Simulate: Simple run → Advanced re-run with different bb_size_mm."""
    setup = advanced_setup
    template_path = (
        Path(__file__).resolve().parent.parent.parent / "templates" / "winston_lutz.xltx"
    )
    runfolder = setup["runfolder"]
    dicom_count = count_dicoms(runfolder)
    mtime = runfolder_mtime(runfolder)

    # "Simple mode" run with bb_size_mm=5.0
    result1 = run_wl_analysis(
        machine_id="LA2",
        runfolder_path=str(runfolder),
        bb_size_mm=5.0,
        machine_scale="VARIAN_IEC",
        dicom_file_count=dicom_count,
        runfolder_mtime_val=mtime,
    )
    xlsx_path = write_session_output(
        result=result1,
        output_root=Path(setup["output_root"]),
        template_path=template_path,
    )
    _max_dist_1 = result1.summary["max_2d_cax_to_bb"]

    # "Advanced re-run" with bb_size_mm=3.0 (different parameter)
    result2 = run_wl_analysis(
        machine_id="LA2",
        runfolder_path=str(runfolder),
        bb_size_mm=3.0,
        machine_scale="VARIAN_IEC",
        dicom_file_count=dicom_count,
        runfolder_mtime_val=mtime,
    )
    xlsx_path2 = write_session_output(
        result=result2,
        output_root=Path(setup["output_root"]),
        template_path=template_path,
    )

    # The xlsx path is the same (same session folder)
    assert xlsx_path == xlsx_path2

    # The result should reflect the different parameter
    assert result2.params_used["bb_size_mm"] == 3.0

    # Verify the xlsx was overwritten with new values
    wb = load_workbook(str(xlsx_path2))
    dn = wb.defined_names["max_2d_cax_to_bb"]
    for sheet_title, coord in dn.destinations:
        written_value = wb[sheet_title][coord].value
        assert written_value == pytest.approx(result2.summary["max_2d_cax_to_bb"])
        break


def test_params_used_reflects_run(advanced_setup) -> None:
    """params_used in the result reflects what was actually run."""
    setup = advanced_setup
    runfolder = setup["runfolder"]
    dicom_count = count_dicoms(runfolder)

    result = run_wl_analysis(
        machine_id="LA2",
        runfolder_path=str(runfolder),
        bb_size_mm=5.0,
        machine_scale="VARIAN_IEC",
        apply_virtual_shift=True,
        low_density_bb=False,
        dicom_file_count=dicom_count,
        runfolder_mtime_val=runfolder_mtime(runfolder),
    )

    assert result.params_used["bb_size_mm"] == 5.0
    assert result.params_used["machine_scale"] == "VARIAN_IEC"
    assert result.params_used["apply_virtual_shift"] is True
    assert result.params_used["low_density_bb"] is False
