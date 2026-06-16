#!/usr/bin/env python
"""Generate synthetic Winston-Lutz test data for assessment.

Creates multiple WL sessions with known BB offsets so pass/fail behaviour
can be predicted. Also downloads pylinac's official demo images (real
clinical-format DICOMs) for realistic testing.

Output directory: ``tests/fixtures/wl_data/``

Scenarios generated:
    - ``demo_clinical``: pylinac's official 17-image WL demo set
    - ``synthetic_pass``: 0.3mm BB offset (well within 1.0mm tolerance → PASS)
    - ``synthetic_borderline``: 0.9mm offset (just under tolerance → PASS)
    - ``synthetic_fail``: 2.0mm offset (exceeds tolerance → FAIL)
    - ``synthetic_8img``: 8-image set (every 45°, standard monthly QA)
    - ``synthetic_couch_iso``: couch-axis variation (tests couch 3D iso)

Usage::

    uv run python scripts/generate_test_data.py

After generation, create a machines.yaml pointing at the data::

    cp machines.yaml.example machines.yaml
    # Edit dicom_roots.winston_lutz to point at tests/fixtures/wl_data/LA2/WinstonLutz
"""

from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "wl_data"


def _generate_synthetic(
    out_dir: Path,
    *,
    bb_offset_mm: float = 0.0,
    n_images: int = 4,
    bb_size_mm: float = 5.0,
    gantry_tilt: float = 0.0,
    gantry_sag: float = 0.0,
) -> None:
    """Generate a synthetic WL DICOM set with pylinac's image generator."""
    from pylinac.core.image_generator import (
        AS500Image,
        FilteredFieldLayer,
        GaussianFilterLayer,
        generate_winstonlutz,
    )

    out_dir.mkdir(parents=True, exist_ok=True)

    # Standard monthly QA: gantry every 90° (4 images) or 45° (8 images)
    if n_images == 4:
        axes = ((0, 0, 0), (90, 0, 0), (180, 0, 0), (270, 0, 0))
    elif n_images == 8:
        axes = tuple((g, 0, 0) for g in range(0, 360, 45))
    elif n_images == 17:
        # Full Winston-Lutz: gantry + collimator + couch combinations
        axes = (
            (0, 0, 0),
            (0, 90, 0),
            (0, 180, 0),
            (0, 270, 0),
            (90, 0, 0),
            (90, 90, 0),
            (90, 180, 0),
            (90, 270, 0),
            (180, 0, 0),
            (180, 90, 0),
            (180, 180, 0),
            (180, 270, 0),
            (270, 0, 0),
            (270, 90, 0),
            (270, 180, 0),
            (270, 270, 0),
            (0, 0, 45),  # one couch image
        )
    else:
        axes = tuple((g, 0, 0) for g in range(0, 360, max(1, 360 // n_images)))

    print(
        f"  Generating {len(axes)} images, BB offset={bb_offset_mm}mm, "
        f"bb_size={bb_size_mm}mm, tilt={gantry_tilt}°, sag={gantry_sag}mm..."
    )

    generate_winstonlutz(
        simulator=AS500Image(),
        field_layer=FilteredFieldLayer,
        dir_out=str(out_dir),
        field_size_mm=(30, 30),
        final_layers=[GaussianFilterLayer(sigma_mm=2)],
        bb_size_mm=bb_size_mm,
        offset_mm_left=bb_offset_mm,
        image_axes=axes,
        gantry_tilt=gantry_tilt,
        gantry_sag=gantry_sag,
    )

    count = len(list(out_dir.glob("*.dcm")))
    print(f"    → {count} DICOM files written to {out_dir}")


def _download_pylinac_demo(out_dir: Path) -> None:
    """Download pylinac's official demo WL images (17-image clinical set)."""
    out_dir.mkdir(parents=True, exist_ok=True)

    print("  Downloading pylinac official demo (winston_lutz.zip)...")
    try:
        from pylinac.core.io import retrieve_demo_file

        zip_path = retrieve_demo_file(name="winston_lutz.zip")
        print(f"    Downloaded to {zip_path}")

        # Extract DICOMs to out_dir
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(str(out_dir))

        count = len(list(out_dir.glob("*.dcm")))
        print(f"    → {count} DICOM files extracted to {out_dir}")

    except Exception as exc:
        print(f"    ⚠ Download failed ({exc}), skipping demo set")


def main() -> int:
    print("=" * 60)
    print("Generating Winston-Lutz Test Data")
    print(f"Output root: {FIXTURE_ROOT}")
    print("=" * 60)

    wl_root = FIXTURE_ROOT / "LA2" / "WinstonLutz"

    # --- Scenario 1: pylinac official demo ---
    print("\n[1/6] pylinac official demo (clinical-format DICOMs)")
    _download_pylinac_demo(wl_root / "demo_clinical")

    # --- Scenario 2: PASS (0.5mm offset) ---
    print("\n[2/6] Synthetic PASS (0.5mm BB offset, 4 images)")
    _generate_synthetic(
        wl_root / "synthetic_pass",
        bb_offset_mm=0.5,
        n_images=4,
    )

    # --- Scenario 3: BORDERLINE (0.9mm offset, just under 1.0 tolerance) ---
    print("\n[3/6] Synthetic BORDERLINE (0.9mm BB offset, 4 images)")
    _generate_synthetic(
        wl_root / "synthetic_borderline",
        bb_offset_mm=0.9,
        n_images=4,
    )

    # --- Scenario 4: FAIL (2.0mm offset) ---
    print("\n[4/6] Synthetic FAIL (2.0mm BB offset, 4 images)")
    _generate_synthetic(
        wl_root / "synthetic_fail",
        bb_offset_mm=2.0,
        n_images=4,
    )

    # --- Scenario 5: Standard 8-image monthly QA ---
    print("\n[5/6] Synthetic 8-image monthly QA (0.5mm offset, 8 images)")
    _generate_synthetic(
        wl_root / "synthetic_8img",
        bb_offset_mm=0.5,
        n_images=8,
    )

    # --- Scenario 6: Full 17-image set with gantry sag ---
    print("\n[6/6] Synthetic full 17-image set (1.0mm offset + 0.3mm sag)")
    _generate_synthetic(
        wl_root / "synthetic_17img_sag",
        bb_offset_mm=1.0,
        n_images=17,
        gantry_sag=0.3,
    )

    # --- Summary ---
    print("\n" + "=" * 60)
    print("TEST DATA SUMMARY")
    print("=" * 60)
    scenarios = sorted(wl_root.iterdir())
    for scenario in scenarios:
        if scenario.is_dir():
            dcm_count = len(list(scenario.glob("*.dcm")))
            print(f"  {scenario.name:30s}  {dcm_count:3d} DICOMs")

    print(f"\nData root: {wl_root}")
    print("\nTo use with the Streamlit app:")
    print("  1. cp machines.yaml.example machines.yaml")
    print(f"  2. Set dicom_roots.winston_lutz to: {wl_root}")
    print("  3. uv run streamlit run app.py")
    print("\nThe app will auto-select the newest runfolder by mtime.")
    print("To test a specific scenario, touch its directory:")
    print("  touch <scenario_dir>  # makes it the newest")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
