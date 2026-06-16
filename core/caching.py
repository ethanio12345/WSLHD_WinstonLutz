"""Session-state caching lifecycle helpers shared across module pages.

Extracted as a new thin abstraction (design D1) so that the WL and CatPhan
pages share a consistent ``st.session_state`` key-naming convention.

Each module uses a short prefix (``"wl"`` or ``"cp"``) to namespace three
session-state keys:

    - ``<prefix>_result`` — the analysis result dataclass (hand-off payload)
    - ``<prefix>_obj``    — the live pylinac object (lazy-init, not picklable)
    - ``<prefix>_params`` — the current sidebar parameters

Public API:
    - :data:`RESULT_SUFFIX`
    - :data:`OBJ_SUFFIX`
    - :data:`PARAMS_SUFFIX`
    - :func:`init_session_state`
    - :func:`get_cached_result`
    - :func:`get_cached_obj`
    - :func:`get_cached_params`
    - :func:`set_cached_result`
    - :func:`set_cached_obj`
    - :func:`invalidate`
"""

from __future__ import annotations

from typing import Any

import streamlit as st

#: Session-state key suffixes (combined with a short module prefix).
RESULT_SUFFIX = "result"
OBJ_SUFFIX = "obj"
PARAMS_SUFFIX = "params"

#: The three managed suffixes per module prefix.
_MANAGED_SUFFIXES: tuple[str, ...] = (RESULT_SUFFIX, OBJ_SUFFIX, PARAMS_SUFFIX)


def _key(prefix: str, suffix: str) -> str:
    """Build a session-state key from a short prefix and a suffix.

    e.g. ``("wl", "result") -> "wl_result"``
    """
    return f"{prefix}_{suffix}"


def init_session_state(prefix: str, defaults: dict[str, Any]) -> None:
    """Initialise session-state keys for ``prefix`` if not already present.

    Args:
        prefix: Short module prefix (e.g. ``"wl"`` or ``"cp"``).
        defaults: Mapping of suffix → default value. Only suffixes present in
            ``defaults`` are initialised. Common suffixes: ``"result"``,
            ``"obj"``, ``"params"``.
    """
    for suffix, default in defaults.items():
        key = _key(prefix, suffix)
        if key not in st.session_state:
            st.session_state[key] = default


def get_cached_result(prefix: str) -> Any:
    """Return the cached analysis result for ``prefix``, or ``None``."""
    return st.session_state.get(_key(prefix, RESULT_SUFFIX))


def get_cached_obj(prefix: str) -> Any:
    """Return the cached live pylinac object for ``prefix``, or ``None``."""
    return st.session_state.get(_key(prefix, OBJ_SUFFIX))


def get_cached_params(prefix: str) -> Any:
    """Return the cached sidebar parameters for ``prefix``, or ``None``."""
    return st.session_state.get(_key(prefix, PARAMS_SUFFIX))


def set_cached_result(prefix: str, value: Any) -> None:
    """Set the cached analysis result for ``prefix``."""
    st.session_state[_key(prefix, RESULT_SUFFIX)] = value


def set_cached_obj(prefix: str, value: Any) -> None:
    """Set the cached live pylinac object for ``prefix``."""
    st.session_state[_key(prefix, OBJ_SUFFIX)] = value


def invalidate(prefix: str, suffixes: tuple[str, ...] | None = None) -> None:
    """Invalidate (pop) session-state keys for ``prefix``.

    By default clears all three managed keys (``result``, ``obj``, ``params``).
    Pass ``suffixes`` to clear a subset (e.g. ``("obj",)`` to clear only the
    live object).

    Args:
        prefix: Short module prefix (e.g. ``"wl"`` or ``"cp"``).
        suffixes: Optional tuple of suffixes to clear; defaults to all three.
    """
    targets = suffixes if suffixes is not None else _MANAGED_SUFFIXES
    for suffix in targets:
        st.session_state.pop(_key(prefix, suffix), None)


__all__ = [
    "OBJ_SUFFIX",
    "PARAMS_SUFFIX",
    "RESULT_SUFFIX",
    "get_cached_obj",
    "get_cached_params",
    "get_cached_result",
    "init_session_state",
    "invalidate",
    "set_cached_obj",
    "set_cached_result",
]
