"""UI utility functions shared across pages."""

from __future__ import annotations

import logging
from pathlib import Path

import streamlit as st

logger = logging.getLogger(__name__)


def render_asset(path: str | Path, placeholder_msg: str) -> None:
    """Render an image asset, or a placeholder info banner if missing.

    Used for the Fry meme (machine-config R5) and future logo.

    Args:
        path: Path to the image file (container path).
        placeholder_msg: Message to display if the file doesn't exist.
    """
    p = Path(path)
    if p.exists():
        st.image(str(p))
    else:
        st.info(placeholder_msg)


def render_mode_toggle() -> str:
    """Render the sidebar mode toggle (Simple | Advanced).

    Defaults to Simple. Persisted in ``st.session_state["mode"]``.

    To programmatically switch modes (e.g. from a button in another part of
    the page), set ``st.session_state["wl_mode_switch"]`` to the target mode
    and call ``st.rerun()``. This function checks for that pending request
    **before** the radio widget renders, avoiding Streamlit's
    ``StreamlitAPIException`` on widget-key mutation.

    Returns:
        The selected mode string (``"simple"`` or ``"advanced"``).
    """
    st.sidebar.title("WL QA")
    # Apply pending mode switch (set by buttons elsewhere in the page)
    pending = st.session_state.pop("wl_mode_switch", None)
    if pending is not None:
        st.session_state["mode"] = pending
    if "mode" not in st.session_state:
        st.session_state["mode"] = "simple"
    mode = st.sidebar.radio(
        "Mode",
        options=["simple", "advanced"],
        format_func=lambda m: "Simple" if m == "simple" else "Advanced",
        key="mode",
    )
    return mode


__all__ = ["render_asset", "render_mode_toggle"]
