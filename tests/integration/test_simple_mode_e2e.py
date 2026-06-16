"""End-to-end test: Simple mode pipeline (synthetic DICOMs → xlsx).

Task 10.1 — synthesize DICOMs, write a temporary machines.yaml, run
``run_wl_analysis`` + ``write_session_output``, verify the produced xlsx
exists, has 25 named cells populated, sheet count = N+1.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from openpyxl import load_workbook

from core.config import REQUIRED_TEMPLATE_NAMES, load_config
from core.excel_writer import write_session_output
from core.wl_runner import count_dicoms, run_wl_analysis, runfolder_mtime


@pytest.fixture
def e2e_setup(tmp_path: Path):
    """Set up a full environment: synthetic DICOMs, config, output dir."""
    try:
        from pylinac.core.image_generator import (
            AS500Image,
            FilteredFieldLayer,
            GaussianFilterLayer,
            generate_winstonlutz,
        )
    except ImportError:
        pytest.skip("pylinac image_generator not available")

    # Synthetic DICOM runfolder
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
        offset_mm_left=1.5,
        image_axes=((0, 0, 0), (90, 0, 0), (180, 0, 0), (270, 0, 0)),
    )

    # Output dir
    output_root = tmp_path / "out"
    output_root.mkdir()

    # machines.yaml
    config_data = {
        "machines": {
            "LA2": {
                "display_name": "LA2 (TrueBeam)",
                "dicom_roots": {"winston_lutz": str(dicom_root)},
            }
        },
        "output": {"root": str(output_root)},
        "analysis_defaults": {
            "winston_lutz": {
                "bb_size_mm": 5.0,
                "machine_scale": "VARIAN_IEC",
                "tolerance_mm": 1.0,
            }
        },
        "assets": {
            "fry_meme_path": "/assets/fry.png",
            "logo_path": "/assets/logo.png",
        },
    }
    config_path = tmp_path / "machines.yaml"
    config_path.write_text(yaml.dump(config_data), encoding="utf-8")

    return {
        "config_path": config_path,
        "runfolder": runfolder,
        "output_root": output_root,
        "dicom_root": dicom_root,
    }


def test_simple_mode_e2e(e2e_setup) -> None:
    """Full Simple-mode pipeline: config → analyze → write xlsx."""
    setup = e2e_setup
    config = load_config(setup["config_path"])
    template_path = (
        Path(__file__).resolve().parent.parent.parent / "templates" / "winston_lutz.xltx"
    )

    # Run analysis
    dicom_count = count_dicoms(setup["runfolder"])
    result = run_wl_analysis(
        machine_id="LA2",
        runfolder_path=str(setup["runfolder"]),
        bb_size_mm=5.0,
        machine_scale="VARIAN_IEC",
        dicom_file_count=dicom_count,
        runfolder_mtime_val=runfolder_mtime(setup["runfolder"]),
    )

    # Write session output
    xlsx_path = write_session_output(
        result=result,
        output_root=Path(config.output.root),
        template_path=template_path,
        machine_display_name="LA2 (TrueBeam)",
    )

    # Verify xlsx exists
    assert xlsx_path.exists()
    assert xlsx_path.suffix == ".xlsx"

    # Verify paired .xltx exists
    assert xlsx_path.with_suffix(".xltx").exists()

    # Verify all 25 named cells populated
    wb = load_workbook(str(xlsx_path))
    for name in REQUIRED_TEMPLATE_NAMES:
        assert name in wb.defined_names, f"Missing defined name: {name}"

    # Verify sheet count = 1 (summary) + N (per-image)
    n_images = len(result.image_keys)
    expected_sheets = 1 + n_images
    assert len(wb.sheetnames) == expected_sheets, (
        f"Expected {expected_sheets} sheets, got {len(wb.sheetnames)}: {wb.sheetnames}"
    )

    # Verify folder structure
    assert "LA2" in str(xlsx_path)
    assert "WL" in str(xlsx_path)
    assert "LA2_WL_2026-06-16_143022" in str(xlsx_path)
