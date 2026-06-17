"""Field Profile QA page — renders Simple or Advanced mode per sidebar toggle.

Implements:
    - fp-simple-mode spec (Simple mode: machine/runfolder/image dropdowns,
      one-click analysis, FFF auto-detection, success card, hand-off)
    - fp-advanced-mode spec (Advanced mode: sidebar params + FFF override,
      4 tabs (Overview, Profiles, Field Map, ROI & Penumbra), re-run, download,
      lazy fp_obj, full inline errors)

Mirrors the structure of ``pages/2_CatPhan.py`` but adapted for the
single-image input model (design D1): Field Analysis operates on one DICOM,
so the page adds an image dropdown after the runfolder dropdown.
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
from core.config import AppConfig
from core.fp_excel_writer import write_fp_session_output
from core.fp_runner import (
    extract_dicom_info,
    load_fp_object,
    run_fp_analysis,
)
from core.result_types import FieldAnalysisResult
from core.runfolder import list_runfolders
from core.ui_utils import render_mode_toggle

logger = logging.getLogger(__name__)

#: Session-state prefix for this module.
_PREFIX = "fp"


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
# Helpers — image discovery (single-image input model, design D1)
# ---------------------------------------------------------------------------


def _list_dicom_images(runfolder: Path) -> list[Path]:
    """List DICOM files in ``runfolder``, sorted by name."""
    if not runfolder.exists():
        return []
    images: list[Path] = []
    for pattern in ("*.dcm", "*.dicom", "*.DCM"):
        images.extend(runfolder.glob(pattern))
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


# ---------------------------------------------------------------------------
# Simple mode
# ---------------------------------------------------------------------------


def _render_simple(config: AppConfig, template_path: Path) -> None:
    """Simple mode: machine → runfolder → image → one-click analysis."""
    st.header("Field Profile — Simple Mode")

    # 5.1 Machine dropdown (filtered to field_profile-configured machines)
    machine_key = _render_machine_dropdown(config)
    if machine_key is None:
        return  # empty-state warning already shown

    machine = config.machines[machine_key]
    dicom_root = Path(machine.dicom_roots["field_profile"])

    # 5.2 Runfolder dropdown (newest-first, auto-select newest)
    runfolder = _render_runfolder_dropdown(dicom_root)
    if runfolder is None:
        return

    # 5.3 Image dropdown with DICOM metadata display
    image_path, dicom_info = _render_image_dropdown(runfolder)
    if image_path is None:
        return

    # 5.4 FFF detection display
    is_fff = bool(dicom_info.get("is_fff", False))
    st.info(f"**FFF detected:** {'Yes' if is_fff else 'No'}")

    # 5.5 One-click analysis button
    if st.button("Shut Up and Give Me My MyQA Results", type="primary"):
        _run_simple_analysis(
            config=config,
            template_path=template_path,
            machine_key=machine_key,
            image_path=image_path,
            image_display_name=dicom_info["display_string"],
        )

    # If we have a cached result from a previous run this session, show the card
    cached = get_cached_result(_PREFIX)
    if cached is not None and st.session_state.get(f"{_PREFIX}_machine") == machine_key:
        _render_success_card(
            result=cached,
            xlsx_path=st.session_state.get(f"{_PREFIX}_xlsx_path"),
        )


def _run_simple_analysis(
    *,
    config: AppConfig,
    template_path: Path,
    machine_key: str,
    image_path: Path,
    image_display_name: str,
) -> None:
    """Execute Simple-mode analysis with error wrapping (5.5)."""
    fp_defaults = config.fp_defaults
    machine = config.machines[machine_key]
    try:
        with st.spinner("Running Field Profile analysis..."):
            result = run_fp_analysis_cached(
                machine_id=machine_key,
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
            xlsx_path = write_fp_session_output(
                result=result,
                output_root=Path(machine.output_root),
                template_path=template_path,
            )
        # Store in session state for success card + hand-off
        set_cached_result(_PREFIX, result)
        st.session_state[f"{_PREFIX}_xlsx_path"] = str(xlsx_path)
        st.session_state[f"{_PREFIX}_machine"] = machine_key
        st.rerun()

    except Exception:
        logging.exception("Field Profile analysis failed in Simple mode")
        summary = _safe_error_message()
        st.error(f"Analysis failed: {summary}. Switch to Advanced mode to debug.")


def _render_machine_dropdown(config: AppConfig) -> str | None:
    """5.1 Sidebar machine dropdown — filtered to field_profile machines."""
    machine_keys = config.machine_keys_for_module("field_profile")
    if not machine_keys:
        st.warning("No machines have Field Profile configured. Edit machines.yaml and reload.")
        return None

    options = {k: config.machines[k].display_name for k in machine_keys}
    selected = st.sidebar.selectbox(
        "Machine",
        options=machine_keys,
        format_func=lambda k: options[k],
    )
    return selected


def _render_runfolder_dropdown(dicom_root: Path) -> Path | None:
    """5.2 Runfolder dropdown — newest-first, auto-select newest."""
    runfolders = list_runfolders(dicom_root)
    if not runfolders:
        st.error(f"No runfolders found for field_profile root {dicom_root}. Contact physics IT.")
        return None

    folder_labels = [p.name for p in runfolders]
    selected_label = st.sidebar.selectbox(
        "Runfolder",
        options=folder_labels,
        index=0,  # newest-first → auto-select newest
        key=f"{_PREFIX}_runfolder_select",
    )
    return runfolders[folder_labels.index(selected_label)]


def _render_image_dropdown(runfolder: Path) -> tuple[Path | None, dict]:
    """5.3 Image dropdown — list DICOMs with metadata display.

    Returns (selected_image_path, dicom_info_dict) or (None, {}) if no images.
    """
    images = _list_dicom_images(runfolder)
    if not images:
        st.error(f"No DICOM images found in runfolder `{runfolder.name}`.")
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
    xlsx_path: str | None,
) -> None:
    """5.6 Success card with key metrics + hand-off button."""
    st.success("Analysis complete!")

    if xlsx_path:
        st.write(f"**Output:** `{xlsx_path}`")

    s = result.summary
    st.write(f"**Flatness Vertical (%):** {s.get('flatness_vertical', '?')}")
    st.write(f"**Flatness Horizontal (%):** {s.get('flatness_horizontal', '?')}")
    st.write(f"**Symmetry Vertical (%):** {s.get('symmetry_vertical', '?')}")
    st.write(f"**Symmetry Horizontal (%):** {s.get('symmetry_horizontal', '?')}")
    st.write(f"**Field Size Vertical (mm):** {s.get('field_size_vertical_mm', '?')}")
    st.write(f"**Field Size Horizontal (mm):** {s.get('field_size_horizontal_mm', '?')}")
    st.write(f"**FFF status:** {'Yes' if result.is_fff else 'No'}")

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
    if "write" in msg.lower() or "permission" in msg.lower():
        return "cannot write to the output directory. Contact physics IT."
    return f"{type_name}: {msg[:80]}"


# ---------------------------------------------------------------------------
# Advanced mode
# ---------------------------------------------------------------------------


def _render_advanced(config: AppConfig, template_path: Path) -> None:
    """Advanced mode: sidebar params + FFF override + 4 tabs."""
    st.header("Field Profile — Advanced Mode")

    # 6.6 Hand-off reception: if fp_result is set, use it; don't re-run
    result: FieldAnalysisResult | None = get_cached_result(_PREFIX)
    machine_key = st.session_state.get(f"{_PREFIX}_machine")

    if result is None or machine_key is None:
        # No hand-off — need to run analysis first via sidebar
        st.info("No analysis result yet. Run analysis from the sidebar.")
        machine_key, result = _advanced_initial_run(config, template_path)
        if result is None:
            return

    # 6.1 Advanced sidebar with params + FFF override
    params = _render_advanced_sidebar(
        config=config,
        result=result,
    )

    # Re-run + download handlers
    col1, col2 = st.sidebar.columns(2)
    rerun_clicked = col1.button("Re-run analysis")
    download_clicked = col2.button("Download xlsx")

    if rerun_clicked:
        result = _handle_rerun(
            config=config,
            template_path=template_path,
            machine_key=machine_key,
            params=params,
            prev_result=result,
        )

    if download_clicked:
        _handle_download(
            result=result,
            config=config,
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


def _advanced_initial_run(
    config: AppConfig, template_path: Path
) -> tuple[str | None, FieldAnalysisResult | None]:
    """Run an initial analysis from the sidebar if no hand-off result exists."""
    machine_key = _render_machine_dropdown(config)
    if machine_key is None:
        return None, None

    machine = config.machines[machine_key]
    fp_defaults = config.fp_defaults
    dicom_root = Path(machine.dicom_roots["field_profile"])

    runfolder = _render_runfolder_dropdown(dicom_root)
    if runfolder is None:
        return machine_key, None

    image_path, dicom_info = _render_image_dropdown(runfolder)
    if image_path is None:
        return machine_key, None

    st.info(
        f"**FFF detected:** {'Yes' if dicom_info.get('is_fff') else 'No'} — will analyse: `{image_path.name}`"
    )

    if st.sidebar.button("Run analysis", type="primary"):
        try:
            with st.spinner("Running Field Profile analysis..."):
                result = run_fp_analysis_cached(
                    machine_id=machine_key,
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
            st.session_state[f"{_PREFIX}_machine"] = machine_key
            st.rerun()
        except Exception:
            logging.exception("Field Profile analysis failed in Advanced mode")
            # 6.9 Full errors surfaced inline in Advanced mode
            import traceback

            st.error("Analysis failed. Full traceback:")
            st.code(traceback.format_exc())

    return machine_key, None


def _render_advanced_sidebar(config: AppConfig, result: FieldAnalysisResult) -> dict:
    """6.1 Render sidebar with all scalar analyze params + FFF override."""
    fp_defaults = config.fp_defaults
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

    # 6.1 FFF override checkbox (pre-checked from detected value)
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
    template_path: Path,
    machine_key: str,
    params: dict,
    prev_result: FieldAnalysisResult,
) -> FieldAnalysisResult | None:
    """6.7 Re-run handler — invalidates fp_obj, calls cached run with new params."""
    # 6.10 Lazy fp_obj invalidation on re-run
    invalidate(_PREFIX, suffixes=("obj",))

    try:
        with st.spinner("Running Field Profile analysis..."):
            result = run_fp_analysis_cached(
                machine_id=machine_key,
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
        # 6.9 Full errors surfaced inline
        import traceback

        st.error("Analysis failed. Full traceback:")
        st.code(traceback.format_exc())
        return prev_result

    # Detect cache short-circuit
    if result == prev_result:
        st.info("Result loaded from cache (parameters unchanged)")
    else:
        set_cached_result(_PREFIX, result)
    return result


def _handle_download(
    *,
    result: FieldAnalysisResult,
    config: AppConfig,
    template_path: Path,
) -> None:
    """6.8 Download handler — write xlsx, show download button."""
    machine = config.machines.get(result.machine_id)
    output_root = machine.output_root if machine else "/tmp"
    xlsx_path = write_fp_session_output(
        result=result,
        output_root=Path(output_root),
        template_path=template_path,
    )
    with open(xlsx_path, "rb") as f:
        st.download_button(
            label="Download xlsx",
            data=f.read(),
            file_name=Path(xlsx_path).name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ---------------------------------------------------------------------------
# Advanced tabs
# ---------------------------------------------------------------------------


def _get_fp_obj(result: FieldAnalysisResult):  # type: ignore[no-untyped-def]
    """6.10 Lazily initialise the pylinac FieldAnalysis object in session_state."""
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
    """6.2 Overview tab — summary table (29 metrics), protocol, FFF status."""
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
    """6.3 Profiles tab — Plotly V+H profile line charts (downsampled ~500 pts)."""
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
    """6.4 Field Map tab — fa.plot_analyzed_image() rendered as matplotlib figure."""
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
    """6.5 ROI & Penumbra tab — central ROI stats + penumbra table + slopes."""
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
