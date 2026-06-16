#!/usr/bin/env python
"""Batch-assess all synthetic WL scenarios.

Runs pylinac analysis on each generated test data set and reports the
key metrics + pass/fail status. Useful for validating that the test data
produces expected results before manual app testing.

Usage::

    uv run python scripts/assess_test_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

WL_ROOT = (
    Path(__file__).resolve().parent.parent
    / "tests"
    / "fixtures"
    / "wl_data"
    / "LA2"
    / "WinstonLutz"
)
TOLERANCE_MM = 1.0


def assess_scenario(runfolder: Path) -> dict | None:
    """Run analysis on a scenario and return key metrics."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.wl_runner import count_dicoms, run_wl_analysis, runfolder_mtime

    dcm_count = count_dicoms(runfolder)
    if dcm_count == 0:
        return None

    try:
        result = run_wl_analysis(
            machine_id="LA2",
            runfolder_path=str(runfolder),
            bb_size_mm=5.0,
            machine_scale="VARIAN_IEC",
            dicom_file_count=dcm_count,
            runfolder_mtime_val=runfolder_mtime(runfolder),
        )

        max_dist = float(result.summary.get("max_2d_cax_to_bb", 0.0))
        median_dist = float(result.summary.get("median_2d_cax_to_bb", 0.0))
        gantry_iso = float(result.summary.get("gantry_3d_iso", 0.0))

        return {
            "name": runfolder.name,
            "n_images": dcm_count,
            "max_2d_cax_to_bb": max_dist,
            "median_2d_cax_to_bb": median_dist,
            "gantry_3d_iso": gantry_iso,
            "passed": max_dist <= TOLERANCE_MM,
            "error": None,
        }
    except Exception as exc:
        return {
            "name": runfolder.name,
            "n_images": dcm_count,
            "max_2d_cax_to_bb": float("nan"),
            "median_2d_cax_to_bb": float("nan"),
            "gantry_3d_iso": float("nan"),
            "passed": False,
            "error": str(exc)[:80],
        }


def main() -> int:
    if not WL_ROOT.exists():
        print(f"Test data root not found: {WL_ROOT}")
        print("Run: uv run python scripts/generate_test_data.py")
        return 1

    print("=" * 80)
    print(f"Winston-Lutz Test Data Assessment (tolerance: {TOLERANCE_MM}mm)")
    print("=" * 80)
    print()
    print(
        f"{'Scenario':<25} {'Images':>6} {'Max 2D':>8} {'Median':>8} {'G3D Iso':>8} {'Status':>8}"
    )
    print("-" * 80)

    scenarios = sorted(d for d in WL_ROOT.iterdir() if d.is_dir())
    results = []

    for scenario in scenarios:
        metrics = assess_scenario(scenario)
        if metrics is None:
            print(f"{scenario.name:<25} {'EMPTY':>6} {'---':>8} {'---':>8} {'---':>8} {'SKIP':>8}")
            continue

        if metrics["error"]:
            print(
                f"{metrics['name']:<25} {metrics['n_images']:>6} {'ERROR':>8} {'---':>8} {'---':>8} {'ERROR':>8}"
            )
            print(f"  └─ {metrics['error']}")
            results.append(metrics)
            continue

        status = "[PASS]" if metrics["passed"] else "[FAIL]"
        print(
            f"{metrics['name']:<25} {metrics['n_images']:>6} "
            f"{metrics['max_2d_cax_to_bb']:>7.2f}m {metrics['median_2d_cax_to_bb']:>7.2f}m "
            f"{metrics['gantry_3d_iso']:>7.2f}m {status:>8}"
        )
        results.append(metrics)

    print("-" * 80)
    print(
        f"\n{len(results)} scenarios assessed. "
        f"{sum(1 for r in results if r['passed'])} PASS, "
        f"{sum(1 for r in results if not r['passed'])} FAIL."
    )

    # Expected results validation
    print("\nExpected behaviour:")
    expectations = {
        "synthetic_pass": True,
        "synthetic_borderline": True,
        "synthetic_fail": False,
    }
    for name, should_pass in expectations.items():
        match = [r for r in results if r["name"] == name]
        if match:
            actual_pass = match[0]["passed"]
            check = "✓" if actual_pass == should_pass else "✗ UNEXPECTED"
            print(
                f"  {name}: expected {'PASS' if should_pass else 'FAIL'}, "
                f"got {'PASS' if actual_pass else 'FAIL'} {check}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
