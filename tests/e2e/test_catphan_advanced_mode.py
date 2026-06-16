"""E2E: CatPhan Advanced mode — 5-tab navigation, re-run, download.

Tests:
1. Advanced mode sidebar with CatPhan analyze parameters
2. All 5 tabs render (Overview, CTP404, CTP486, CTP528, CTP515)
3. CTP404 tab shows HU linearity materials
4. CTP528 tab shows MTF data
5. Re-run analysis button exists
6. Download xlsx button exists
"""

from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.e2e


def _wait_for_text(page, text: str, timeout: int = 30000) -> None:  # type: ignore[no-untyped-def]
    page.wait_for_selector(f"text={text}", timeout=timeout)


def _click_button(page, label: str, timeout: int = 30000) -> None:  # type: ignore[no-untyped-def]
    page.get_by_role("button", name=label).first.click(timeout=timeout)


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


def test_cp_advanced_sidebar_params(catphan_page) -> None:  # type: ignore[no-untyped-def]
    """Advanced mode sidebar shows CatPhan analyze parameters."""
    _switch_to_advanced(catphan_page)
    _run_analysis_if_needed(catphan_page)

    body_text = catphan_page.text_content("body") or ""
    assert "HU tolerance" in body_text, "HU tolerance param not visible"
    assert "Scaling tolerance" in body_text, "Scaling tolerance param not visible"


def test_cp_advanced_all_tabs_render(catphan_page) -> None:  # type: ignore[no-untyped-def]
    """All 5 CatPhan Advanced mode tabs render."""
    _switch_to_advanced(catphan_page)
    _run_analysis_if_needed(catphan_page)

    body = catphan_page.text_content("body") or ""
    assert "Overview" in body, "Overview tab missing"
    assert "CTP404" in body, "CTP404 tab missing"
    assert "CTP486" in body, "CTP486 tab missing"
    assert "CTP528" in body, "CTP528 tab missing"
    assert "CTP515" in body, "CTP515 tab missing"


def test_cp_advanced_ctp404_tab_content(catphan_page) -> None:  # type: ignore[no-untyped-def]
    """CTP404 tab shows HU linearity materials when clicked."""
    _switch_to_advanced(catphan_page)
    _run_analysis_if_needed(catphan_page)

    catphan_page.get_by_text("CTP404", exact=False).first.click()
    catphan_page.wait_for_load_state("networkidle")
    time.sleep(2)

    body = catphan_page.text_content("body") or ""
    assert "Air" in body or "Teflon" in body or "Acrylic" in body, (
        "HU linearity materials not visible in CTP404 tab"
    )


def test_cp_advanced_ctp528_tab_content(catphan_page) -> None:  # type: ignore[no-untyped-def]
    """CTP528 tab shows MTF data when clicked."""
    _switch_to_advanced(catphan_page)
    _run_analysis_if_needed(catphan_page)

    catphan_page.get_by_text("CTP528", exact=False).first.click()
    catphan_page.wait_for_load_state("networkidle")
    time.sleep(2)

    body = catphan_page.text_content("body") or ""
    assert "MTF" in body or "lp/mm" in body, "MTF data not visible in CTP528 tab"


def test_cp_advanced_rerun_button(catphan_page) -> None:  # type: ignore[no-untyped-def]
    """The Re-run analysis button exists."""
    _switch_to_advanced(catphan_page)
    _run_analysis_if_needed(catphan_page)

    rerun_btn = catphan_page.get_by_role("button", name="Re-run analysis")
    assert rerun_btn.count() >= 1, "Re-run analysis button not found"


def test_cp_advanced_download_button(catphan_page) -> None:  # type: ignore[no-untyped-def]
    """The Download xlsx button exists."""
    _switch_to_advanced(catphan_page)
    _run_analysis_if_needed(catphan_page)

    download_btn = catphan_page.get_by_role("button", name="Download xlsx")
    assert download_btn.count() >= 1, "Download xlsx button not found"
