"""Field Profile QA page — renders Simple or Advanced mode per sidebar toggle.

Implements:
    - fp-simple-mode spec (Simple mode: cascading folder browser, image dropdown,
      one-click analysis, FFF auto-detection, success card, hand-off)
    - fp-advanced-mode spec (Advanced mode: sidebar params + FFF override,
      4 tabs (Overview, Profiles, Field Map, ROI & Penumbra), re-run, download,
      lazy fp_obj, full inline errors)

The page is a **general-purpose standalone tool** (decoupled from per-machine
config — see ``generalize-field-profile-browser`` change). The physicist
navigates to any RT image folder via a cascading selectbox browser rooted at
``config.fp_browse_root`` (default ``/data``).
"""

from __future__ import annotations

import logging
from pathlib import Path

import streamlit as st

from core.caching import (
    get_cached_obj,
    get_cached_result,
    invalidate,
    set_cached_obj,
    set_cached_result,
)
from core.config import AppConfig, FieldProfileDefaults
from core.fp_excel_writer import build_fp_xlsx_bytes
from core.fp_runner import (
    extract_dicom_info,
    load_fp_object,
    run_fp_analysis,
)
from core.result_types import FieldAnalysisResult
from core.ui_utils import render_mode_toggle

logger = logging.getLogger(__name__)

#: Session-state prefix for this module.
_PREFIX = "fp"

#: Session-state key for the cascading folder browser path (list of components).
_BROWSER_PATH_KEY = "fp_browser_path"

#: Default FieldProfileDefaults used when ``analysis_defaults.field_profile``
#: is absent (decoupled page falls back to protocol: VARIAN + pylinac defaults).
_DEFAULT_FP_DEFAULTS = FieldProfileDefaults(protocol="VARIAN")


def render(config: AppConfig, template_path: Path) -> None:
    """Render the Field Profile page (entry point called by the page script)."""
    mode = render_mode_toggle()

    if mode == "simple":
        _render_simple(config, template_path)
    else:
        _render_advanced(config, template_path)


# ---------------------------------------------------------------------------
# Cached wrapper (same pattern as CatPhan page's run_cbct_analysis_cached)
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner="Running Field Profile analysis...")
def run_fp_analysis_cached(**kwargs):  # type: ignore[no-untyped-def]
    """Cached wrapper around run_fp_analysis.

    The ``@st.cache_data`` decorator caches based on ALL arguments (which
    include ``machine_id``, ``image_path``, all analyze params).
    """
    return run_fp_analysis(**kwargs)


# ---------------------------------------------------------------------------
# Helpers — cascading folder browser (design D1)
# ---------------------------------------------------------------------------


def _list_subdirs(folder: Path) -> list[Path]:
    """Return immediate subdirectories of ``folder``, sorted by name.

    Files are never listed. Returns an empty list if ``folder`` does not
    exist or contains no subdirectories.
    """
    if not folder.exists() or not folder.is_dir():
        return []
    return sorted((p for p in folder.iterdir() if p.is_dir()), key=lambda p: p.name)


def _list_dicom_images(folder: Path) -> list[Path]:
    """List DICOM files in ``folder``, sorted by name."""
    if not folder.exists():
        return []
    images: list[Path] = []
    for pattern in ("*.dcm", "*.dicom", "*.DCM"):
        images.extend(folder.glob(pattern))
    return sorted(set(images), key=lambda p: p.name)


def _build_image_label(image_path: Path) -> tuple[str, dict]:
    """Build the dropdown label for an image, returning (label, dicom_info).

    Delegates to :func:`core.fp_runner.extract_dicom_info` for the metadata
    display string. Missing tags render as ``"?"`` — no crash (fp-simple-mode
    spec: DICOM metadata missing).
    """
    try:
        info = extract_dicom_info(image_path)
        return info["display_string"], info
    except Exception:
        logger.exception("Failed to extract DICOM info for %s", image_path)
        return f"?  ?  ?  ?  ({image_path.name})", {
            "display_string": f"?  ?  ?  ?  ({image_path.name})",
            "is_fff": False,
            "filename": image_path.name,
        }


