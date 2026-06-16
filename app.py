"""Streamlit entry point — home page + startup validation.

On first render:
    1. Configure logging to stdout (9.4)
    2. Load ``machines.yaml`` (2.2)
    3. Validate the xltx template (2.3)
    4. Probe ``output.root`` writability (via load_config)

If any check fails, the app displays the specific failure and refuses to
render the module selector / page links.

The Fry meme (machine-config R5) renders via ``render_asset`` (6.0).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import streamlit as st

from core.config import (
    ConfigError,
    configure_logging,
    load_config,
    validate_catphan_template,
    validate_template,
)
from core.ui_utils import render_asset

logger = logging.getLogger(__name__)

#: Default config path: env var → ``machines.yaml`` next to this script.
DEFAULT_CONFIG_PATH = os.environ.get("WL_CONFIG_PATH", "machines.yaml")

#: Default template paths.
DEFAULT_TEMPLATE_PATH = "templates/winston_lutz.xltx"
DEFAULT_CATPHAN_TEMPLATE_PATH = "templates/catphan_504.xltx"


def main() -> None:
    configure_logging()
    st.set_page_config(
        page_title="WL QA",
        page_icon=":radiation:",
        layout="wide",
    )

    config_path = Path(DEFAULT_CONFIG_PATH)
    template_path = Path(DEFAULT_TEMPLATE_PATH)
    catphan_template_path = Path(DEFAULT_CATPHAN_TEMPLATE_PATH)

    # --- Startup checks ---
    try:
        config = load_config(config_path)
        validate_template(template_path)
        # CatPhan template is only required if any machine has catphan configured
        if config.has_catphan():
            validate_catphan_template(catphan_template_path)
    except ConfigError as exc:
        st.error(f"**Startup check failed:** {exc}")
        st.info(
            "The app cannot start until this is resolved.\n\n"
            "Common causes:\n"
            "- ``machines.yaml`` missing or invalid (copy from ``machines.yaml.example``)\n"
            "- DICOM root or output root not mounted (check ``docker-compose.yml`` volumes)\n"
            "- xltx template missing required defined names "
            "(run ``scripts/build_xltx_template.py`` or ``scripts/build_catphan_xltx_template.py``)"
        )
        return

    # --- Home page ---
    st.title("WSLHD Winston-Lutz QA")
    st.write("Web GUI for pylinac Winston-Lutz analysis → MyQA-ready xlsx output.")

    # Fry meme (D10, machine-config R5)
    render_asset(
        config.assets.fry_meme_path,
        placeholder_msg=f"Drop a meme image at: {config.assets.fry_meme_path}",
    )

    # Module selector (static for v1)
    st.subheader("Modules")
    st.write("• **Winston-Lutz** — available (see the Winston-Lutz page in the sidebar)")
    if config.has_catphan():
        st.write("• **CatPhan 504** — available (see the CatPhan page in the sidebar)")
    else:
        st.write("• CatPhan — *not configured (add ``catphan:`` to machines.yaml to enable)*")
    st.write("• Field Profile, Trajectory Log — *coming soon*")

    # Cache config + template path in session_state for pages
    st.session_state["wl_config"] = config
    st.session_state["wl_template_path"] = str(template_path)
    st.session_state["cp_template_path"] = str(catphan_template_path)


if __name__ == "__main__":
    main()
