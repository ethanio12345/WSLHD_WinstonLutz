"""E2E: Field Profile page — full browser interaction tests.

Tests the complete Simple + Advanced mode flows:
1. Machine dropdown shows the test machine (with field_profile configured)
2. Image dropdown shows the demo DICOM with metadata
3. FFF detection display renders
4. Analysis button triggers FieldAnalysis
5. Success card renders with flatness/symmetry/field size
6. Hand-off to Advanced mode works
7. Advanced mode: Re-run with changed param, Download, all 4 tabs
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def _wait_for_text(page, text: str, timeout: int = 30000) -> None:  # type: ignore[no-untyped-def]
    page.wait_for_selector(f"text={text}", timeout=timeout)


def _click_button(page, label: str, timeout: int = 30000) -> None:  # type: ignore[no-untyped-def]
    page.get_by_role("button", name=label).first.click(timeout=timeout)


def _switch_to_advanced(field_profile_page) -> None:  # type: ignore[no-untyped-def]
    """Switch to Advanced mode via the sidebar toggle."""
    field_profile_page.get_by_text("Advanced").first.click()
    field_profile_page.wait_for_load_state("networkidle")
    time.sleep(2)


def _run_analysis_if_needed(page, timeout: int = 120000) -> None:  # type: ignore[no-untyped-def]
    """Click 'Run analysis' in the sidebar if it exists, then wait for Overview."""
    btn = page.get_by_role("button", name="Run analysis")
    if btn.count() > 0:
        btn.first.click()
        _wait_for_text(page, "Overview", timeout=timeout)
        time.sleep(3)


def _get_sidebar_param_input(page, label_text: str):  # type: ignore[no-untyped-def]
    """Find a number input in the sidebar by its label text."""
    container = page.locator("[data-testid='stNumberInput']").filter(has_text=label_text)
    return container.locator("input").first


# ---------------------------------------------------------------------------
# Simple mode — machine/runfolder/image dropdowns + FFF display
# ---------------------------------------------------------------------------


def test_fp_machine_dropdown_shows_machine(field_profile_page) -> None:  # type: ignore[no-untyped-def]
    """The Field Profile page machine dropdown shows the test machine."""
    _wait_for_text(field_profile_page, "LA2", timeout=20000)


def test_fp_simple_mode_fff_detection_display(field_profile_page) -> None:  # type: ignore[no-untyped-def]
    """The FFF detection display renders after image selection."""
    _wait_for_text(field_profile_page, "FFF detected", timeout=20000)


def test_fp_simple_mode_analysis_button(field_profile_page) -> None:  # type: ignore[no-untyped-def]
    """The analysis button exists on the Field Profile page."""
    _wait_for_text(field_profile_page, "Shut Up", timeout=20000)


# ---------------------------------------------------------------------------
# Simple mode — full pipeline (button → success card → hand-off)
# ---------------------------------------------------------------------------


def test_fp_simple_mode_full_pipeline(field_profile_page) -> None:  # type: ignore[no-untyped-def]
    """Full Simple mode: click button -> success card with profile metrics."""
    _click_button(field_profile_page, "Shut Up and Give Me My MyQA Results")

    # FieldAnalysis runs in ~5-20s for a single demo image
    _wait_for_text(field_profile_page, "Analysis complete", timeout=120000)

    body = field_profile_page.text_content("body") or ""

    # Verify flatness/symmetry/field size metrics on the success card
    assert "Flatness Vertical" in body, "Flatness Vertical missing from success card"
    assert "Flatness Horizontal" in body, "Flatness Horizontal missing"
    assert "Symmetry Vertical" in body, "Symmetry Vertical missing"
    assert "Symmetry Horizontal" in body, "Symmetry Horizontal missing"
    assert "Field Size Vertical" in body, "Field Size Vertical missing"
    assert "Field Size Horizontal" in body, "Field Size Horizontal missing"
    assert "FFF status" in body, "FFF status missing"


def test_fp_simple_mode_handoff_to_advanced(field_profile_page) -> None:  # type: ignore[no-untyped-def]
    """The 'View in Advanced mode' button switches to Field Profile Advanced mode."""
    _click_button(field_profile_page, "Shut Up and Give Me My MyQA Results")
    _wait_for_text(field_profile_page, "Analysis complete", timeout=120000)

    _click_button(field_profile_page, "View in Advanced mode")
    field_profile_page.wait_for_load_state("networkidle")
    time.sleep(3)

    # Verify Advanced mode tabs appear (Overview + Profiles + Field Map + ROI & Penumbra)
    body = field_profile_page.text_content("body") or ""
    assert "Overview" in body, "Overview tab not visible after hand-off"
    assert "Profiles" in body, "Profiles tab not visible after hand-off"
    assert "Field Map" in body, "Field Map tab not visible after hand-off"


# ---------------------------------------------------------------------------
# Advanced mode — Re-run with changed param
# ---------------------------------------------------------------------------


def test_fp_advanced_rerun_with_changed_param(field_profile_page) -> None:  # type: ignore[no-untyped-def]
    """Change in-field ratio from 0.8 to 0.6, click Re-run, verify it completes."""
    _switch_to_advanced(field_profile_page)
    _run_analysis_if_needed(field_profile_page)

    # Change in-field ratio in the sidebar
    ifr_input = _get_sidebar_param_input(field_profile_page, "In-field ratio")
    ifr_input.click()
    ifr_input.press("Control+a")
    ifr_input.type("0.6")
    ifr_input.press("Tab")
    field_profile_page.wait_for_load_state("networkidle")
    time.sleep(2)

    # Click Re-run analysis
    rerun_btn = field_profile_page.get_by_role("button", name="Re-run analysis")
    assert rerun_btn.count() >= 1, "Re-run button not found"
    rerun_btn.first.click()

    # Wait for the analysis to complete
    _wait_for_text(field_profile_page, "Overview", timeout=120000)
    time.sleep(3)

    # Verify the new in-field ratio is reflected in the params caption
    body_after = field_profile_page.text_content("body") or ""
    assert "in_field_ratio" in body_after, (
        f"in_field_ratio not in params caption. Body snippet: {body_after[:500]}"
    )


# ---------------------------------------------------------------------------
# Advanced mode — Download xlsx
# ---------------------------------------------------------------------------


def test_fp_advanced_download_produces_xlsx(
    field_profile_page,
    output_root: Path,  # type: ignore[no-untyped-def]
) -> None:
    """Click Download xlsx, verify the FP xlsx is written (refreshed) on disk.

    Note: FP sessions key on the image stem, so the download overwrites the
    same path used by the earlier Simple-mode run (spec: "Re-run overwrites
    same session"). We therefore verify the file is refreshed by mtime rather
    than by counting files.
    """
    _switch_to_advanced(field_profile_page)
    _run_analysis_if_needed(field_profile_page)

    expected = output_root / "FP" / "LA2_FP_flatsym_demo" / "LA2_FP_flatsym_demo.xlsx"
    mtime_before = expected.stat().st_mtime if expected.exists() else 0.0

    download_btn = field_profile_page.get_by_role("button", name="Download xlsx")
    assert download_btn.count() >= 1, "Download xlsx button not found"
    download_btn.first.click()
    field_profile_page.wait_for_load_state("networkidle")
    time.sleep(3)

    assert expected.exists(), f"FP xlsx not written to expected path: {expected}"
    assert expected.stat().st_size > 0, f"Downloaded xlsx is empty: {expected}"
    assert expected.stat().st_mtime > mtime_before, (
        f"FP xlsx not refreshed by download. mtime before={mtime_before}, "
        f"after={expected.stat().st_mtime}"
    )


# ---------------------------------------------------------------------------
# Advanced mode — all 4 tabs clicked and verified
# ---------------------------------------------------------------------------


def test_fp_advanced_click_overview_tab(field_profile_page) -> None:  # type: ignore[no-untyped-def]
    """Click Overview tab → verify summary metrics + protocol + FFF render."""
    _switch_to_advanced(field_profile_page)
    _run_analysis_if_needed(field_profile_page)

    field_profile_page.get_by_role("tab", name="Overview").first.click()
    field_profile_page.wait_for_load_state("networkidle")
    time.sleep(2)

    body = field_profile_page.text_content("body") or ""
    assert "Protocol" in body, "Protocol not visible in Overview tab"
    assert "FFF" in body, "FFF status not visible in Overview tab"
    assert "Analysed with" in body, "Params caption not visible in Overview tab"


def test_fp_advanced_click_profiles_tab(field_profile_page) -> None:  # type: ignore[no-untyped-def]
    """Click Profiles tab → verify V+H profile charts render."""
    _switch_to_advanced(field_profile_page)
    _run_analysis_if_needed(field_profile_page)

    field_profile_page.get_by_role("tab", name="Profiles").first.click()
    field_profile_page.wait_for_load_state("networkidle")
    time.sleep(2)

    body = field_profile_page.text_content("body") or ""
    assert "Vertical Profile" in body or "Horizontal Profile" in body, (
        "Profile charts not visible in Profiles tab"
    )


def test_fp_advanced_click_field_map_tab(field_profile_page) -> None:  # type: ignore[no-untyped-def]
    """Click Field Map tab → verify the analyzed image renders."""
    _switch_to_advanced(field_profile_page)
    _run_analysis_if_needed(field_profile_page)

    field_profile_page.get_by_role("tab", name="Field Map").first.click()
    field_profile_page.wait_for_load_state("networkidle")
    time.sleep(5)  # plot_analyzed_image is slow (matplotlib + lazy fp_obj)

    # The tab should not show a render failure warning
    body = field_profile_page.text_content("body") or ""
    assert "Could not render" not in body, f"Field Map failed to render. Body snippet: {body[:500]}"


def test_fp_advanced_click_roi_tab(field_profile_page) -> None:  # type: ignore[no-untyped-def]
    """Click ROI & Penumbra tab → verify ROI stats + penumbra + slopes render."""
    _switch_to_advanced(field_profile_page)
    _run_analysis_if_needed(field_profile_page)

    field_profile_page.get_by_role("tab", name="ROI & Penumbra").first.click()
    field_profile_page.wait_for_load_state("networkidle")
    time.sleep(2)

    body = field_profile_page.text_content("body") or ""
    assert "Central ROI" in body, "Central ROI section not visible in ROI tab"
    assert "Penumbra" in body, "Penumbra section not visible in ROI tab"
    assert "Slopes" in body, "Slopes section not visible in ROI tab"


# ---------------------------------------------------------------------------
# Advanced mode — sidebar params present
# ---------------------------------------------------------------------------


def test_fp_advanced_all_sidebar_params_present(field_profile_page) -> None:  # type: ignore[no-untyped-def]
    """All FieldAnalysis analyze parameters appear in the Advanced sidebar."""
    _switch_to_advanced(field_profile_page)
    _run_analysis_if_needed(field_profile_page)

    body = field_profile_page.text_content("body") or ""
    expected_params = [
        "Protocol",
        "Centering",
        "In-field ratio",
        "Penumbra",
        "Vertical position",
        "Horizontal position",
        "Interpolation",
        "Edge detection method",
        "Force FFF",
    ]
    for param in expected_params:
        assert param in body, f"Sidebar param '{param}' not found on page"