def _resolve_browse_root(browse_root_str: str) -> Path | None:
    """Resolve the configured browse_root, returning None + showing a message if invalid.

    Handles empty/non-existent browse_root with an inline info message (no crash),
    per spec scenario "browse_root missing or empty".
    """
    browse_root = Path(browse_root_str)
    if not browse_root.exists():
        st.info(
            f"Field Profile browse root `{browse_root_str}` does not exist. "
            "Set `field_profile.browse_root` in machines.yaml to a mounted DICOM share."
        )
        return None
    if not browse_root.is_dir():
        st.info(f"Field Profile browse root `{browse_root_str}` is not a directory.")
        return None
    return browse_root


def render_folder_browser(browse_root: Path) -> Path | None:
    """Render cascading selectboxes for navigating folders under ``browse_root``.

    Sandboxed to ``browse_root`` — there is no affordance to navigate above it
    (no ``..``, no absolute-path entry). Each selectbox lists immediate
    subdirectories (sorted by name); files are never listed. Changing a
    higher-level selectbox truncates the deeper levels (re-branches).

    Persists the selected path components in ``st.session_state["fp_browser_path"]``
    and returns the currently-selected folder (the deepest selected folder,
    which may be ``browse_root`` itself if no subdirs have been chosen).

    Args:
        browse_root: The root directory the browser is sandboxed to.

    Returns:
        The currently-selected folder path, or ``None`` if ``browse_root``
        is empty (contains no subdirectories and no DICOMs).
    """
    # Recover the persisted path components (list of subdir names under browse_root)
    components: list[str] = list(st.session_state.get(_BROWSER_PATH_KEY, []))

    # Filter out persisted components that no longer exist on disk
    valid_components: list[str] = []
    current = browse_root
    for comp in components:
        candidate = current / comp
        if candidate.exists() and candidate.is_dir():
            valid_components.append(comp)
            current = candidate
        else:
            break  # a parent was removed/renamed; truncate here
    components = valid_components
    st.session_state[_BROWSER_PATH_KEY] = components

    # Render cascading selectboxes level-by-level
    current_folder = browse_root
    level = 0
    while True:
        subdirs = _list_subdirs(current_folder)
        if not subdirs:
            break  # no deeper level to render

        options = ["(none)"] + [p.name for p in subdirs]
        # Pre-select the persisted component for this level, if any
        current_selection = components[level] if level < len(components) else "(none)"
        try:
            index = options.index(current_selection)
        except ValueError:
            index = 0  # "(none)"

        selected = st.sidebar.selectbox(
            f"Folder (level {level + 1})" if level > 0 else "Folder",
            options=options,
            index=index,
            key=f"{_PREFIX}_browser_level_{level}",
        )

        if selected == "(none)":
            # Truncate any deeper persisted components
            if level < len(components):
                components = components[:level]
                st.session_state[_BROWSER_PATH_KEY] = components
            break

        # Persist / update the component at this level
        if level < len(components):
            if components[level] != selected:
                # Re-branch: truncate deeper levels
                components = [*components[:level], selected]
                st.session_state[_BROWSER_PATH_KEY] = components
        else:
            components.append(selected)
            st.session_state[_BROWSER_PATH_KEY] = components

        current_folder = current_folder / selected
        level += 1

    return current_folder


# ---------------------------------------------------------------------------
# Shared FP defaults accessor (page uses the optional accessor)
# ---------------------------------------------------------------------------


def _get_fp_defaults(config: AppConfig) -> FieldProfileDefaults:
    """Return the centre-wide FP defaults, or the VARIAN default if absent."""
    return config.fp_defaults_or_none or _DEFAULT_FP_DEFAULTS


# ---------------------------------------------------------------------------
# Simple mode
# ---------------------------------------------------------------------------


def _render_simple(config: AppConfig, template_path: Path) -> None:
    """Simple mode: folder browser → image → one-click analysis."""
    st.header("Field Profile — Simple Mode")

    # Cascading folder browser (rooted at config.fp_browse_root)
    browse_root = _resolve_browse_root(config.fp_browse_root)
    if browse_root is None:
        return

    folder = render_folder_browser(browse_root)

    # Image dropdown with DICOM metadata display
    image_path, dicom_info = _render_image_dropdown(folder)
    if image_path is None:
        return

    # FFF detection display
    is_fff = bool(dicom_info.get("is_fff", False))
    st.info(f"**FFF detected:** {'Yes' if is_fff else 'No'}")

    # One-click analysis button
    if st.button("Shut Up and Give Me My MyQA Results", type="primary"):
        _run_simple_analysis(
            config=config,
            template_path=template_path,
            folder=folder,
            image_path=image_path,
            image_display_name=dicom_info["display_string"],
        )

    # If we have a cached result from a previous run this session, show the card
    cached = get_cached_result(_PREFIX)
    if cached is not None:
        _render_success_card(
            result=cached,
            template_path=template_path,
        )


