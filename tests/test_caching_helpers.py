"""Tests for the session-state caching helpers (``core/caching.py``).

Task 1.4b — verifies:
- ``init_session_state("cp", ...)`` produces key ``cp_result``
- ``invalidate("cp")`` clears ``cp_result``/``cp_obj``/``cp_params`` but not ``wl_result``
- ``get_cached_obj("wl")`` returns the WL obj or ``None``
"""

from __future__ import annotations

import pytest
import streamlit as st
from streamlit.runtime.state import SessionStateProxy


@pytest.fixture
def _clear_session_state(monkeypatch: pytest.MonkeyPatch) -> SessionStateProxy:
    """Provide an empty session_state for each test.

    ``st.session_state`` is a process-wide singleton proxy; we clear known
    keys before and after each test to keep them isolated.
    """
    for key in [
        "cp_result",
        "cp_obj",
        "cp_params",
        "wl_result",
        "wl_obj",
        "wl_params",
    ]:
        st.session_state.pop(key, None)
    yield st.session_state
    for key in [
        "cp_result",
        "cp_obj",
        "cp_params",
        "wl_result",
        "wl_obj",
        "wl_params",
    ]:
        st.session_state.pop(key, None)


def test_init_session_state_creates_cp_result(_clear_session_state: object) -> None:
    """``init_session_state("cp", ...)`` produces key ``cp_result``."""
    from core.caching import init_session_state

    init_session_state("cp", {"result": None, "obj": None, "params": {}})
    assert "cp_result" in st.session_state
    assert "cp_obj" in st.session_state
    assert "cp_params" in st.session_state
    assert st.session_state["cp_result"] is None
    assert st.session_state["cp_params"] == {}


def test_invalidate_cp_clears_cp_but_not_wl(_clear_session_state: object) -> None:
    """``invalidate("cp")`` clears cp_* keys but leaves wl_* keys intact."""
    from core.caching import invalidate

    st.session_state["cp_result"] = {"x": 1}
    st.session_state["cp_obj"] = "cp_obj_val"
    st.session_state["cp_params"] = {"hu_tolerance": 40}
    st.session_state["wl_result"] = {"y": 2}
    st.session_state["wl_obj"] = "wl_obj_val"
    st.session_state["wl_params"] = {"bb_size_mm": 5.0}

    invalidate("cp")

    assert "cp_result" not in st.session_state
    assert "cp_obj" not in st.session_state
    assert "cp_params" not in st.session_state
    # WL keys must survive
    assert st.session_state["wl_result"] == {"y": 2}
    assert st.session_state["wl_obj"] == "wl_obj_val"
    assert st.session_state["wl_params"] == {"bb_size_mm": 5.0}


def test_get_cached_obj_wl_returns_obj_or_none(_clear_session_state: object) -> None:
    """``get_cached_obj("wl")`` returns the WL obj when set, else None."""
    from core.caching import get_cached_obj

    # Before being set
    assert get_cached_obj("wl") is None

    # After being set
    sentinel = object()
    st.session_state["wl_obj"] = sentinel
    assert get_cached_obj("wl") is sentinel


def test_init_session_state_does_not_overwrite_existing(_clear_session_state: object) -> None:
    """``init_session_state`` must not clobber an existing value."""
    from core.caching import init_session_state

    st.session_state["cp_result"] = "pre_existing"
    init_session_state("cp", {"result": None})
    assert st.session_state["cp_result"] == "pre_existing"


def test_invalidate_subset_only_clears_specified_suffixes(_clear_session_state: object) -> None:
    """``invalidate("wl", suffixes=("obj",))`` clears only wl_obj."""
    from core.caching import invalidate

    st.session_state["wl_result"] = "keep"
    st.session_state["wl_obj"] = "clear_me"
    st.session_state["wl_params"] = "keep_too"

    invalidate("wl", suffixes=("obj",))

    assert st.session_state["wl_result"] == "keep"
    assert "wl_obj" not in st.session_state
    assert st.session_state["wl_params"] == "keep_too"


def test_set_and_get_cached_result(_clear_session_state: object) -> None:
    """``set_cached_result`` / ``get_cached_result`` round-trip."""
    from core.caching import get_cached_result, set_cached_result

    payload = {"machine": "LA2", "passed": True}
    set_cached_result("cp", payload)
    assert get_cached_result("cp") is payload
