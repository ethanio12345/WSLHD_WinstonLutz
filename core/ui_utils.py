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

    Returns:
        The selected mode string (``"simple"`` or ``"advanced"``).
    """
    st.sidebar.title("WL QA")
    mode = st.sidebar.radio(
        "Mode",
        options=["simple", "advanced"],
        format_func=lambda m: "Simple" if m == "simple" else "Advanced",
        index=0 if st.session_state.get("mode", "simple") == "simple" else 1,
        key="mode",
    )
    return mode


__all__ = ["render_asset", "render_mode_toggle"]
