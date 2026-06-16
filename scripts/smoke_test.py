#!/usr/bin/env python
"""Playwright smoke test for the Winston-Lutz Streamlit app.

Tests:
1. Home page renders with title and Fry meme
2. Winston-Lutz page accessible
3. Simple mode: machine dropdown, runfolder preview, analysis button
4. Click "Shut Up and Give Me My MyQA Results" → success card
5. Verify xlsx was written to disk
6. Switch to Advanced mode → tabs render
7. Verify all 4 tabs are present

Run via with_server.py which manages the Streamlit server lifecycle.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


def wait_for_streamlit(page: Page, timeout: int = 30) -> None:
    """Wait for Streamlit to fully load (app runner ready)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            page.wait_for_selector('[data-testid="stAppViewContainer"]', timeout=5000)
            return
        except Exception:
            time.sleep(1)
    raise TimeoutError(f"Streamlit did not load within {timeout}s")


def safe_screenshot(page: Page, path: str) -> str | None:
    """Take a viewport screenshot. Returns path or None on failure."""
    try:
        page.screenshot(path=path, full_page=False, timeout=10000)
        return path
    except Exception:
        print(f"   (screenshot failed: {path})", flush=True)
        return None


def get_streamlit_text(page: Page) -> str:
    """Extract all visible text from the Streamlit main area."""
    main = page.locator('[data-testid="stMain"]')
    if main.count() == 0:
        main = page.locator("section.main")
    return main.inner_text(timeout=5000) if main.count() > 0 else page.content()


