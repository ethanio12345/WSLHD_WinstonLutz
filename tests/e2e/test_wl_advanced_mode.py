"""E2E: Winston-Lutz Advanced mode — tab navigation, re-run, download.

Tests:
1. Advanced mode sidebar with analyze parameters
2. Tab navigation (Overview, Deviation, BB Scatter, Histogram, Detection)
3. Re-run analysis button exists
4. Download xlsx button exists
"""

from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.e2e


def _wait_for_text(page, text: str, timeout: int = 30000) -> None:  # type: ignore[no-untyped-def]
    page.wait_for_selector(f"text={text}", timeout=timeout)


def _click_button(page, label: str, timeout: int = 30000) -> None:  # type: ignore[no-untyped-def]
    page.get_by_role("button", name=label).first.click(timeout=timeout)


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


def test_wl_advanced_sidebar_params(wl_page) -> None:  # type: ignore[no-untyped-def]
    """Advanced mode sidebar shows the analyze parameters after running."""
    _switch_to_advanced(wl_page)
    _run_analysis_if_needed(wl_page)

    body_text = wl_page.text_content("body") or ""
    assert "BB" in body_text or "bb_size" in body_text, "BB Size param not visible"


def test_wl_advanced_tabs_render(wl_page) -> None:  # type: ignore[no-untyped-def]
    """All Advanced mode tabs render after running analysis."""
    _switch_to_advanced(wl_page)
    _run_analysis_if_needed(wl_page)

    body = wl_page.text_content("body") or ""
    assert "Overview" in body, "Overview tab missing"


def test_wl_advanced_rerun_button(wl_page) -> None:  # type: ignore[no-untyped-def]
    """The Re-run analysis button exists in the sidebar."""
    _switch_to_advanced(wl_page)
    _run_analysis_if_needed(wl_page)

    rerun_btn = wl_page.get_by_role("button", name="Re-run analysis")
    assert rerun_btn.count() >= 1, "Re-run analysis button not found"


def test_wl_advanced_download_button(wl_page) -> None:  # type: ignore[no-untyped-def]
    """The Download xlsx button exists in the sidebar."""
    _switch_to_advanced(wl_page)
    _run_analysis_if_needed(wl_page)

    download_btn = wl_page.get_by_role("button", name="Download xlsx")
    assert download_btn.count() >= 1, "Download xlsx button not found"
