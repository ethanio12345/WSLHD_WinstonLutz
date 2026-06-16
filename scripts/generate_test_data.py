#!/usr/bin/env python
"""Download the pylinac Winston-Lutz demo images for testing.

Downloads the official pylinac demo set (17 clinical-format DICOMs covering
gantry, collimator, and couch axes) and extracts them to
``tests/fixtures/wl_data/LA2/WinstonLutz/demo_clinical/``.

These are the same images used by pylinac's own test suite and documentation.
They contain a realistic BB offset (max_2d_cax_to_bb ≈ 1.24mm) that exceeds
the default 1.0mm tolerance — good for testing both the analysis pipeline
and the FAIL display path.

Usage::

    uv run python scripts/generate_test_data.py
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "wl_data"


def main() -> int:
    out_dir = FIXTURE_ROOT / "LA2" / "WinstonLutz" / "demo_clinical"

    print("Downloading pylinac Winston-Lutz demo images...")
    from pylinac.core.io import retrieve_demo_file

    zip_path = retrieve_demo_file(name="winston_lutz.zip")
    print(f"  Downloaded: {zip_path} ({zip_path.stat().st_size // 1024}KB)")

    # Clean and extract
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(str(out_dir))

    dcm_count = len(list(out_dir.glob("*.dcm")))
    print(f"  Extracted {dcm_count} DICOM files to {out_dir}")

    # Quick verification
    import warnings

    warnings.filterwarnings("ignore")
    from pylinac import WinstonLutz

    wl = WinstonLutz(str(out_dir))
    wl.analyze(bb_size_mm=5)
    data = wl.results_data(as_dict=True)
    max_d = data["max_2d_cax_to_bb_mm"]
    print(f"\nVerification: {data['num_total_images']} images, max_2d_cax_to_bb={max_d:.3f}mm")
    print(f"  → {'PASS' if max_d <= 1.0 else 'FAIL'} at 1.0mm tolerance")

    print(f"\nTest data ready: {out_dir}")
    print("machines.yaml already points here. Run: uv run streamlit run app.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
