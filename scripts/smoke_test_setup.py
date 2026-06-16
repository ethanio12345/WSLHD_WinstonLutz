#!/usr/bin/env python
"""Set up the test environment for the Playwright smoke test.

Generates synthetic WL DICOMs, creates a test machines.yaml, and prints
the config path so the Streamlit server can use it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


def main() -> int:
    test_env = Path("/tmp/wl_test_env")
    test_env.mkdir(parents=True, exist_ok=True)

    # --- Generate synthetic DICOMs ---
    dicom_root = test_env / "dicom" / "LA2" / "WinstonLutz"
    runfolder = dicom_root / "2026-06-16_143022"
    runfolder.mkdir(parents=True, exist_ok=True)

    print("Generating synthetic WL DICOMs...", flush=True)
    from pylinac.core.image_generator import (
        AS500Image,
        FilteredFieldLayer,
        GaussianFilterLayer,
        generate_winstonlutz,
    )

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
    print(f"  DICOMs written to {runfolder}", flush=True)

    # --- Create output dir ---
    output_root = test_env / "out"
    output_root.mkdir(parents=True, exist_ok=True)

    # --- Create machines.yaml ---
    project_root = Path(__file__).resolve().parent.parent
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
            "fry_meme_path": str(project_root / "assets" / "fry_money.png"),
            "logo_path": str(project_root / "assets" / "fry_money.png"),
        },
    }
    config_path = test_env / "machines.yaml"
    config_path.write_text(yaml.dump(config_data), encoding="utf-8")
    print(f"  Config written to {config_path}", flush=True)

    # --- Create assets dir (copy fry meme) ---
    assets_dir = test_env / "assets"
    assets_dir.mkdir(exist_ok=True)

    print(f"\nTest environment ready at {test_env}", flush=True)
    print(f"Config path: {config_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
