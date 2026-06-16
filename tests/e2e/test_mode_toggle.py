"""E2E: Mode toggle persistence — switch Simple <-> Advanced and verify state.

Tests:
1. Run in Simple → switch to Advanced → verify result preserved
2. Switch back to Simple → verify success card still present
3. Switch Advanced → Simple → Advanced → verify no data loss
"""

from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.e2e


def _wait_for_text(page, text: str, timeout: int = 30000) -> None:  # type: ignore[no-untyped-def]
    page.wait_for_selector(f"text={text}", timeout=timeout)


def _click_button(page, label: str, timeout: int = 30000) -> None:  # type: ignore[no-untyped-def]
    page.get_by_role("button", name=label).first.click(timeout=timeout)


def _click_mode(page, mode: str) -> None:  # type: ignore[no-untyped-def]
    """Click the Simple or Advanced radio toggle."""
    page.get_by_text(mode).first.click()
    page.wait_for_load_state("networkidle")
    time.sleep(2)


def test_wl_simple_to_advanced_preserves_result(wl_page) -> None:  # type: ignore[no-untyped-def]
    """Run analysis in Simple, switch to Advanced, verify result is there."""
    # Run analysis in Simple mode
    _click_button(wl_page, "Shut Up and Give Me My MyQA Results")
    _wait_for_text(wl_page, "Analysis complete", timeout=120000)
    _wait_for_text(wl_page, "PASS", timeout=10000)

    # Switch to Advanced
    _click_button(wl_page, "View in Advanced mode")
    wl_page.wait_for_load_state("networkidle")
    time.sleep(3)

    # Verify Advanced mode shows the result (Overview tab with data)
    body = wl_page.text_content("body") or ""
    assert "Overview" in body, "Advanced mode didn't load with the result"


def test_wl_advanced_back_to_simple(wl_page) -> None:  # type: ignore[no-untyped-def]
    """Run in Simple, switch to Advanced, switch back to Simple — result persists."""
    # Run in Simple
    _click_button(wl_page, "Shut Up and Give Me My MyQA Results")
    _wait_for_text(wl_page, "Analysis complete", timeout=120000)

    # Switch to Advanced via hand-off
    _click_button(wl_page, "View in Advanced mode")
    wl_page.wait_for_load_state("networkidle")
    time.sleep(3)

    # Switch back to Simple via the toggle
    _click_mode(wl_page, "Simple")
    wl_page.wait_for_load_state("networkidle")
    time.sleep(2)

    # Verify the success card is still showing (result persisted)
    body = wl_page.text_content("body") or ""
    assert "Analysis complete" in body or "PASS" in body, (
        "Result not preserved after switching Advanced -> Simple"
    )


def test_wl_mode_toggle_roundtrip(wl_page) -> None:  # type: ignore[no-untyped-def]
    """Toggle Simple -> Advanced -> Simple -> Advanced without data loss."""
    # Run in Simple
    _click_button(wl_page, "Shut Up and Give Me My MyQA Results")
    _wait_for_text(wl_page, "Analysis complete", timeout=120000)

    # Toggle: Simple -> Advanced
    _click_mode(wl_page, "Advanced")
    time.sleep(2)
    body_adv1 = wl_page.text_content("body") or ""
    assert "Overview" in body_adv1, "Advanced not loaded on first toggle"

    # Toggle: Advanced -> Simple
    _click_mode(wl_page, "Simple")
    time.sleep(2)
    body_simp = wl_page.text_content("body") or ""
    assert "Analysis complete" in body_simp or "PASS" in body_simp, (
        "Result lost after Advanced -> Simple"
    )

    # Toggle: Simple -> Advanced again
    _click_mode(wl_page, "Advanced")
    time.sleep(2)
    body_adv2 = wl_page.text_content("body") or ""
    assert "Overview" in body_adv2, "Advanced not loaded on second toggle"
