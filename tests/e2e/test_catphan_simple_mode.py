"""E2E: CatPhan Simple mode — full browser interaction test.

Tests the complete Simple mode flow:
1. Machine dropdown shows the test machine (with catphan configured)
2. Runfolder preview appears
3. Analysis button triggers CatPhan analysis
4. Success card renders with 4 pass/fail flags
5. Hand-off to Advanced mode works
"""

from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.e2e


def _wait_for_text(page, text: str, timeout: int = 30000) -> None:  # type: ignore[no-untyped-def]
    page.wait_for_selector(f"text={text}", timeout=timeout)


def _click_button(page, label: str, timeout: int = 30000) -> None:  # type: ignore[no-untyped-def]
    page.get_by_role("button", name=label).first.click(timeout=timeout)


def test_cp_machine_dropdown_shows_machine(catphan_page) -> None:  # type: ignore[no-untyped-def]
    """The CatPhan page machine dropdown shows the test machine."""
    _wait_for_text(catphan_page, "LA2", timeout=20000)


def test_cp_simple_mode_runfolder_preview(catphan_page) -> None:  # type: ignore[no-untyped-def]
    """The runfolder preview appears with a DICOM count."""
    _wait_for_text(catphan_page, "DICOM", timeout=20000)


def test_cp_simple_mode_analysis_button(catphan_page) -> None:  # type: ignore[no-untyped-def]
    """The analysis button exists on the CatPhan page."""
    _wait_for_text(catphan_page, "Shut Up", timeout=20000)


def test_cp_simple_mode_full_pipeline(catphan_page) -> None:  # type: ignore[no-untyped-def]
    """Full CatPhan Simple mode: click button -> success card with 4 flags."""
    _click_button(catphan_page, "Shut Up and Give Me My MyQA Results")

    # CatPhan analysis takes longer (~30-60s for demo data)
    _wait_for_text(catphan_page, "Analysis complete", timeout=180000)

    body = catphan_page.text_content("body") or ""

    # Verify the 4 pass/fail flags are present
    assert "HU Linearity" in body, "HU Linearity flag missing from success card"
    assert "Geometry" in body, "Geometry flag missing"
    assert "Uniformity" in body, "Uniformity flag missing"
    assert "Thickness" in body, "Thickness flag missing"

    # Verify pass/fail badges
    assert "PASS" in body or "FAIL" in body

    # Verify LCV metric
    assert "Low Contrast" in body or "Contrast Visibility" in body


def test_cp_simple_mode_handoff_to_advanced(catphan_page) -> None:  # type: ignore[no-untyped-def]
    """The 'View in Advanced mode' button switches to CatPhan Advanced mode."""
    _click_button(catphan_page, "Shut Up and Give Me My MyQA Results")
    _wait_for_text(catphan_page, "Analysis complete", timeout=180000)

    _click_button(catphan_page, "View in Advanced mode")
    catphan_page.wait_for_load_state("networkidle")
    time.sleep(3)

    # Verify Advanced mode tabs appear (Overview + CTP modules)
    body = catphan_page.text_content("body") or ""
    assert "Overview" in body, "Overview tab not visible after hand-off"
    assert "CTP404" in body, "CTP404 tab not visible after hand-off"
