"""E2E: Winston-Lutz Simple mode — full browser interaction test.

Tests the complete Simple mode flow:
1. Machine dropdown shows the test machine
2. Runfolder preview appears
3. "Shut Up and Give Me My MyQA Results" button click triggers analysis
4. Success card renders with pass/fail metrics
5. Hand-off to Advanced mode works
"""

from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.e2e


def _wait_for_text(page, text: str, timeout: int = 30000) -> None:  # type: ignore[no-untyped-def]
    """Wait until ``text`` appears on the page."""
    page.wait_for_selector(f"text={text}", timeout=timeout)


def _click_streamlit_button(page, label: str, timeout: int = 30000) -> None:  # type: ignore[no-untyped-def]
    """Click a Streamlit button by its label text."""
    btn = page.get_by_role("button", name=label)
    btn.first.click(timeout=timeout)


def test_wl_machine_dropdown_shows_machine(wl_page) -> None:  # type: ignore[no-untyped-def]
    """The WL page machine dropdown shows the test machine (LA2)."""
    _wait_for_text(wl_page, "LA2", timeout=20000)


def test_wl_simple_mode_runfolder_preview(wl_page) -> None:  # type: ignore[no-untyped-def]
    """The runfolder preview appears with a DICOM count."""
    _wait_for_text(wl_page, "DICOM", timeout=20000)


def test_wl_simple_mode_analysis_button(wl_page) -> None:  # type: ignore[no-untyped-def]
    """The 'Shut Up and Give Me My MyQA Results' button exists."""
    _wait_for_text(wl_page, "Shut Up", timeout=20000)


def test_wl_simple_mode_full_pipeline(wl_page) -> None:  # type: ignore[no-untyped-def]
    """Full Simple mode pipeline: click button -> success card appears."""
    # Click the analysis button
    _click_streamlit_button(wl_page, "Shut Up and Give Me My MyQA Results")

    # Wait for the success card (analysis takes a few seconds)
    _wait_for_text(wl_page, "Analysis complete", timeout=120000)

    # Verify pass/fail metrics appear
    body = wl_page.text_content("body") or ""
    assert "PASS" in body or "FAIL" in body, "No pass/fail badge in success card"

    # Verify the xlsx output path is shown
    assert ".xlsx" in body or ".xltx" in body, "No output path in success card"


def test_wl_simple_mode_handoff_to_advanced(wl_page) -> None:  # type: ignore[no-untyped-def]
    """The 'View in Advanced mode' button switches to Advanced mode."""
    # First run the analysis to get the success card
    _click_streamlit_button(wl_page, "Shut Up and Give Me My MyQA Results")
    _wait_for_text(wl_page, "Analysis complete", timeout=120000)

    # Click hand-off button
    _click_streamlit_button(wl_page, "View in Advanced mode")
    wl_page.wait_for_load_state("networkidle")
    time.sleep(3)

    # Verify we're in Advanced mode (tabs should appear)
    body = wl_page.text_content("body") or ""
    assert "Overview" in body or "Deviation" in body, (
        "Advanced mode tabs not visible after hand-off"
    )