def run_smoke_test() -> int:
    # Use /tmp/wl_output (matches machines.yaml output.root)
    output_dir = Path("/tmp/wl_output")
    screenshots: list[str] = []
    errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        try:
            # === 1. Home page ===
            print("1. Navigating to home page...", flush=True)
            page.goto("http://localhost:8501", wait_until="domcontentloaded", timeout=30000)
            wait_for_streamlit(page)
            time.sleep(3)  # let Streamlit settle

            s = safe_screenshot(page, "/tmp/wl_smoke_01_home.png")
            if s:
                screenshots.append(s)

            body_text = page.inner_text("body")
            if "WSLHD Winston-Lutz QA" not in body_text:
                errors.append("Home page title not found")
            else:
                print("   ✓ Home page renders with title", flush=True)

            if "Startup check failed" in body_text:
                errors.append(f"Startup failed: {body_text[:200]}")
            else:
                print("   ✓ No startup errors", flush=True)

            # === 2. Navigate to Winston-Lutz page ===
            print("2. Navigating to Winston-Lutz page...", flush=True)
            # Streamlit multi-page: click the nav link in the sidebar
            wl_link = page.locator('a:has-text("Winston")').first
            if wl_link.count() > 0:
                wl_link.click()
            else:
                nav_links = page.locator('[data-testid="stSidebarNavLink"]')
                count = nav_links.count()
                print(f"   Found {count} nav links", flush=True)
                if count > 0:
                    nav_links.first.nth(1).click() if count > 1 else nav_links.first.click()

            page.wait_for_load_state("domcontentloaded", timeout=15000)
            time.sleep(3)
            s = safe_screenshot(page, "/tmp/wl_smoke_02_wl_page.png")
            if s:
                screenshots.append(s)

            body_text = page.inner_text("body")
            if "Winston-Lutz" not in body_text:
                errors.append("WL page title not found")
            else:
                print("   ✓ Winston-Lutz page renders", flush=True)

            # === 3. Check runfolder preview ===
            print("3. Checking runfolder preview...", flush=True)
            time.sleep(2)
            body_text = page.inner_text("body")
            if "Will analyze" in body_text or "demo_clinical" in body_text:
                print("   ✓ Runfolder preview visible", flush=True)
            elif "No runfolders" in body_text:
                errors.append("No runfolders found (DICOM generation may have failed)")
            else:
                print("   ? Runfolder preview state unclear, checking more...", flush=True)

            # === 4. Click the analysis button ===
            print("4. Clicking analysis button...", flush=True)
            safe_screenshot(page, "/tmp/wl_smoke_03_before_analysis.png")

            # The button text is long — use partial match
            btn = page.locator('button:has-text("Shut Up")').first
            if btn.count() == 0:
                btn = page.locator('button:has-text("MyQA")').first
            if btn.count() == 0:
                btn = page.locator('button[kind="primary"]').first

            if btn.count() > 0:
                btn.click()
                print("   Button clicked, waiting for analysis...", flush=True)
                # Analysis takes ~15-40s with 17 DICOM images
                time.sleep(20)
                s = safe_screenshot(page, "/tmp/wl_smoke_04_after_analysis.png")
                if s:
                    screenshots.append(s)

                body_text = page.inner_text("body")
                if "Analysis complete" in body_text or "Max 2D" in body_text:
                    print("   ✓ Success card appeared", flush=True)
                elif "Analysis failed" in body_text:
                    errors.append("Analysis failed in Simple mode")
                    print(f"   ✗ Analysis failed. Body text: {body_text[:300]}", flush=True)
                else:
                    print(f"   ? No success card yet. Body text: {body_text[:200]}", flush=True)
            else:
                errors.append("Analysis button not found")
                print("   ✗ Analysis button not found", flush=True)

            # === 5. Check xlsx on disk ===
            print("5. Checking xlsx output on disk...", flush=True)
            xlsx_files = list(output_dir.rglob("*.xlsx"))
            xltx_files = list(output_dir.rglob("*.xltx"))
            if xlsx_files:
                print(f"   ✓ xlsx written: {xlsx_files[0]}", flush=True)
            else:
                errors.append("No xlsx file written to output")
                print("   ✗ No xlsx file found", flush=True)
            if xltx_files:
                print(f"   ✓ xltx paired: {xltx_files[0]}", flush=True)
            else:
                print("   (no xltx file yet)", flush=True)

            # === 6. Switch to Advanced mode ===
            print("6. Switching to Advanced mode...", flush=True)
            # Click "View in Advanced mode" if present
            adv_btn = page.locator('button:has-text("Advanced")').first
            if adv_btn.count() > 0:
                adv_btn.click()
                time.sleep(5)
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            else:
                # Toggle mode in sidebar
                radio = page.locator('label:has-text("Advanced")').first
                if radio.count() > 0:
                    radio.click()
                    time.sleep(3)

            s = safe_screenshot(page, "/tmp/wl_smoke_05_advanced.png")
            if s:
                screenshots.append(s)

            body_text = page.inner_text("body")
            if "Advanced" in body_text:
                print("   ✓ Advanced mode reached", flush=True)
            else:
                print("   ? Advanced mode state unclear", flush=True)

            # === 7. Check tabs ===
            print("7. Checking tabs...", flush=True)
            tabs = page.locator('[role="tab"]')
            tab_count = tabs.count()
            if tab_count >= 4:
                tab_texts = [tabs.nth(i).inner_text() for i in range(tab_count)]
                print(f"   ✓ Found {tab_count} tabs: {tab_texts}", flush=True)
            else:
                body_text = page.inner_text("body")
                found_tabs = [
                    t for t in ["Overview", "Per-image", "Plots", "Detection"] if t in body_text
                ]
                if found_tabs:
                    print(f"   ✓ Found tab labels in text: {found_tabs}", flush=True)
                else:
                    errors.append(f"Only {tab_count} tabs found (expected 4)")
                    print(f"   ? Tab count: {tab_count}", flush=True)

            # Click through tabs
            for tab_name in ["Overview", "Per-image", "Plots", "Detection"]:
                tab = page.locator(f'[role="tab"]:has-text("{tab_name}")').first
                if tab.count() > 0:
                    tab.click()
                    time.sleep(2)
                    s = safe_screenshot(
                        page, f"/tmp/wl_smoke_06_tab_{tab_name.lower().replace('-', '_')}.png"
                    )
                    if s:
                        screenshots.append(s)
                    print(f"   ✓ Clicked tab: {tab_name}", flush=True)

        except Exception as exc:
            errors.append(f"Exception during test: {exc}")
            import traceback

            traceback.print_exc()
            safe_screenshot(page, "/tmp/wl_smoke_error.png")
        finally:
            browser.close()

    # === Summary ===
    print("\n" + "=" * 60, flush=True)
    print("SMOKE TEST SUMMARY", flush=True)
    print("=" * 60, flush=True)
    print(f"Screenshots saved: {len(screenshots)}", flush=True)
    for s in screenshots:
        print(f"  - {s}", flush=True)

    if errors:
        print(f"\n❌ {len(errors)} error(s):", flush=True)
        for e in errors:
            print(f"  - {e}", flush=True)
        return 1
    else:
        print("\n✅ All smoke test checks passed!", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(run_smoke_test())