def _run_simple_analysis(
    *,
    config: AppConfig,
    template_path: Path,
    folder: Path,
    image_path: Path,
    image_display_name: str,
) -> None:
    """Execute Simple-mode analysis with error wrapping (5.5).

    No server-side file write — the result is shown in-browser and the xlsx
    is served via ``st.download_button`` in the success card.
    """
    fp_defaults = _get_fp_defaults(config)
    # Use the deepest folder name as the session identifier (decoupled from
    # machine config). This populates the ``machine_name`` MyQA metadata cell.
    session_id = folder.name or "field_profile"
    try:
        with st.spinner("Running Field Profile analysis..."):
            result = run_fp_analysis_cached(
                machine_id=session_id,
                image_path=str(image_path),
                image_display_name=image_display_name,
                protocol=fp_defaults.protocol,
                centering=fp_defaults.centering,
                vert_position=fp_defaults.vert_position,
                horiz_position=fp_defaults.horiz_position,
                vert_width=fp_defaults.vert_width,
                horiz_width=fp_defaults.horiz_width,
                in_field_ratio=fp_defaults.in_field_ratio,
                slope_exclusion_ratio=fp_defaults.slope_exclusion_ratio,
                is_FFF=None,  # auto-detect per image
                penumbra=fp_defaults.penumbra,
                interpolation=fp_defaults.interpolation,
                edge_detection_method=fp_defaults.edge_detection_method,
                edge_smoothing_ratio=fp_defaults.edge_smoothing_ratio,
                hill_window_ratio=fp_defaults.hill_window_ratio,
            )
        # Store in session state for success card + hand-off
        set_cached_result(_PREFIX, result)
        st.rerun()

    except Exception:
        logging.exception("Field Profile analysis failed in Simple mode")
        summary = _safe_error_message()
        st.error(f"Analysis failed: {summary}. Switch to Advanced mode to debug.")


def _render_image_dropdown(folder: Path) -> tuple[Path | None, dict]:
    """Image dropdown — list DICOMs in the selected folder with metadata display.

    Returns (selected_image_path, dicom_info_dict) or (None, {}) if no images.
    Handles empty selected folder with an inline info message (no crash),
    per spec scenario "browse_root missing or empty".
    """
    images = _list_dicom_images(folder)
    if not images:
        st.info(
            f"No DICOM images (``.dcm``/``.dicom``) found in `{folder}`. "
            "Navigate to a folder containing RT portal images."
        )
        return None, {}

    # Build labels (cached-friendly: rebuild each render is fine for tens of images)
    labels: list[str] = []
    infos: list[dict] = []
    for img in images:
        label, info = _build_image_label(img)
        labels.append(label)
        infos.append(info)

    selected_idx = st.sidebar.selectbox(
        "Image",
        options=range(len(images)),
        format_func=lambda i: labels[i],
        index=0,
        key=f"{_PREFIX}_image_select",
    )
    return images[selected_idx], infos[selected_idx]


