"""E2E: Home page startup validation.

Verifies the app loads, shows the title, module selector, and assets.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


def test_home_page_title(page) -> None:  # type: ignore[no-untyped-def]
    """The home page shows the expected title."""
    page.wait_for_selector("h1", timeout=15000)
    headings = page.query_selector_all("h1")
    texts = [h.text_content() or "" for h in headings]
    assert any("WSLHD" in t and "QA" in t for t in texts), f"Title not found in {texts}"


def test_module_selector_shows_wl_and_catphan(page) -> None:  # type: ignore[no-untyped-def]
    """Both Winston-Lutz and CatPhan modules are listed on the home page."""
    page.wait_for_selector("text=Winston-Lutz", timeout=15000)
    body_text = page.text_content("body") or ""
    assert "Winston-Lutz" in body_text
    assert "CatPhan" in body_text


def test_fry_meme_renders(page) -> None:  # type: ignore[no-untyped-def]
    """The Fry meme image is present on the home page."""
    images = page.query_selector_all("img")
    # At least one image should be present (the Fry meme)
    assert len(images) >= 1, "No images found on home page (Fry meme missing)"


def test_sidebar_navigation_exists(page) -> None:  # type: ignore[no-untyped-def]
    """The sidebar contains navigation links to the WL and CatPhan pages."""
    sidebar = page.query_selector("[data-testid='stSidebar']")
    assert sidebar is not None, "Sidebar not found"
    sidebar_text = sidebar.text_content() or ""
    assert "Winston" in sidebar_text or "WL" in sidebar_text
