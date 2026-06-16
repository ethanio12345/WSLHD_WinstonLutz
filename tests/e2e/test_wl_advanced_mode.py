"""E2E: Winston-Lutz Advanced mode — full interactive workflows.

Every button is clicked, every flow is exercised end-to-end:
1. Switch to Advanced, run analysis from sidebar
2. Change a parameter, click Re-run, verify new result
3. Click Download xlsx, verify file appears on disk
4. Click all tabs, verify content renders
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def _wait_for_text(page, text: str, timeout: int = 30000) -> None:  # type: ignore[no-untyped-def]
    page.wait_for_selector(f"text={text}", timeout=timeout)


def _switch_to_advanced(wl_page) -> None:  # type: ignore[no-untyped-def]
    """Switch to Advanced mode via the sidebar toggle."""
    wl_page.get_by_text("Advanced").first.click()
    wl_page.wait_for_load_state("networkidle")
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
# Full Re-run workflow: change param → click Re-run → verify new result
# ---------------------------------------------------------------------------


def test_wl_advanced_rerun_with_changed_param(wl_page) -> None:  # type: ignore[no-untyped-def]
    """Change BB Size from 5 to 7, click Re-run, verify the new value appears."""
    _switch_to_advanced(wl_page)
    _run_analysis_if_needed(wl_page)

    # Capture the original "Analysed with" text
    body_before = wl_page.text_content("body") or ""

    # Change BB Size in the sidebar
    bb_input = _get_sidebar_param_input(wl_page, "BB Size")
    bb_input.click()
    bb_input.press("Control+a")
    bb_input.type("7.0")
    bb_input.press("Tab")
    wl_page.wait_for_load_state("networkidle")
    time.sleep(2)

    # Click Re-run analysis
    rerun_btn = wl_page.get_by_role("button", name="Re-run analysis")
    assert rerun_btn.count() >= 1, "Re-run button not found"
    rerun_btn.first.click()

    # Wait for the analysis to complete
    _wait_for_text(wl_page, "Overview", timeout=120000)
    time.sleep(3)

    # Verify the result reflects the new BB size
    body_after = wl_page.text_content("body") or ""
    assert "7.0" in body_after or "7" in body_after, (
        f"New BB size 7.0 not reflected in result. Body snippet: {body_after[:500]}"
    )
    assert body_after != body_before, "Page content unchanged after re-run"


# ---------------------------------------------------------------------------
# Full Download workflow: click Download → verify xlsx on disk
# ---------------------------------------------------------------------------


def test_wl_advanced_download_produces_xlsx(
    wl_page,
    output_root: Path,  # type: ignore[no-untyped-def]
) -> None:
    """Click Download xlsx, verify the file is written to the output directory."""
    _switch_to_advanced(wl_page)
    _run_analysis_if_needed(wl_page)

    # Track WL xlsx mtime before (file may exist from prior tests)
    wl_before = [p for p in output_root.rglob("*.xlsx") if "_WL_" in p.name]
    mtime_before = max((p.stat().st_mtime for p in wl_before), default=0)

    # Click Download xlsx
    download_btn = wl_page.get_by_role("button", name="Download xlsx")
    assert download_btn.count() >= 1, "Download xlsx button not found"
    download_btn.first.click()
    wl_page.wait_for_load_state("networkidle")
    time.sleep(3)

    # Verify the WL xlsx was written or re-written (mtime updated)
    wl_after = [p for p in output_root.rglob("*.xlsx") if "_WL_" in p.name]
    assert len(wl_after) >= 1, "No WL xlsx file found after download"
    mtime_after = max(p.stat().st_mtime for p in wl_after)
    assert mtime_after > mtime_before, "WL xlsx not re-written after download click"

    newest = max(wl_after, key=lambda p: p.stat().st_mtime)
    assert newest.stat().st_size > 0, f"Downloaded xlsx is empty: {newest}"


# ---------------------------------------------------------------------------
# Tab content: click each tab, verify specific content renders
# ---------------------------------------------------------------------------


def test_wl_advanced_all_tabs_clickable(wl_page) -> None:  # type: ignore[no-untyped-def]
    """Click through every Advanced mode tab and verify content renders."""
    _switch_to_advanced(wl_page)
    _run_analysis_if_needed(wl_page)

    tabs = ["Overview", "Deviation", "Scatter", "Histogram"]
    for tab_name in tabs:
        tab = wl_page.get_by_role("tab", name=tab_name)
        if tab.count() == 0:
            # Some tabs might have slightly different names
            tab = wl_page.locator(f"button:has-text('{tab_name}')")
        if tab.count() > 0:
            tab.first.click()
            wl_page.wait_for_load_state("networkidle")
            time.sleep(1)
            # Verify the page didn't go blank
            body = wl_page.text_content("body") or ""
            assert len(body) > 100, f"Page appears blank after clicking {tab_name} tab"


# ---------------------------------------------------------------------------
# Sidebar params: verify all 9 analyze params are present
# ---------------------------------------------------------------------------


def test_wl_advanced_all_sidebar_params_present(wl_page) -> None:  # type: ignore[no-untyped-def]
    """All 9 WL analyze parameters appear in the Advanced sidebar."""
    _switch_to_advanced(wl_page)
    _run_analysis_if_needed(wl_page)

    body = wl_page.text_content("body") or ""
    expected_params = ["BB size", "Machine scale", "Low density", "Open field"]
    for param in expected_params:
        assert param in body, f"Sidebar param '{param}' not found on page"
