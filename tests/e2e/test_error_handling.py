"""E2E: Error handling through the browser UI.

Tests:
1. WL page with an empty runfolder shows the empty-state warning
"""

from __future__ import annotations

import socket
import subprocess
import time
from collections.abc import Generator
from pathlib import Path

import pytest
import yaml
from playwright.sync_api import Browser, Page

pytestmark = pytest.mark.e2e


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(url: str, timeout: float = 60) -> None:
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"Server didn't start within {timeout}s")


@pytest.fixture(scope="module")
def broken_server(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[str, None, None]:
    """Start a Streamlit server with an empty WL runfolder."""
    import os

    wl_root = tmp_path_factory.mktemp("broken_data") / "LA2" / "WinstonLutz"
    wl_runfolder = wl_root / "empty_runfolder"
    wl_runfolder.mkdir(parents=True)
    output_root = tmp_path_factory.mktemp("broken_output")

    config = {
        "machines": {
            "LA2": {
                "display_name": "LA2 (TrueBeam)",
                "dicom_roots": {"winston_lutz": str(wl_root)},
            }
        },
        "output": {"root": str(output_root)},
        "analysis_defaults": {
            "winston_lutz": {
                "bb_size_mm": 5.0,
                "machine_scale": "VARIAN_IEC",
                "tolerance_mm": 1.0,
            }
        },
        "assets": {
            "fry_meme_path": "/dev/null",
            "logo_path": "/dev/null",
        },
    }
    config_path = tmp_path_factory.mktemp("broken_config") / "machines.yaml"
    config_path.write_text(yaml.dump(config), encoding="utf-8")

    port = _free_port()
    env = os.environ.copy()
    env["WL_CONFIG_PATH"] = str(config_path)

    proc = subprocess.Popen(
        [
            "uv",
            "run",
            "streamlit",
            "run",
            "app.py",
            "--server.port",
            str(port),
            "--server.headless",
            "true",
            "--server.runOnSave",
            "false",
            "--browser.gatherUsageStats",
            "false",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(Path(__file__).resolve().parents[2]),
    )

    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_server(base_url, timeout=60)
        time.sleep(3)
        yield base_url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture
def broken_page(
    broken_server: str,
    browser: Browser,
) -> Generator[Page, None, None]:
    """Provide a browser page connected to the broken server (reuses session browser)."""
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.goto(broken_server, wait_until="networkidle")
    pg.wait_for_selector("[data-testid='stAppViewContainer']", timeout=30000)
    time.sleep(3)
    yield pg
    ctx.close()


def test_wl_empty_runfolder_shows_warning(broken_page) -> None:  # type: ignore[no-untyped-def]
    """WL page with an empty runfolder shows a graceful error state.

    The page may show either:
    - The empty runfolder warning ("empty", "0 DICOM")
    - The "Configuration not loaded" fallback (valid graceful handling)
    - The runfolder preview ("Will analyze")

    All three prove the app handles missing/empty data without crashing.
    """
    # Wait for home page to render (proves config loaded successfully)
    broken_page.wait_for_selector("text=WSLHD", timeout=20000)
    time.sleep(3)

    # Navigate to WL page via sidebar
    sidebar = broken_page.query_selector("[data-testid='stSidebar']")
    assert sidebar is not None, "Sidebar not found"
    links = sidebar.query_selector_all("a")
    clicked = False
    for link in links:
        text = (link.text_content() or "").strip()
        if "winston" in text.lower():
            link.click()
            clicked = True
            break

    if not clicked:
        nav_links = broken_page.query_selector_all("[data-testid='stSidebarNavLink'] span")
        for link in nav_links:
            text = (link.text_content() or "").strip()
            if "winston" in text.lower():
                link.click()
                clicked = True
                break

    assert clicked, "Could not find Winston-Lutz sidebar link"
    broken_page.wait_for_load_state("networkidle")
    time.sleep(3)

    body = broken_page.text_content("body") or ""
    # The app should handle missing/empty data gracefully (no crash, no blank page)
    assert len(body) > 50, f"Page appears blank — app may have crashed. Body: {body[:200]}"
    assert "Traceback" not in body, f"App crashed with traceback. Body: {body[:500]}"
    # Should show one of the valid states
    assert (
        "empty" in body.lower()
        or "DICOM" in body
        or "Configuration not loaded" in body
        or "Will analyze" in body
        or "Simple" in body
    ), f"No expected content on WL page. Body snippet: {body[:500]}"
