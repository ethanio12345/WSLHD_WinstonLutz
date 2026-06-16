"""End-to-end browser test fixtures for the Streamlit app.

Manages:
- A Streamlit server running on a random port (session-scoped)
- Synthetic WL DICOMs + CatPhan demo DICOMs (session-scoped)
- A test machines.yaml pointing at both data sets
- A fresh Playwright browser page per test (function-scoped)
"""

from __future__ import annotations

import socket
import time
import warnings
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import yaml
from playwright.sync_api import Browser, Page, sync_playwright

# ---------------------------------------------------------------------------
# Port helpers
# ---------------------------------------------------------------------------


def _free_port() -> int:
    """Return a free TCP port for the Streamlit server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(url: str, timeout: float = 60) -> None:
    """Wait until the Streamlit server responds at ``url``."""
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"Streamlit server did not start within {timeout}s at {url}")


# ---------------------------------------------------------------------------
# Test data fixtures (session-scoped — set up once)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def wl_runfolder(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate synthetic Winston-Lutz DICOMs for testing."""
    runfolder = tmp_path_factory.mktemp("wl_data") / "LA2" / "WinstonLutz" / "demo_clinical"
    runfolder.mkdir(parents=True)
    try:
        from pylinac.core.image_generator import (
            AS500Image,
            FilteredFieldLayer,
            GaussianFilterLayer,
            generate_winstonlutz,
        )

        generate_winstonlutz(
            simulator=AS500Image(),
            field_layer=FilteredFieldLayer,
            dir_out=str(runfolder),
            field_size_mm=(30, 30),
            final_layers=[GaussianFilterLayer(sigma_mm=2)],
            bb_size_mm=5,
            image_axes=((0, 0, 0), (90, 0, 0), (180, 0, 0), (270, 0, 0)),
        )
    except ImportError:
        pytest.skip("pylinac image_generator not available")
    return runfolder


@pytest.fixture(scope="session")
def catphan_runfolder(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Write CatPhan 504 demo DICOMs for testing."""
    runfolder = tmp_path_factory.mktemp("cp_data") / "LA2" / "CatPhan" / "2026-06-16_monthly"
    runfolder.mkdir(parents=True)
    from pylinac import CatPhan504

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        cbct = CatPhan504.from_demo_images()
    for i, img in enumerate(cbct.dicom_stack):
        img.save(str(runfolder / f"image_{i:04d}.dcm"))
    return runfolder


@pytest.fixture(scope="session")
def test_config(
    wl_runfolder: Path,
    catphan_runfolder: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, Any]:
    """Build a machines.yaml config dict pointing at test data."""
    output_root = tmp_path_factory.mktemp("output")
    return {
        "machines": {
            "LA2": {
                "display_name": "LA2 (TrueBeam)",
                "dicom_roots": {
                    "winston_lutz": str(wl_runfolder.parent),
                    "catphan": str(catphan_runfolder.parent),
                },
                "output_root": str(output_root),
            }
        },
        "analysis_defaults": {
            "winston_lutz": {
                "bb_size_mm": 5.0,
                "machine_scale": "VARIAN_IEC",
                "tolerance_mm": 1.0,
            },
            "catphan": {
                "hu_tolerance": 40,
                "scaling_tolerance": 0.5,
                "slice_thickness_tolerance": 0.5,
            },
        },
        "assets": {
            "fry_meme_path": str(Path(__file__).resolve().parents[2] / "assets" / "fry_money.png"),
            "logo_path": str(Path(__file__).resolve().parents[2] / "assets" / "fry_money.png"),
        },
    }


@pytest.fixture(scope="session")
def output_root(
    test_config: dict[str, Any],
) -> Path:
    """Expose the output root directory for file-existence checks."""
    return Path(test_config["machines"]["LA2"]["output_root"])


@pytest.fixture(scope="session")
def config_path(
    test_config: dict[str, Any],
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """Write the test machines.yaml and return its path."""
    config_dir = tmp_path_factory.mktemp("config")
    path = config_dir / "machines.yaml"
    path.write_text(yaml.dump(test_config), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Streamlit server fixture (session-scoped)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def streamlit_server(
    config_path: Path,
) -> Generator[tuple[str, int], None, None]:
    """Start a headless Streamlit server and yield (base_url, port).

    The server uses the test ``machines.yaml`` via ``WL_CONFIG_PATH``.
    """
    import os
    import subprocess

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
        time.sleep(3)  # extra settle time for Streamlit initial render
        yield (base_url, port)
    finally:
        proc.terminate()
        proc.wait(timeout=10)


# ---------------------------------------------------------------------------
# Playwright browser fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def browser() -> Generator[Browser, None, None]:
    """Launch a Chromium browser for the test session."""
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True)
        yield br
        br.close()


@pytest.fixture
def page(browser: Browser, streamlit_server: tuple[str, int]) -> Generator[Page, None, None]:
    """Provide a fresh browser page connected to the Streamlit server."""
    base_url, _ = streamlit_server
    context = browser.new_context()
    pg = context.new_page()
    pg.goto(base_url, wait_until="networkidle")
    # Wait for Streamlit to finish initial render
    pg.wait_for_selector("[data-testid='stAppViewContainer']", timeout=30000)
    time.sleep(2)
    yield pg
    context.close()


def _click_sidebar_nav(page: Page, page_name: str) -> None:
    """Click a sidebar navigation link matching ``page_name``.

    Streamlit multipage apps list pages in the sidebar as ``<a>`` links.
    We find the one whose text contains ``page_name`` and click it.
    """
    sidebar = page.query_selector("[data-testid='stSidebar']")
    if sidebar is None:
        raise RuntimeError("Sidebar not found — Streamlit may not have rendered yet")

    links = sidebar.query_selector_all("a")
    for link in links:
        text = (link.text_content() or "").strip()
        if page_name.lower() in text.lower():
            link.click()
            return

    # Fallback: try [data-testid='stSidebarNavLink'] selectors
    nav_links = page.query_selector_all("[data-testid='stSidebarNavLink'] span")
    for link in nav_links:
        text = (link.text_content() or "").strip()
        if page_name.lower() in text.lower():
            link.click()
            return

    raise RuntimeError(f"Could not find sidebar nav link for '{page_name}'")


@pytest.fixture
def wl_page(page: Page) -> Page:
    """Navigate to the Winston-Lutz page via sidebar (after home page establishes session_state)."""
    _click_sidebar_nav(page, "Winston")
    page.wait_for_load_state("networkidle")
    time.sleep(3)
    return page


@pytest.fixture
def catphan_page(page: Page) -> Page:
    """Navigate to the CatPhan page via sidebar."""
    _click_sidebar_nav(page, "CatPhan")
    page.wait_for_load_state("networkidle")
    time.sleep(3)
    return page
