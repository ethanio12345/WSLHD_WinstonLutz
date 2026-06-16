"""Winston-Lutz QA page — renders Simple or Advanced mode per sidebar toggle.

Implements:
    - wl-simple-mode spec (Simple mode: one-click analysis, success card, hand-off)
    - wl-advanced-mode spec (Advanced mode: 4 tabs, re-run, download, lazy wl_obj)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import streamlit as st

from core.config import AppConfig
from core.excel_writer import write_session_output
from core.result_types import WLAnalysisResult
from core.ui_utils import render_mode_toggle
from core.wl_runner import (
    count_dicoms,
    find_newest_runfolder,
    list_runfolders,
    load_wl_object,
    run_wl_analysis,
    runfolder_mtime,
)

logger = logging.getLogger(__name__)

#: Streamlit ≥1.33 is required for st.dialog (container-deployment spec).
try:
    from streamlit import dialog as _st_dialog  # noqa: F401

    _HAS_DIALOG = True
except ImportError:  # pragma: no cover
    _HAS_DIALOG = False


def render(config: AppConfig, template_path: Path) -> None:
    """Render the Winston-Lutz page (entry point called by the page script)."""
    mode = render_mode_toggle()

    if mode == "simple":
        _render_simple(config, template_path)
    else:
        _render_advanced(config, template_path)


# ---------------------------------------------------------------------------
# Simple mode
# ---------------------------------------------------------------------------


def _render_simple(config: AppConfig, template_path: Path) -> None:
    """Simple mode: machine dropdown → runfolder preview → one-click analysis."""
    st.header("Winston-Lutz — Simple Mode")

    # 6.1 Machine dropdown
    machine_key = _render_machine_dropdown(config)
    if machine_key is None:
        return  # empty-state banner already shown

    machine = config.machines[machine_key]
    wl_defaults = config.wl_defaults
    dicom_root = Path(machine.dicom_roots["winston_lutz"])

    # 6.2 Runfolder preview
    runfolder = find_newest_runfolder(dicom_root)
    if runfolder is None:
        st.error(f"No runfolders found for {machine_key} at {dicom_root}. Contact physics IT.")
        return

    dicom_count = count_dicoms(runfolder)
    if dicom_count == 0:
        st.warning(
            f"Runfolder `{runfolder.name}` is empty. "
            "Wait for DICOM export to complete, then click the button again."
        )
    else:
        st.info(f"Will analyze: `{runfolder.name}` ({dicom_count} DICOMs)")

    # 6.3 One-click analysis button
    button_label = "Shut Up and Give Me My MyQA Results"
    if st.button(
        button_label, type="primary", disabled=(dicom_count == 0 and runfolder is not None)
    ):
        _run_simple_analysis(
            config=config,
            template_path=template_path,
            machine_key=machine_key,
            runfolder=runfolder,
            dicom_count=dicom_count,
        )

    # If we have a cached result from a previous run this session, show the success card
    if "wl_result" in st.session_state and st.session_state.get("wl_machine") == machine_key:
        _render_success_card(
            result=st.session_state["wl_result"],
            xlsx_path=st.session_state.get("wl_xlsx_path"),
            tolerance_mm=wl_defaults.tolerance_mm,
            template_path=template_path,
            config=config,
        )


def _run_simple_analysis(
    *,
    config: AppConfig,
    template_path: Path,
    machine_key: str,
    runfolder: Path,
    dicom_count: int,
) -> None:
    """Execute Simple-mode analysis with error wrapping (6.5)."""
    wl_defaults = config.wl_defaults
    machine = config.machines[machine_key]
    try:
        with st.spinner("Running Winston-Lutz analysis..."):
            result = run_wl_analysis_cached(
                machine_id=machine_key,
                runfolder_path=str(runfolder),
                bb_size_mm=wl_defaults.bb_size_mm,
                machine_scale=wl_defaults.machine_scale,
                low_density_bb=wl_defaults.low_density_bb,
                open_field=wl_defaults.open_field,
                apply_virtual_shift=wl_defaults.apply_virtual_shift,
                snap_tolerance=wl_defaults.snap_tolerance,
                gantry_reference=wl_defaults.gantry_reference,
                collimator_reference=wl_defaults.collimator_reference,
                couch_reference=wl_defaults.couch_reference,
                dicom_file_count=dicom_count,
                runfolder_mtime_val=runfolder_mtime(runfolder),
            )
            xlsx_path = write_session_output(
                result=result,
                output_root=Path(config.output.root),
                template_path=template_path,
                machine_display_name=machine.display_name,
                category=config.output.category,
                pylinac_subfolder=config.output.pylinac_subfolder,
            )
        # Store in session state for success card + hand-off
        st.session_state["wl_result"] = result
        st.session_state["wl_xlsx_path"] = str(xlsx_path)
        st.session_state["wl_machine"] = machine_key
        st.rerun()

    except Exception:
        logging.exception("Winston-Lutz analysis failed in Simple mode")
        summary = _safe_error_message()
        st.error(f"Analysis failed: {summary}. Switch to Advanced mode to debug.")


def _render_machine_dropdown(config: AppConfig) -> str | None:
    """6.1 Sidebar machine dropdown. Returns machine key or None (empty state)."""
    machine_keys = config.sorted_machine_keys
    if not machine_keys:
        st.warning("No machines configured. Edit machines.yaml and reload.")
        return None

    options = {k: config.machines[k].display_name for k in machine_keys}
    selected = st.sidebar.selectbox(
        "Machine",
        options=machine_keys,
        format_func=lambda k: options[k],
    )
    return selected


def _render_success_card(
    *,
    result: WLAnalysisResult,
    xlsx_path: str | None,
    tolerance_mm: float,
    template_path: Path,
    config: AppConfig,
) -> None:
    """6.4 Success card with metrics + hand-off button."""
    st.success("Analysis complete!")

    if xlsx_path:
        st.write(f"**Output:** `{xlsx_path}`")

    max_dist = result.summary.get("max_2d_cax_to_bb", 0.0)
    passed = float(max_dist) <= tolerance_mm
    badge = "[PASS]" if passed else "[FAIL]"

    st.write(f"**Max 2D dist:** {max_dist} mm {badge}")
    st.write(f"**Median 2D dist:** {result.summary.get('median_2d_cax_to_bb', '?')}")
    st.write(f"**Gantry 3D iso:** {result.summary.get('gantry_3d_iso', '?')}")

    # 6.6 Hand-off to Advanced mode
    if st.button("View in Advanced mode"):
        st.session_state["wl_result"] = result
        st.session_state["wl_mode_switch"] = "advanced"
        st.rerun()


def _safe_error_message() -> str:
    """Generate a one-line user-safe error summary (6.5)."""
    import sys

    exc_type, exc_value, _ = sys.exc_info()
    if exc_type is None:
        return "unknown error"
    type_name = exc_type.__name__
    msg = str(exc_value)
    # Map known exception types to friendly messages
    if "BB" in msg or "bb" in msg:
        return "could not detect the BB. Check image quality or switch to Advanced mode."
    if "DICOM" in msg or "dicom" in msg:
        return "could not read DICOM images. Check the runfolder."
    return f"{type_name}: {msg[:80]}"


# ---------------------------------------------------------------------------
# Caching wrapper (8.1)
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def run_wl_analysis_cached(**kwargs):  # type: ignore[no-untyped-def]
    """Cached wrapper around run_wl_analysis (8.1, 8.3).

    The ``@st.cache_data`` decorator caches based on ALL arguments (which
    include ``machine_id``, ``runfolder_path``, all 9 analyze params, and
    ``dicom_file_count`` + ``runfolder_mtime_val`` for staleness invalidation).
    """
    return run_wl_analysis(**kwargs)


# ---------------------------------------------------------------------------
# Advanced mode
# ---------------------------------------------------------------------------


def _render_advanced(config: AppConfig, template_path: Path) -> None:
    """Advanced mode: sidebar params + 4 tabs."""
    st.header("Winston-Lutz — Advanced Mode")

    # 7.7 Hand-off reception: if wl_result is set, use it; don't re-run
    result: WLAnalysisResult | None = st.session_state.get("wl_result")
    machine_key = st.session_state.get("wl_machine")

    if result is None or machine_key is None:
        # No hand-off — need to run analysis first via sidebar
        st.info("No analysis result yet. Run analysis from the sidebar.")
        machine_key, result = _advanced_initial_run(config, template_path)
        if result is None:
            return

    # 7.1 Advanced sidebar with params + tolerance + buttons
    params, tolerance_mm = _render_advanced_sidebar(
        config=config,
        result=result,
    )

    # 7.8 Re-run handler
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
    tab_overview, tab_per_image, tab_plots, tab_detection = st.tabs(
        ["Overview", "Per-image", "Plots", "Detection overlay"]
    )

    with tab_overview:
        _render_overview_tab(result, tolerance_mm)
    with tab_per_image:
        _render_per_image_tab(result, config)
    with tab_plots:
        _render_plots_tab(result)
    with tab_detection:
        _render_detection_tab(result, params)


def _advanced_initial_run(
    config: AppConfig, template_path: Path
) -> tuple[str | None, WLAnalysisResult | None]:
    """Run an initial analysis from the sidebar if no hand-off result exists."""
    machine_key = _render_machine_dropdown(config)
    if machine_key is None:
        return None, None

    machine = config.machines[machine_key]
    wl_defaults = config.wl_defaults
    dicom_root = Path(machine.dicom_roots["winston_lutz"])

    # --- Folder picker: selectbox of auto-discovered runfolders ---
    runfolders = list_runfolders(dicom_root)
    runfolder: Path | None = None
    custom_path = ""

    if runfolders:
        # Default to newest; show folder names sorted newest-first
        default_idx = 0
        folder_labels = [p.name for p in runfolders]
        selected_label = st.sidebar.selectbox(
            "Runfolder",
            options=folder_labels,
            index=default_idx,
            key="wl_runfolder_select",
            help="Choose a runfolder from the DICOM root, or enter a custom path below.",
        )
        runfolder = runfolders[folder_labels.index(selected_label)]
    else:
        st.sidebar.warning(f"No runfolders found under `{dicom_root}`.")

    # --- Custom path override (for folders outside dicom_root) ---
    custom_path = st.sidebar.text_input(
        "Or enter custom folder path",
        value="",
        placeholder="/path/to/dicom/runfolder",
        key="wl_custom_runfolder",
        help="Override the selected runfolder with an absolute path to any DICOM folder.",
    )
    if custom_path.strip():
        custom = Path(custom_path.strip())
        if custom.is_dir():
            runfolder = custom
        else:
            st.sidebar.error(f"Path does not exist: `{custom}`")
            return machine_key, None

    if runfolder is None:
        st.error("No runfolder selected. Enter a custom path above.")
        return machine_key, None

    dicom_count = count_dicoms(runfolder)
    st.info(f"Will analyze: `{runfolder}` ({dicom_count} DICOMs)")

    if st.sidebar.button("Run analysis", type="primary"):
        try:
            with st.spinner("Running Winston-Lutz analysis..."):
                result = run_wl_analysis_cached(
                    machine_id=machine_key,
                    runfolder_path=str(runfolder),
                    bb_size_mm=wl_defaults.bb_size_mm,
                    machine_scale=wl_defaults.machine_scale,
                    low_density_bb=wl_defaults.low_density_bb,
                    open_field=wl_defaults.open_field,
                    apply_virtual_shift=wl_defaults.apply_virtual_shift,
                    snap_tolerance=wl_defaults.snap_tolerance,
                    gantry_reference=wl_defaults.gantry_reference,
                    collimator_reference=wl_defaults.collimator_reference,
                    couch_reference=wl_defaults.couch_reference,
                    dicom_file_count=dicom_count,
                    runfolder_mtime_val=runfolder_mtime(runfolder),
                )
            st.session_state["wl_result"] = result
            st.session_state["wl_machine"] = machine_key
            st.rerun()
        except Exception:
            logging.exception("Winston-Lutz analysis failed in Advanced mode")
            summary = _safe_error_message()
            st.error(f"Analysis failed: {summary}")

    return machine_key, None


def _render_advanced_sidebar(config: AppConfig, result: WLAnalysisResult) -> tuple[dict, float]:
    """7.1 Render sidebar with 9 pylinac params + tolerance_mm widget."""
    wl_defaults = config.wl_defaults
    # On hand-off, use params_used; otherwise use config defaults
    base_params = result.params_used if result else {}

    st.sidebar.markdown("---")
    st.sidebar.subheader("Analysis Parameters")

    params: dict = {}
    params["bb_size_mm"] = st.sidebar.number_input(
        "BB size (mm)",
        min_value=0.5,
        max_value=20.0,
        value=float(base_params.get("bb_size_mm", wl_defaults.bb_size_mm)),
        step=0.5,
    )
    params["machine_scale"] = st.sidebar.selectbox(
        "Machine scale",
        options=["VARIAN_IEC", "VARIAN_STANDARD", "IEC61217"],
        index=["VARIAN_IEC", "VARIAN_STANDARD", "IEC61217"].index(
            base_params.get("machine_scale", wl_defaults.machine_scale)
        ),
    )
    params["low_density_bb"] = st.sidebar.checkbox(
        "Low density BB",
        value=bool(base_params.get("low_density_bb", wl_defaults.low_density_bb)),
    )
    params["open_field"] = st.sidebar.checkbox(
        "Open field",
        value=bool(base_params.get("open_field", wl_defaults.open_field)),
    )
    params["apply_virtual_shift"] = st.sidebar.checkbox(
        "Apply virtual shift",
        value=bool(base_params.get("apply_virtual_shift", wl_defaults.apply_virtual_shift)),
    )
    params["snap_tolerance"] = st.sidebar.number_input(
        "Snap tolerance",
        min_value=0.0,
        value=float(base_params.get("snap_tolerance") or 5.0),
        step=1.0,
    )
    params["gantry_reference"] = st.sidebar.number_input(
        "Gantry reference",
        value=float(base_params.get("gantry_reference") or 0.0),
        step=1.0,
    )
    params["collimator_reference"] = st.sidebar.number_input(
        "Collimator reference",
        value=float(base_params.get("collimator_reference") or 0.0),
        step=1.0,
    )
    params["couch_reference"] = st.sidebar.number_input(
        "Couch reference",
        value=float(base_params.get("couch_reference") or 0.0),
        step=1.0,
    )

    tolerance_mm = st.sidebar.number_input(
        "Tolerance (mm, UI-only)",
        min_value=0.1,
        value=float(wl_defaults.tolerance_mm),
        step=0.1,
        help="Pass/fail threshold for max_2d_cax_to_bb. Not passed to pylinac.",
    )

    return params, tolerance_mm


def _handle_rerun(
    *,
    config: AppConfig,
    template_path: Path,
    machine_key: str,
    params: dict,
    prev_result: WLAnalysisResult,
) -> WLAnalysisResult | None:
    """7.8 Re-run analysis handler — invalidates wl_obj, calls cached run."""
    # Clear the lazy wl_obj so it reloads with new params
    st.session_state.pop("wl_obj", None)

    runfolder = Path(prev_result.runfolder_path)
    dicom_count = count_dicoms(runfolder)

    try:
        with st.spinner("Running Winston-Lutz analysis..."):
            result = run_wl_analysis_cached(
                machine_id=machine_key,
                runfolder_path=str(runfolder),
                bb_size_mm=params["bb_size_mm"],
                machine_scale=params["machine_scale"],
                low_density_bb=params["low_density_bb"],
                open_field=params["open_field"],
                apply_virtual_shift=params["apply_virtual_shift"],
                snap_tolerance=params["snap_tolerance"],
                gantry_reference=params["gantry_reference"],
                collimator_reference=params["collimator_reference"],
                couch_reference=params["couch_reference"],
                dicom_file_count=dicom_count,
                runfolder_mtime_val=runfolder_mtime(runfolder),
            )
    except Exception:
        logging.exception("Winston-Lutz re-run failed in Advanced mode")
        st.error(f"Analysis failed: {_safe_error_message()}")
        return prev_result  # keep the old result so tabs still render

    # Detect cache short-circuit
    if result == prev_result:
        st.info("Result loaded from cache (parameters unchanged)")
    else:
        st.session_state["wl_result"] = result
    return result


def _handle_download(
    *,
    result: WLAnalysisResult,
    config: AppConfig,
    template_path: Path,
) -> None:
    """7.9 Download xlsx handler."""
    machine = config.machines.get(result.machine_id)
    display_name = machine.display_name if machine else result.machine_id
    xlsx_path = write_session_output(
        result=result,
        output_root=Path(config.output.root),
        template_path=template_path,
        machine_display_name=display_name,
        category=config.output.category,
        pylinac_subfolder=config.output.pylinac_subfolder,
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


def _format_bb_shift(x: float, y: float, z: float) -> str:
    """Format the 3D BB shift vector as a human-readable string with directions.

    Uses IEC 61217 convention (Varian default):
        X+ = Left,    X- = Right
        Y+ = Superior, Y- = Inferior
        Z+ = Anterior, Z- = Posterior

    Args:
        x: Lateral shift component (mm).
        y: Longitudinal shift component (mm).
        z: Vertical shift component (mm).

    Returns:
        e.g. ``"0.50 mm Left, 0.30 mm Superior, 0.20 mm Posterior (total 0.62 mm)"``
    """
    import math

    parts = [
        f"{abs(x):.2f} mm {'Left' if x >= 0 else 'Right'}",
        f"{abs(y):.2f} mm {'Superior' if y >= 0 else 'Inferior'}",
        f"{abs(z):.2f} mm {'Anterior' if z >= 0 else 'Posterior'}",
    ]
    total = math.sqrt(x * x + y * y + z * z)
    return f"{', '.join(parts)}  (total {total:.2f} mm)"


def _render_overview_tab(result: WLAnalysisResult, tolerance_mm: float) -> None:
    """7.2 Overview tab — summary dataframe + pass/fail on max_2d_cax_to_bb."""
    import pandas as pd

    # Show session metadata as header
    st.write(
        f"**Machine:** {result.summary.get('machine_name', '?')}  |  "
        f"**Date:** {result.summary.get('session_date', '?')}  |  "
        f"**Images:** {result.summary.get('num_total_images', '?')}"
    )

    # Build dataframe of all metrics
    from core.config import WL_METRIC_NAMES

    meta_fields = {"machine_name", "session_date", "num_total_images"}
    rows = []
    for name in WL_METRIC_NAMES:
        if name in meta_fields:
            continue
        value = result.summary.get(name, 0.0)
        status = ""
        if name == "max_2d_cax_to_bb":
            passed = float(value) <= tolerance_mm
            status = "[PASS]" if passed else "[FAIL]"
        rows.append({"Metric": name, "Value": value, "Status": status})

    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    # Human-readable BB shift vector with clinical directions
    bb_shift_text = _format_bb_shift(
        result.summary.get("bb_shift_x", 0.0),
        result.summary.get("bb_shift_y", 0.0),
        result.summary.get("bb_shift_z", 0.0),
    )
    st.info(f"**Suggested BB shift:** {bb_shift_text}")

    # "Analysed with" summary line
    params = result.params_used
    param_str = ", ".join(f"{k}={v}" for k, v in sorted(params.items()))
    st.caption(f"Analysed with: {param_str}")


def _render_per_image_tab(result: WLAnalysisResult, config: AppConfig) -> None:
    """7.3 Per-image tab — dataframe + axis filter + view-image button."""
    import pandas as pd

    if not result.image_details:
        st.info("No per-image data available.")
        return

    df = pd.DataFrame(result.image_details)
    df.insert(0, "image_key", result.image_keys)

    # Axis filter
    col1, col2 = st.columns(2)
    axis = col1.selectbox(
        "Filter axis", options=["None", "gantry_angle", "collimator_angle", "couch_angle"]
    )
    filter_value = col2.number_input("Axis value", value=0.0, step=1.0)

    if axis != "None" and axis in df.columns:
        filtered = df[df[axis].astype(float) == filter_value]
        st.dataframe(filtered, use_container_width=True)
    else:
        st.dataframe(df, use_container_width=True)

    # Per-row "View image" buttons (requires wl_obj)
    st.markdown("**View individual image:**")
    selected_key = st.selectbox("Image key", options=result.image_keys)
    if st.button("View image") and selected_key:
        wl_obj = _get_wl_obj(result)
        if wl_obj is not None:
            idx = result.image_keys.index(selected_key)
            try:
                _render_wl_image(wl_obj, idx)
            except Exception:
                logger.exception("Failed to render image %s", selected_key)
                st.warning(f"Could not render image {selected_key}.")


def _render_plots_tab(result: WLAnalysisResult) -> None:
    """7.4 Plots tab — three Plotly charts from precomputed arrays."""
    import plotly.graph_objects as go

    # (a) Deviation vs gantry
    dev = result.deviation_vs_gantry
    if dev.get("x"):
        fig1 = go.Figure(
            data=go.Scatter(
                x=dev["x"],
                y=dev["y"],
                mode="markers",
                text=dev.get("text"),
                hovertemplate="Gantry %{x}°: %{y:.2f} mm<br>%{text}<extra></extra>",
            )
        )
        fig1.update_layout(
            title="CAX→BB distance vs Gantry angle",
            xaxis_title="Gantry angle (°)",
            yaxis_title="CAX→BB distance (mm)",
        )
        st.plotly_chart(fig1, use_container_width=True)

    # (b) BB X vs Y scatter
    scatter = result.bb_xy_scatter
    if scatter.get("x"):
        # Deterministic color assignment based on variable_axis label
        axis_labels = scatter.get("color", [])
        unique_axes = sorted({str(a) for a in axis_labels})
        axis_to_idx = {label: i for i, label in enumerate(unique_axes)}
        color_indices = [axis_to_idx.get(str(a), 0) for a in axis_labels]

        fig2 = go.Figure(
            data=go.Scatter(
                x=scatter["x"],
                y=scatter["y"],
                mode="markers",
                marker={
                    "color": color_indices,
                    "colorscale": "Viridis",
                    "showscale": True,
                    "colorbar": {
                        "title": "Axis",
                        "tickvals": list(range(len(unique_axes))),
                        "ticktext": unique_axes,
                    },
                },
                text=axis_labels,
                hovertemplate="X: %{x:.2f}, Y: %{y:.2f}<br>%{text}<extra></extra>",
            )
        )
        fig2.update_layout(
            title="BB X vs Y deviation",
            xaxis_title="CAX→BB X (mm)",
            yaxis_title="CAX→BB Y (mm)",
        )
        st.plotly_chart(fig2, use_container_width=True)

    # (c) Distance histogram
    hist = result.distance_histogram
    if hist.get("values"):
        fig3 = go.Figure(data=go.Histogram(x=hist["values"], nbinsx=10))
        fig3.update_layout(
            title="CAX→BB distance distribution",
            xaxis_title="Distance (mm)",
            yaxis_title="Count",
        )
        st.plotly_chart(fig3, use_container_width=True)


def _render_detection_tab(result: WLAnalysisResult, params: dict) -> None:
    """7.5 Detection overlay tab — grid of wl.images[i].plot()."""
    wl_obj = _get_wl_obj(result)
    if wl_obj is None:
        st.info("Loading images...")
        return

    st.write(f"Showing {len(result.image_keys)} images:")
    # Grid: 4 columns
    cols = st.columns(4)
    for i, key in enumerate(result.image_keys):
        col = cols[i % 4]
        with col:
            try:
                _render_wl_image(wl_obj, i, caption=key)
            except Exception:
                logger.exception("Failed to render detection overlay %s", key)
                st.warning(f"Could not render {key}.")

    # Click for full-size view via st.dialog (Streamlit ≥1.33)
    if _HAS_DIALOG:
        selected_key = st.selectbox("Open full-size image", options=result.image_keys)
        if st.button("Open dialog") and selected_key:
            _show_image_dialog(wl_obj, result.image_keys.index(selected_key), selected_key)


def _show_image_dialog(wl_obj, idx: int, key: str) -> None:  # type: ignore[no-untyped-def]
    """Open a st.dialog with a full-size image."""
    if _HAS_DIALOG:

        @st.dialog(f"Image {key}", width="large")
        def _dialog():
            try:
                _render_wl_image(wl_obj, idx)
            except Exception:
                st.error("Could not render image.")
            if st.button("Close"):
                st.rerun()

        _dialog()


# ---------------------------------------------------------------------------
# Lazy wl_obj init (7.6)
# ---------------------------------------------------------------------------


def _render_wl_image(wl_obj: Any, idx: int, caption: str | None = None) -> None:
    """Render a single pylinac WL image via matplotlib → st.pyplot.

    pylinac's ``WinstonLutz2D.plot()`` returns a matplotlib Axes (not a Figure),
    so we extract ``ax.figure`` for ``st.pyplot``.
    """
    import matplotlib.pyplot as plt

    ax = wl_obj.images[idx].plot()
    # plot() may return Axes or None depending on pylinac version
    fig = ax.figure if hasattr(ax, "figure") else plt.gcf()
    if caption:
        st.caption(caption)
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def _get_wl_obj(result: WLAnalysisResult):  # type: ignore[no-untyped-def]
    """7.6 Lazily initialise the pylinac WinstonLutz object in session_state."""
    if "wl_obj" not in st.session_state:
        try:
            wl_obj = load_wl_object(result.runfolder_path, result.params_used)
            st.session_state["wl_obj"] = wl_obj
        except Exception:
            logger.exception("Failed to load WL object for detection overlay")
            return None
    return st.session_state["wl_obj"]


# ---------------------------------------------------------------------------
# Page entry point (executed when Streamlit loads this page script)
# Streamlit runs pages as top-level scripts, so this always executes.
_config = st.session_state.get("wl_config")
_template = st.session_state.get("wl_template_path", "templates/winston_lutz.xltx")
if _config is not None:
    render(_config, Path(_template))
else:
    st.warning("Configuration not loaded. Return to the home page to initialise.")
