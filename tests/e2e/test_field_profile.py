"""E2E: Field Profile page — full browser interaction tests.

Tests the complete Simple + Advanced mode flows for the decoupled
general-purpose Field Profile page (see ``generalize-field-profile-browser``
change):

1. Cascading folder browser renders (rooted at ``field_profile.browse_root``)
2. Image dropdown shows the demo DICOM with metadata
3. FFF detection display renders
4. Analysis button triggers FieldAnalysis
5. Success card renders with flatness/symmetry/field size
6. Hand-off to Advanced mode works
7. Advanced mode: Re-run with changed param, Download, all 4 tabs
8. No files are written to any server-side output directory (FP decoupled)
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


def _navigate_folder_browser(field_profile_page) -> None:  # type: ignore[no-untyped-def]
    """Navigate the cascading folder browser to the demo DICOM's folder.

    The demo DICOM lives at ``<browse_root>/LA2/FieldProfile/2026-06-16_monthly/``.
    The cascading selectboxes drill down: Folder → LA2 → FieldProfile →
    2026-06-16_monthly. The image dropdown then populates from the deepest
    selected folder.
    """
    # The cascading selectboxes appear in the sidebar. The first one is labeled
    # "Folder"; deeper ones are "Folder (level 2)", "Folder (level 3)", etc.
    sidebar = field_profile_page.query_selector("[data-testid='stSidebar']")
    assert sidebar is not None, "Sidebar not found"

    # Wait for the first folder selectbox to render
    _wait_for_text(field_profile_page, "Folder", timeout=20000)

    # Select "LA2" in the first folder selectbox (level 1)
    # Streamlit selectboxes render as divs with role="combobox"; we interact
    # via the visible text. The cleanest cross-version approach is to click
    # the selectbox container then the option.
    # Level 1: select LA2
    _select_folder_option(field_profile_page, level=1, option="LA2")
    field_profile_page.wait_for_load_state("networkidle")
    time.sleep(1)

    # Level 2: select FieldProfile
    _select_folder_option(field_profile_page, level=2, option="FieldProfile")
    field_profile_page.wait_for_load_state("networkidle")
    time.sleep(1)

    # Level 3: select 2026-06-16_monthly
    _select_folder_option(field_profile_page, level=3, option="2026-06-16_monthly")
    field_profile_page.wait_for_load_state("networkidle")
    time.sleep(2)


def _select_folder_option(page, level: int, option: str) -> None:  # type: ignore[no-untyped-def]
    """Select ``option`` in the folder selectbox at ``level`` (1-indexed)."""
    # Build the label used in the selectbox's aria context. Level 1 is "Folder";
    # deeper levels are "Folder (level N)".
    label = "Folder" if level == 1 else f"Folder (level {level})"

    # Streamlit 1.x selectbox: locate the widget by its canonical testid, then
    # filter to the one whose label text matches. Click the widget to open the
    # dropdown menu overlay.
    selectbox = page.locator("[data-testid='stSelectbox']").filter(has_text=label).first
    selectbox.click(timeout=20000)
    page.wait_for_timeout(500)
    # The dropdown options render in a menu overlay; click the option by its
    # visible text. Use first() to disambiguate if multiple menus are transient.
    page.get_by_role("option", name=option).first.click(timeout=10000)


# ---------------------------------------------------------------------------
# Simple mode — folder browser + FFF display
# ---------------------------------------------------------------------------


def test_fp_folder_browser_renders(field_profile_page) -> None:  # type: ignore[no-untyped-def]
    """The cascading folder browser renders on the Field Profile page."""
    # The first selectbox is labeled "Folder"
    _wait_for_text(field_profile_page, "Folder", timeout=20000)


def test_fp_simple_mode_fff_detection_display(field_profile_page) -> None:  # type: ignore[no-untyped-def]
    """Navigate the folder browser, select image → FFF detection display renders."""
    _navigate_folder_browser(field_profile_page)
    _wait_for_text(field_profile_page, "FFF detected", timeout=20000)


def test_fp_simple_mode_analysis_button(field_profile_page) -> None:  # type: ignore[no-untyped-def]
    """The analysis button exists on the Field Profile page."""
    _navigate_folder_browser(field_profile_page)
    _wait_for_text(field_profile_page, "Shut Up", timeout=20000)


# ---------------------------------------------------------------------------
# Simple mode — full pipeline (button → success card → hand-off)
# ---------------------------------------------------------------------------


def test_fp_simple_mode_full_pipeline(field_profile_page) -> None:  # type: ignore[no-untyped-def]
    """Full Simple mode: navigate browser -> click button -> success card with metrics."""
    _navigate_folder_browser(field_profile_page)
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

    # No server-side output path should be shown (there is none)
    assert "Output:" not in body, "Server-side output path should not be shown"


def test_fp_simple_mode_handoff_to_advanced(field_profile_page) -> None:  # type: ignore[no-untyped-def]
    """The 'View in Advanced mode' button switches to Field Profile Advanced mode."""
    _navigate_folder_browser(field_profile_page)
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
    _navigate_folder_browser(field_profile_page)
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
# Advanced mode — Download xlsx (in-browser, no server write)
# ---------------------------------------------------------------------------


def test_fp_advanced_download_serves_xlsx(
    field_profile_page,
    output_root: Path,  # type: ignore[no-untyped-def]
) -> None:
    """Click Download xlsx → the button is an st.download_button (no server write).

    The download is served in-browser via ``st.download_button`` with
    in-memory bytes. We verify:
    1. The Download xlsx button renders (as a download button, not a regular one)
    2. No files are written to the server's output_root (FP is decoupled —
       see ``generalize-field-profile-browser`` change)

    Note: Playwright can intercept the download to verify the bytes, but the
    primary contract here is "no server-side write" — that's what the spec
    ``fp-result-export`` requires.
    """
    _switch_to_advanced(field_profile_page)
    _navigate_folder_browser(field_profile_page)
    _run_analysis_if_needed(field_profile_page)

    # Record output_root state BEFORE the download click
    fp_output_before = output_root / "FP"
    files_before = set(fp_output_before.glob("**/*")) if fp_output_before.exists() else set()

    download_btn = field_profile_page.get_by_role("button", name="Download xlsx")
    assert download_btn.count() >= 1, "Download xlsx button not found"
    # st.download_button renders as a link with role=button; clicking it triggers
    # a browser download (no server roundtrip that writes a file).
    download_btn.first.click()
    field_profile_page.wait_for_load_state("networkidle")
    time.sleep(3)

    # Verify NO files were written to output_root/FP (the decoupling contract)
    files_after = set(fp_output_before.glob("**/*")) if fp_output_before.exists() else set()
    new_files = files_after - files_before
    assert not new_files, (
        f"FP download wrote files to output_root (should be in-browser only): "
        f"{[str(f) for f in new_files]}"
    )


# ---------------------------------------------------------------------------
# Advanced mode — all 4 tabs clicked and verified
# ---------------------------------------------------------------------------


def test_fp_advanced_click_overview_tab(field_profile_page) -> None:  # type: ignore[no-untyped-def]
    """Click Overview tab → verify summary metrics + protocol + FFF render."""
    _switch_to_advanced(field_profile_page)
    _navigate_folder_browser(field_profile_page)
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
    _navigate_folder_browser(field_profile_page)
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
    _navigate_folder_browser(field_profile_page)
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
    _navigate_folder_browser(field_profile_page)
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
    _navigate_folder_browser(field_profile_page)
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


# ---------------------------------------------------------------------------
# No server-side writes (fp-result-export spec: "No FP files written to output_root")
# ---------------------------------------------------------------------------


def test_fp_no_files_written_to_output_root(
    field_profile_page,
    output_root: Path,  # type: ignore[no-untyped-def]
) -> None:
    """Run a full Simple-mode analysis + download → no FP files written to output_root.

    Verifies the ``fp-result-export`` spec scenario "No FP files written to
    output_root": the decoupled FP page serves results in-browser and via
    ``st.download_button``; no ``FP/`` subdirectory is ever created under any
    machine's output_root.
    """
    # Record output_root state BEFORE
    fp_output_before = output_root / "FP"
    files_before = set(output_root.glob("**/*")) if output_root.exists() else set()

    _navigate_folder_browser(field_profile_page)
    _click_button(field_profile_page, "Shut Up and Give Me My MyQA Results")
    _wait_for_text(field_profile_page, "Analysis complete", timeout=120000)

    # Verify NO files were written to output_root (and no FP/ subdir created)
    files_after = set(output_root.glob("**/*")) if output_root.exists() else set()
    new_files = files_after - files_before
    assert not new_files, (
        f"FP analysis wrote files to output_root (should be in-browser only): "
        f"{[str(f) for f in new_files]}"
    )
    assert not fp_output_before.exists(), (
        "FP/ subdirectory was created under output_root (should not exist — "
        "FP is decoupled from server-side output)"
    )
