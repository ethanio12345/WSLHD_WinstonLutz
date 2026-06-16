"""E2E: CatPhan Advanced mode — full interactive workflows.

Every button is clicked, every flow is exercised end-to-end:
1. Switch to Advanced, run analysis from sidebar
2. Change HU tolerance, click Re-run, verify new result
3. Click Download xlsx, verify file appears on disk
4. Click all 5 CTP tabs, verify specific content renders
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def _wait_for_text(page, text: str, timeout: int = 30000) -> None:  # type: ignore[no-untyped-def]
    page.wait_for_selector(f"text={text}", timeout=timeout)


def _switch_to_advanced(catphan_page) -> None:  # type: ignore[no-untyped-def]
    """Switch to Advanced mode via the sidebar toggle."""
    catphan_page.get_by_text("Advanced").first.click()
    catphan_page.wait_for_load_state("networkidle")
    time.sleep(2)


def _run_analysis_if_needed(page, timeout: int = 180000) -> None:  # type: ignore[no-untyped-def]
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
# Full Re-run workflow: change HU tolerance → click Re-run → verify new result
# ---------------------------------------------------------------------------


def test_cp_advanced_rerun_with_changed_param(catphan_page) -> None:  # type: ignore[no-untyped-def]
    """Change HU tolerance from 40 to 80, click Re-run, verify new value."""
    _switch_to_advanced(catphan_page)
    _run_analysis_if_needed(catphan_page)

    # Change HU tolerance in the sidebar
    hu_input = _get_sidebar_param_input(catphan_page, "HU tolerance")
    hu_input.click()
    hu_input.press("Control+a")
    hu_input.type("80")
    hu_input.press("Tab")
    catphan_page.wait_for_load_state("networkidle")
    time.sleep(2)

    # Click Re-run analysis
    rerun_btn = catphan_page.get_by_role("button", name="Re-run analysis")
    assert rerun_btn.count() >= 1, "Re-run button not found"
    rerun_btn.first.click()

    # Wait for the analysis to complete (CatPhan takes ~30-60s)
    _wait_for_text(catphan_page, "Overview", timeout=180000)
    time.sleep(3)

    # Verify the result reflects the new HU tolerance
    body_after = catphan_page.text_content("body") or ""
    assert "80" in body_after, (
        f"New HU tolerance 80 not reflected in result. Body snippet: {body_after[:500]}"
    )


# ---------------------------------------------------------------------------
# Full Download workflow: click Download → verify xlsx on disk
# ---------------------------------------------------------------------------


def test_cp_advanced_download_produces_xlsx(
    catphan_page,
    output_root: Path,  # type: ignore[no-untyped-def]
) -> None:
    """Click Download xlsx, verify the CatPhan xlsx file is written."""
    _switch_to_advanced(catphan_page)
    _run_analysis_if_needed(catphan_page)

    xlsx_before = list(output_root.rglob("*.xlsx"))

    download_btn = catphan_page.get_by_role("button", name="Download xlsx")
    assert download_btn.count() >= 1, "Download xlsx button not found"
    download_btn.first.click()
    catphan_page.wait_for_load_state("networkidle")
    time.sleep(3)

    xlsx_after = list(output_root.rglob("*.xlsx"))
    assert len(xlsx_after) > len(xlsx_before), (
        f"No new xlsx after download. Before={len(xlsx_before)}, After={len(xlsx_after)}"
    )

    newest = max(xlsx_after, key=lambda p: p.stat().st_mtime)
    assert newest.stat().st_size > 0, f"Downloaded xlsx is empty: {newest}"


# ---------------------------------------------------------------------------
# Tab content: click each of the 5 CTP tabs, verify specific content
# ---------------------------------------------------------------------------


def test_cp_advanced_click_ctp404_tab(catphan_page) -> None:  # type: ignore[no-untyped-def]
    """Click CTP404 tab → verify HU linearity materials render."""
    _switch_to_advanced(catphan_page)
    _run_analysis_if_needed(catphan_page)

    catphan_page.get_by_role("tab", name="CTP404").first.click()
    catphan_page.wait_for_load_state("networkidle")
    time.sleep(2)

    body = catphan_page.text_content("body") or ""
    assert "Air" in body or "Teflon" in body or "Acrylic" in body, (
        "HU linearity materials not visible in CTP404 tab"
    )
    assert "Geometry" in body or "line" in body.lower(), "Geometry data not visible in CTP404 tab"


def test_cp_advanced_click_ctp486_tab(catphan_page) -> None:  # type: ignore[no-untyped-def]
    """Click CTP486 tab → verify uniformity ROIs render."""
    _switch_to_advanced(catphan_page)
    _run_analysis_if_needed(catphan_page)

    catphan_page.get_by_role("tab", name="CTP486").first.click()
    catphan_page.wait_for_load_state("networkidle")
    time.sleep(2)

    body = catphan_page.text_content("body") or ""
    assert "Center" in body or "uniformity" in body.lower(), (
        "Uniformity data not visible in CTP486 tab"
    )


def test_cp_advanced_click_ctp528_tab(catphan_page) -> None:  # type: ignore[no-untyped-def]
    """Click CTP528 tab → verify MTF curve/table renders."""
    _switch_to_advanced(catphan_page)
    _run_analysis_if_needed(catphan_page)

    catphan_page.get_by_role("tab", name="CTP528").first.click()
    catphan_page.wait_for_load_state("networkidle")
    time.sleep(2)

    body = catphan_page.text_content("body") or ""
    assert "MTF" in body or "lp/mm" in body, "MTF data not visible in CTP528 tab"


def test_cp_advanced_click_ctp515_tab(catphan_page) -> None:  # type: ignore[no-untyped-def]
    """Click CTP515 tab → verify low contrast ROI data renders."""
    _switch_to_advanced(catphan_page)
    _run_analysis_if_needed(catphan_page)

    catphan_page.get_by_role("tab", name="CTP515").first.click()
    catphan_page.wait_for_load_state("networkidle")
    time.sleep(2)

    body = catphan_page.text_content("body") or ""
    assert "ROI" in body or "Contrast" in body or "rois" in body.lower(), (
        "Low contrast ROI data not visible in CTP515 tab"
    )


def test_cp_advanced_click_overview_tab(catphan_page) -> None:  # type: ignore[no-untyped-def]
    """Click Overview tab → verify summary metrics render."""
    _switch_to_advanced(catphan_page)
    _run_analysis_if_needed(catphan_page)

    catphan_page.get_by_role("tab", name="Overview").first.click()
    catphan_page.wait_for_load_state("networkidle")
    time.sleep(2)

    body = catphan_page.text_content("body") or ""
    assert "Machine" in body or "Images" in body, "Session metadata not visible in Overview tab"
    assert "Analysed with" in body or "hu_tolerance" in body, (
        "Params summary not visible in Overview tab"
    )


# ---------------------------------------------------------------------------
# Sidebar params: verify CatPhan analyze params present
# ---------------------------------------------------------------------------


def test_cp_advanced_all_sidebar_params_present(catphan_page) -> None:  # type: ignore[no-untyped-def]
    """All CatPhan analyze parameters appear in the Advanced sidebar."""
    _switch_to_advanced(catphan_page)
    _run_analysis_if_needed(catphan_page)

    body = catphan_page.text_content("body") or ""
    expected_params = [
        "HU tolerance",
        "Scaling tolerance",
        "Slice thickness tolerance",
        "X adjustment",
        "Y adjustment",
        "Angle adjustment",
        "ROI size factor",
        "Scaling factor",
        "Minimum ROIs",
    ]
    for param in expected_params:
        assert param in body, f"Sidebar param '{param}' not found on page"