def _render_success_card(
    *,
    result: FieldAnalysisResult,
    template_path: Path,
) -> None:
    """Success card with key metrics + download button + hand-off button.

    No server-side output path is shown (there is none). The xlsx is served
    in-browser via ``st.download_button``.
    """
    st.success("Analysis complete!")

    s = result.summary
    st.write(f"**Flatness Vertical (%):** {s.get('flatness_vertical', '?')}")
    st.write(f"**Flatness Horizontal (%):** {s.get('flatness_horizontal', '?')}")
    st.write(f"**Symmetry Vertical (%):** {s.get('symmetry_vertical', '?')}")
    st.write(f"**Symmetry Horizontal (%):** {s.get('symmetry_horizontal', '?')}")
    st.write(f"**Field Size Vertical (mm):** {s.get('field_size_vertical_mm', '?')}")
    st.write(f"**Field Size Horizontal (mm):** {s.get('field_size_horizontal_mm', '?')}")
    st.write(f"**FFF status:** {'Yes' if result.is_fff else 'No'}")

    # In-browser xlsx download (no server write). The file_name keys on the
    # image stem per fp-result-export spec.
    image_stem = Path(result.image_path).stem
    try:
        xlsx_bytes = build_fp_xlsx_bytes(result=result, template_path=template_path)
        st.download_button(
            label="Download xlsx",
            data=xlsx_bytes,
            file_name=f"{image_stem}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception:
        logging.exception("Failed to build Field Profile xlsx bytes for download")
        st.warning("Could not build the xlsx download. See the logs for details.")

    # Hand-off to Advanced mode
    if st.button("View in Advanced mode"):
        set_cached_result(_PREFIX, result)
        st.session_state["wl_mode_switch"] = "advanced"
        st.rerun()


def _safe_error_message() -> str:
    """Generate a one-line user-safe error summary (5.5)."""
    import sys

    exc_type, exc_value, _ = sys.exc_info()
    if exc_type is None:
        return "unknown error"
    type_name = exc_type.__name__
    msg = str(exc_value)
    if "DICOM" in msg or "dicom" in msg or "load" in msg.lower():
        return "could not read the DICOM image. Check the selected file."
    if "edge" in msg.lower() or "field" in msg.lower():
        return (
            "could not detect the field edges. Check image quality/positioning "
            "or switch to Advanced mode."
        )
    return f"{type_name}: {msg[:80]}"


# ---------------------------------------------------------------------------
# Advanced mode
# ---------------------------------------------------------------------------


def _render_advanced(config: AppConfig, template_path: Path) -> None:
    """Advanced mode: sidebar params + FFF override + 4 tabs."""
    st.header("Field Profile — Advanced Mode")

    # Hand-off reception: if fp_result is set, use it; don't re-run
    result: FieldAnalysisResult | None = get_cached_result(_PREFIX)

    if result is None:
        # No hand-off — need to run analysis first via sidebar
        st.info("No analysis result yet. Run analysis from the sidebar.")
        result = _advanced_initial_run(config, template_path)
        if result is None:
            return

    # Advanced sidebar with params + FFF override
    params = _render_advanced_sidebar(
        config=config,
        result=result,
    )

    # Re-run + download handlers
    col1, col2 = st.sidebar.columns(2)
    rerun_clicked = col1.button("Re-run analysis")
    download_clicked = col2.button("Download xlsx")

    if rerun_clicked:
        new_result = _handle_rerun(
            config=config,
            params=params,
            prev_result=result,
        )
        if new_result is not None:
            result = new_result

    if download_clicked:
        _handle_download(
            result=result,
            template_path=template_path,
        )

    # Render the 4 tabs
    tab_overview, tab_profiles, tab_field_map, tab_roi = st.tabs(
        ["Overview", "Profiles", "Field Map", "ROI & Penumbra"]
    )

    with tab_overview:
        _render_overview_tab(result)
    with tab_profiles:
        _render_profiles_tab(result)
    with tab_field_map:
        _render_field_map_tab(result)
    with tab_roi:
        _render_roi_tab(result)


def _advanced_initial_run(config: AppConfig, template_path: Path) -> FieldAnalysisResult | None:
    """Run an initial analysis from the sidebar if no hand-off result exists."""
    browse_root = _resolve_browse_root(config.fp_browse_root)
    if browse_root is None:
        return None

    folder = render_folder_browser(browse_root)

    image_path, dicom_info = _render_image_dropdown(folder)
    if image_path is None:
        return None

    st.info(
        f"**FFF detected:** {'Yes' if dicom_info.get('is_fff') else 'No'} — will analyse: `{image_path.name}`"
    )

    fp_defaults = _get_fp_defaults(config)
    session_id = folder.name or "field_profile"

    if st.sidebar.button("Run analysis", type="primary"):
        try:
            with st.spinner("Running Field Profile analysis..."):
                result = run_fp_analysis_cached(
                    machine_id=session_id,
                    image_path=str(image_path),
                    image_display_name=dicom_info["display_string"],
                    protocol=fp_defaults.protocol,
                    centering=fp_defaults.centering,
                    vert_position=fp_defaults.vert_position,
                    horiz_position=fp_defaults.horiz_position,
                    vert_width=fp_defaults.vert_width,
                    horiz_width=fp_defaults.horiz_width,
                    in_field_ratio=fp_defaults.in_field_ratio,
                    slope_exclusion_ratio=fp_defaults.slope_exclusion_ratio,
                    is_FFF=None,
                    penumbra=fp_defaults.penumbra,
                    interpolation=fp_defaults.interpolation,
                    edge_detection_method=fp_defaults.edge_detection_method,
                    edge_smoothing_ratio=fp_defaults.edge_smoothing_ratio,
                    hill_window_ratio=fp_defaults.hill_window_ratio,
                )
            set_cached_result(_PREFIX, result)
            st.rerun()
        except Exception:
            logging.exception("Field Profile analysis failed in Advanced mode")
            # Full errors surfaced inline in Advanced mode
            import traceback

            st.error("Analysis failed. Full traceback:")
            st.code(traceback.format_exc())

    return None


def _render_advanced_sidebar(config: AppConfig, result: FieldAnalysisResult) -> dict:
    """Render sidebar with all scalar analyze params + FFF override."""
    fp_defaults = _get_fp_defaults(config)
    base_params = result.params_used if result else {}

    st.sidebar.markdown("---")
    st.sidebar.subheader("Analysis Parameters")

    params: dict = {}
    params["protocol"] = st.sidebar.selectbox(
        "Protocol",
        options=["VARIAN", "SIEMENS", "ELEKTA"],
        index=["VARIAN", "SIEMENS", "ELEKTA"].index(
            str(base_params.get("protocol", fp_defaults.protocol))
        ),
    )
    params["centering"] = st.sidebar.selectbox(
        "Centering",
        options=["BEAM_CENTER", "GEOMETRIC_CENTER", "MANUAL"],
        index=["BEAM_CENTER", "GEOMETRIC_CENTER", "MANUAL"].index(
            str(base_params.get("centering", fp_defaults.centering))
        ),
    )
    params["in_field_ratio"] = st.sidebar.number_input(
        "In-field ratio",
        min_value=0.0,
        max_value=1.0,
        value=float(base_params.get("in_field_ratio", fp_defaults.in_field_ratio)),
        step=0.05,
    )
    # Penumbra lower/upper
    penumbra_default = list(base_params.get("penumbra", fp_defaults.penumbra))
    params["penumbra"] = [
        st.sidebar.number_input(
            "Penumbra lower (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(penumbra_default[0]),
            step=1.0,
        ),
        st.sidebar.number_input(
            "Penumbra upper (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(penumbra_default[1]),
            step=1.0,
        ),
    ]
    params["vert_position"] = st.sidebar.number_input(
        "Vertical position",
        min_value=0.0,
        max_value=1.0,
        value=float(base_params.get("vert_position", fp_defaults.vert_position)),
        step=0.05,
    )
    params["horiz_position"] = st.sidebar.number_input(
        "Horizontal position",
        min_value=0.0,
        max_value=1.0,
        value=float(base_params.get("horiz_position", fp_defaults.horiz_position)),
        step=0.05,
    )
    params["vert_width"] = st.sidebar.number_input(
        "Vertical width",
        min_value=0.0,
        value=float(base_params.get("vert_width", fp_defaults.vert_width)),
        step=0.1,
    )
    params["horiz_width"] = st.sidebar.number_input(
        "Horizontal width",
        min_value=0.0,
        value=float(base_params.get("horiz_width", fp_defaults.horiz_width)),
        step=0.1,
    )
    params["interpolation"] = st.sidebar.selectbox(
        "Interpolation",
        options=["LINEAR", "CUBIC"],
        index=["LINEAR", "CUBIC"].index(
            str(base_params.get("interpolation", fp_defaults.interpolation))
        ),
    )
    params["edge_detection_method"] = st.sidebar.selectbox(
        "Edge detection method",
        options=["INFLECTION_DERIVATIVE", "INFLECTION_HILL", "FWHM"],
        index=["INFLECTION_DERIVATIVE", "INFLECTION_HILL", "FWHM"].index(
            str(base_params.get("edge_detection_method", fp_defaults.edge_detection_method))
        ),
    )
    params["slope_exclusion_ratio"] = st.sidebar.number_input(
        "Slope exclusion ratio",
        min_value=0.0,
        max_value=1.0,
        value=float(base_params.get("slope_exclusion_ratio", fp_defaults.slope_exclusion_ratio)),
        step=0.05,
    )
    params["edge_smoothing_ratio"] = st.sidebar.number_input(
        "Edge smoothing ratio",
        min_value=0.0,
        max_value=0.1,
        value=float(base_params.get("edge_smoothing_ratio", fp_defaults.edge_smoothing_ratio)),
        step=0.001,
    )
    params["hill_window_ratio"] = st.sidebar.number_input(
        "Hill window ratio",
        min_value=0.0,
        max_value=1.0,
        value=float(base_params.get("hill_window_ratio", fp_defaults.hill_window_ratio)),
        step=0.05,
    )

    # FFF override checkbox (pre-checked from detected value)
    detected_fff = bool(base_params.get("is_FFF", False))
    params["is_FFF"] = st.sidebar.checkbox(
        "Force FFF analysis",
        value=detected_fff,
        help=(
            f"Auto-detected: {'FFF' if detected_fff else 'flat'}. "
            "Toggle to override for the next Re-run."
        ),
    )

    return params


def _handle_rerun(
    *,
    config: AppConfig,
    params: dict,
    prev_result: FieldAnalysisResult,
) -> FieldAnalysisResult | None:
    """Re-run handler — invalidates fp_obj, calls cached run with new params."""
    # Lazy fp_obj invalidation on re-run
    invalidate(_PREFIX, suffixes=("obj",))

    # Use the previous session id (preserves the machine_name MyQA cell)
    session_id = prev_result.machine_id

    try:
        with st.spinner("Running Field Profile analysis..."):
            result = run_fp_analysis_cached(
                machine_id=session_id,
                image_path=prev_result.image_path,
                image_display_name=prev_result.image_display_name,
                protocol=params["protocol"],
                centering=params["centering"],
                vert_position=params["vert_position"],
                horiz_position=params["horiz_position"],
                vert_width=params["vert_width"],
                horiz_width=params["horiz_width"],
                in_field_ratio=params["in_field_ratio"],
                slope_exclusion_ratio=params["slope_exclusion_ratio"],
                is_FFF=params["is_FFF"],
                penumbra=params["penumbra"],
                interpolation=params["interpolation"],
                edge_detection_method=params["edge_detection_method"],
                edge_smoothing_ratio=params["edge_smoothing_ratio"],
                hill_window_ratio=params["hill_window_ratio"],
            )
    except Exception:
        logging.exception("Field Profile re-run failed in Advanced mode")
        # Full errors surfaced inline
        import traceback

        st.error("Analysis failed. Full traceback:")
        st.code(traceback.format_exc())
        return None

    # Detect cache short-circuit
    if result == prev_result:
        st.info("Result loaded from cache (parameters unchanged)")
    else:
        set_cached_result(_PREFIX, result)
    return result


def _handle_download(
    *,
    result: FieldAnalysisResult,
    template_path: Path,
) -> None:
    """Download handler — build xlsx bytes, render ``st.download_button``.

    No server-side write. The browser writes the xlsx to the user's Downloads.
    """
    image_stem = Path(result.image_path).stem
    try:
        xlsx_bytes = build_fp_xlsx_bytes(result=result, template_path=template_path)
    except Exception:
        logging.exception("Failed to build Field Profile xlsx bytes for download")
        st.error("Could not build the xlsx download. See the logs for details.")
        return
    st.download_button(
        label="Download xlsx",
        data=xlsx_bytes,
        file_name=f"{image_stem}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------------------------------------------------------------------------
# Advanced tabs
# ---------------------------------------------------------------------------


def _get_fp_obj(result: FieldAnalysisResult):  # type: ignore[no-untyped-def]
    """Lazily initialise the pylinac FieldAnalysis object in session_state."""
    obj = get_cached_obj(_PREFIX)
    if obj is None:
        try:
            fp_obj = load_fp_object(result.image_path, result.params_used)
            set_cached_obj(_PREFIX, fp_obj)
            return fp_obj
        except Exception:
            logger.exception("Failed to load FieldAnalysis object for plot overlays")
            return None
    return obj


def _render_overview_tab(result: FieldAnalysisResult) -> None:
    """Overview tab — summary table (29 metrics), protocol, FFF status."""
    import pandas as pd

    # Session + protocol + FFF status line
    st.write(
        f"**Machine:** {result.summary.get('machine_name', '?')}  |  "
        f"**Date:** {result.summary.get('session_date', '?')}  |  "
        f"**Image:** {result.summary.get('image_name', '?')}"
    )
    protocol = result.params_used.get("protocol", "?")
    st.write(f"**Protocol:** {protocol}  |  **FFF:** {'Yes' if result.is_fff else 'No'}")

    # Build dataframe of all 29 metrics
    meta_fields = {"machine_name", "session_date", "image_name"}
    rows = []
    for name in result.summary:
        if name in meta_fields:
            continue
        rows.append({"Metric": name, "Value": result.summary[name]})
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    # "Analysed with" caption
    params = result.params_used
    param_str = ", ".join(f"{k}={v}" for k, v in sorted(params.items()) if v is not None)
    st.caption(f"Analysed with: {param_str}")


def _render_profiles_tab(result: FieldAnalysisResult) -> None:
    """Profiles tab — Plotly V+H profile line charts (downsampled ~500 pts)."""
    import plotly.graph_objects as go

    vert = result.vert_profile_values
    horiz = result.horiz_profile_values

    if vert:
        fig_v = go.Figure(
            data=go.Scatter(
                y=vert,
                mode="lines",
                hovertemplate="index %{x}: %{y:.4f}<extra></extra>",
            )
        )
        fig_v.update_layout(
            title="Vertical Profile",
            xaxis_title="Position (index)",
            yaxis_title="Normalized dose",
        )
        st.plotly_chart(fig_v, use_container_width=True)

    if horiz:
        fig_h = go.Figure(
            data=go.Scatter(
                y=horiz,
                mode="lines",
                hovertemplate="index %{x}: %{y:.4f}<extra></extra>",
            )
        )
        fig_h.update_layout(
            title="Horizontal Profile",
            xaxis_title="Position (index)",
            yaxis_title="Normalized dose",
        )
        st.plotly_chart(fig_h, use_container_width=True)


def _render_field_map_tab(result: FieldAnalysisResult) -> None:
    """Field Map tab — fa.plot_analyzed_image() rendered as matplotlib figure."""
    import matplotlib.pyplot as plt

    fp_obj = _get_fp_obj(result)
    if fp_obj is None:
        st.warning("Could not load the FieldAnalysis object for the field map.")
        return

    try:
        # pylinac's plot_analyzed_image returns (axes, fig) or similar; render
        # via the current figure to be robust across return shapes.
        fp_obj.plot_analyzed_image()
        fig = plt.gcf()
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    except Exception:
        logger.exception("Failed to render field map")
        st.warning("Could not render the analyzed field map.")


def _render_roi_tab(result: FieldAnalysisResult) -> None:
    """ROI & Penumbra tab — central ROI stats + penumbra table + slopes."""
    import pandas as pd

    s = result.summary

    # Central ROI stats
    st.subheader("Central ROI")
    roi_rows = [
        {"Statistic": "Mean", "Value": s.get("central_roi_mean", "?")},
        {"Statistic": "Max", "Value": s.get("central_roi_max", "?")},
        {"Statistic": "Min", "Value": s.get("central_roi_min", "?")},
        {"Statistic": "Std", "Value": s.get("central_roi_std", "?")},
    ]
    st.dataframe(pd.DataFrame(roi_rows), use_container_width=True)

    # Penumbra table (4 sides)
    st.subheader("Penumbra (mm)")
    penumbra_rows = [
        {"Side": "Top", "Value": s.get("top_penumbra_mm", "?")},
        {"Side": "Bottom", "Value": s.get("bottom_penumbra_mm", "?")},
        {"Side": "Left", "Value": s.get("left_penumbra_mm", "?")},
        {"Side": "Right", "Value": s.get("right_penumbra_mm", "?")},
    ]
    st.dataframe(pd.DataFrame(penumbra_rows), use_container_width=True)

    # Slopes table (4 sides)
    st.subheader("Slopes (%/mm)")
    slope_rows = [
        {"Side": "Top", "Value": s.get("top_slope_percent_mm", "?")},
        {"Side": "Bottom", "Value": s.get("bottom_slope_percent_mm", "?")},
        {"Side": "Left", "Value": s.get("left_slope_percent_mm", "?")},
        {"Side": "Right", "Value": s.get("right_slope_percent_mm", "?")},
    ]
    st.dataframe(pd.DataFrame(slope_rows), use_container_width=True)


# ---------------------------------------------------------------------------
# Page entry point (executed when Streamlit loads this page script)
_config = st.session_state.get("wl_config")
_template = st.session_state.get("fp_template_path", "templates/field_profile.xltx")
if _config is not None:
    render(_config, Path(_template))
else:
    st.warning("Configuration not loaded. Return to the home page to initialise.")
