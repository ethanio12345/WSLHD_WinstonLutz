"""CatPhan 504 QA page — renders Simple or Advanced mode per sidebar toggle.

Implements:
    - cbct-simple-mode spec (Simple mode: one-click analysis, success card, hand-off)
    - cbct-advanced-mode spec (Advanced mode: 5 tabs, re-run, download, lazy cp_obj)

Mirrors the structure of ``pages/1_Winston_Lutz.py`` but for CatPhan analysis.
Uses the shared utilities extracted in the refactor (``core.caching``,
``core.runfolder``, ``core.session_io``, ``core.excel_helpers``).
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
from core.cbct_excel_writer import write_cbct_session_output
from core.cbct_runner import load_cbct_object, run_cbct_analysis
from core.config import AppConfig
from core.result_types import CatPhanAnalysisResult
from core.runfolder import count_dicoms, find_newest_runfolder, runfolder_mtime
from core.ui_utils import render_mode_toggle

logger = logging.getLogger(__name__)


def render(config: AppConfig, template_path: Path) -> None:
    """Render the CatPhan page (entry point called by the page script)."""
    mode = render_mode_toggle()

    if mode == "simple":
        _render_simple(config, template_path)
    else:
        _render_advanced(config, template_path)


# ---------------------------------------------------------------------------
# Cached wrapper (same pattern as WL page's run_wl_analysis_cached)
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner="Running CatPhan 504 analysis...")
def run_cbct_analysis_cached(**kwargs):  # type: ignore[no-untyped-def]
    """Cached wrapper around run_cbct_analysis.

    The ``@st.cache_data`` decorator caches based on ALL arguments (which
    include ``machine_id``, ``runfolder_path``, all 10 analyze params, and
    ``dicom_file_count`` + ``runfolder_mtime`` for staleness invalidation).
    """
    return run_cbct_analysis(**kwargs)


# ---------------------------------------------------------------------------
# Simple mode
# ---------------------------------------------------------------------------


def _render_simple(config: AppConfig, template_path: Path) -> None:
    """Simple mode: machine dropdown -> runfolder preview -> one-click analysis."""
    st.header("CatPhan 504 — Simple Mode")

    # 6.1 Machine dropdown (filtered to catphan-configured machines)
    machine_key = _render_machine_dropdown(config)
    if machine_key is None:
        return  # empty-state banner already shown

    machine = config.machines[machine_key]
    dicom_root = Path(machine.dicom_roots["catphan"])

    # 6.2 Runfolder preview
    runfolder = find_newest_runfolder(dicom_root)
    if runfolder is None:
        st.error(f"No runfolders found for {machine_key} at {dicom_root}. Contact physics IT.")
        return

    dicom_count = count_dicoms(runfolder)
    run_button_disabled = False
    if dicom_count == 0:
        st.warning(
            f"Runfolder `{runfolder.name}` is empty. "
            "Wait for DICOM export to complete, then click the button again."
        )
    else:
        st.info(f"Will analyze: `{runfolder.name}` ({dicom_count} DICOMs)")

    # 6.3 One-click analysis button
    button_label = "Shut Up and Give Me My MyQA Results"
    if st.button(button_label, type="primary", disabled=run_button_disabled and dicom_count == 0):
        _run_simple_analysis(
            config=config,
            template_path=template_path,
            machine_key=machine_key,
            runfolder=runfolder,
            dicom_count=dicom_count,
        )

    # If we have a cached result from a previous run this session, show the success card
    _cp_result = get_cached_result("cp")
    if _cp_result is not None and st.session_state.get("cp_machine") == machine_key:
        _render_success_card(
            result=_cp_result,
            xlsx_path=st.session_state.get("cp_xlsx_path"),
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
    cp_defaults = config.cp_defaults
    machine = config.machines[machine_key]
    try:
        with st.spinner("Running CatPhan 504 analysis..."):
            result = run_cbct_analysis_cached(
                machine_id=machine_key,
                runfolder_path=str(runfolder),
                hu_tolerance=cp_defaults.hu_tolerance,
                scaling_tolerance=cp_defaults.scaling_tolerance,
                slice_thickness_tolerance=cp_defaults.slice_thickness_tolerance,
                thickness_slice_straddle=cp_defaults.thickness_slice_straddle,
                x_adjustment=cp_defaults.x_adjustment,
                y_adjustment=cp_defaults.y_adjustment,
                angle_adjustment=cp_defaults.angle_adjustment,
                roi_size_factor=cp_defaults.roi_size_factor,
                scaling_factor=cp_defaults.scaling_factor,
                minimum_rois_seen=cp_defaults.minimum_rois_seen,
                dicom_file_count=dicom_count,
                runfolder_mtime=runfolder_mtime(runfolder),
                expected_hu_values=cp_defaults.expected_hu_values,
            )
            xlsx_path = write_cbct_session_output(
                result=result,
                output_root=Path(config.output.root),
                template_path=template_path,
                machine_display_name=machine.display_name,
                category=config.output.category,
                pylinac_subfolder=config.output.pylinac_subfolder,
            )
        # Store in session state for success card + hand-off
        set_cached_result("cp", result)
        st.session_state["cp_xlsx_path"] = str(xlsx_path)
        st.session_state["cp_machine"] = machine_key
        st.rerun()

    except Exception:
        logging.exception("CatPhan analysis failed in Simple mode")
        summary = _safe_error_message()
        st.error(f"Analysis failed: {summary}. Switch to Advanced mode to debug.")


def _render_machine_dropdown(config: AppConfig) -> str | None:
    """6.1 Sidebar machine dropdown — filtered to catphan-configured machines."""
    machine_keys = config.machine_keys_for_module("catphan")
    if not machine_keys:
        st.warning("No machines have CatPhan configured. Edit machines.yaml and reload.")
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
    result: CatPhanAnalysisResult,
    xlsx_path: str | None,
    template_path: Path,
    config: AppConfig,
) -> None:
    """6.4 Success card with metrics + hand-off button."""
    st.success("Analysis complete!")

    if xlsx_path:
        st.write(f"**Output:** `{xlsx_path}`")

    # Four pass/fail flags
    flags = [
        ("HU Linearity", "hu_linearity_passed"),
        ("Geometry", "geometry_passed"),
        ("Uniformity", "uniformity_passed"),
        ("Thickness", "thickness_passed"),
    ]
    for label, key in flags:
        passed = bool(result.summary.get(key, False))
        badge = "[PASS]" if passed else "[FAIL]"
        st.write(f"**{label}:** {badge}")

    lcv = result.summary.get("low_contrast_visibility", "?")
    st.write(f"**Low Contrast Visibility:** {lcv}")

    # 6.6 Hand-off to Advanced mode
    if st.button("View in Advanced mode"):
        set_cached_result("cp", result)
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
    if "phantom" in msg.lower() or "localiz" in msg.lower():
        return (
            "could not localise the phantom. Check phantom positioning or switch to Advanced mode."
        )
    if "DICOM" in msg or "dicom" in msg:
        return "could not read DICOM images. Check the runfolder."
    if "write" in msg.lower() or "permission" in msg.lower():
        return "cannot write to the output directory. Contact physics IT."
    return f"{type_name}: {msg[:80]}"


# ---------------------------------------------------------------------------
# Advanced mode
# ---------------------------------------------------------------------------


def _render_advanced(config: AppConfig, template_path: Path) -> None:
    """Advanced mode: sidebar params + 5 tabs."""
    st.header("CatPhan 504 — Advanced Mode")

    # 7.8 Hand-off reception: if cp_result is set, use it; don't re-run
    result: CatPhanAnalysisResult | None = get_cached_result("cp")
    machine_key = st.session_state.get("cp_machine")

    if result is None or machine_key is None:
        # No hand-off — need to run analysis first via sidebar
        st.info("No analysis result yet. Run analysis from the sidebar.")
        machine_key, result = _advanced_initial_run(config, template_path)
        if result is None:
            return

    # 7.1 Advanced sidebar with params + buttons
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

    # Render the 5 tabs
    tab_overview, tab_ctp404, tab_ctp486, tab_ctp528, tab_ctp515 = st.tabs(
        ["Overview", "CTP404", "CTP486", "CTP528", "CTP515"]
    )

    with tab_overview:
        _render_overview_tab(result)
    with tab_ctp404:
        _render_ctp404_tab(result)
    with tab_ctp486:
        _render_ctp486_tab(result)
    with tab_ctp528:
        _render_ctp528_tab(result)
    with tab_ctp515:
        _render_ctp515_tab(result)


def _advanced_initial_run(
    config: AppConfig, template_path: Path
) -> tuple[str | None, CatPhanAnalysisResult | None]:
    """Run an initial analysis from the sidebar if no hand-off result exists."""
    machine_key = _render_machine_dropdown(config)
    if machine_key is None:
        return None, None

    machine = config.machines[machine_key]
    cp_defaults = config.cp_defaults
    dicom_root = Path(machine.dicom_roots["catphan"])

    from core.runfolder import list_runfolders

    runfolders = list_runfolders(dicom_root)
    runfolder: Path | None = None

    if runfolders:
        folder_labels = [p.name for p in runfolders]
        selected_label = st.sidebar.selectbox(
            "Runfolder",
            options=folder_labels,
            index=0,
            key="cp_runfolder_select",
        )
        runfolder = runfolders[folder_labels.index(selected_label)]
    else:
        st.sidebar.warning(f"No runfolders found under `{dicom_root}`.")

    if runfolder is None:
        st.error("No runfolder selected.")
        return machine_key, None

    dicom_count = count_dicoms(runfolder)
    st.info(f"Will analyze: `{runfolder}` ({dicom_count} DICOMs)")

    if st.sidebar.button("Run analysis", type="primary"):
        try:
            with st.spinner("Running CatPhan 504 analysis..."):
                result = run_cbct_analysis_cached(
                    machine_id=machine_key,
                    runfolder_path=str(runfolder),
                    hu_tolerance=cp_defaults.hu_tolerance,
                    scaling_tolerance=cp_defaults.scaling_tolerance,
                    slice_thickness_tolerance=cp_defaults.slice_thickness_tolerance,
                    thickness_slice_straddle=cp_defaults.thickness_slice_straddle,
                    x_adjustment=cp_defaults.x_adjustment,
                    y_adjustment=cp_defaults.y_adjustment,
                    angle_adjustment=cp_defaults.angle_adjustment,
                    roi_size_factor=cp_defaults.roi_size_factor,
                    scaling_factor=cp_defaults.scaling_factor,
                    minimum_rois_seen=cp_defaults.minimum_rois_seen,
                    dicom_file_count=dicom_count,
                    runfolder_mtime=runfolder_mtime(runfolder),
                    expected_hu_values=cp_defaults.expected_hu_values,
                )
            set_cached_result("cp", result)
            st.session_state["cp_machine"] = machine_key
            st.rerun()
        except Exception:
            logging.exception("CatPhan analysis failed in Advanced mode")
            # 7.11 Full errors surfaced inline in Advanced mode
            import traceback

            st.error("Analysis failed. Full traceback:")
            st.code(traceback.format_exc())

    return machine_key, None


def _render_advanced_sidebar(config: AppConfig, result: CatPhanAnalysisResult) -> dict:
    """7.1 Render sidebar with 10 scalar analyze params (NO tolerance widget)."""
    cp_defaults = config.cp_defaults
    base_params = result.params_used if result else {}

    st.sidebar.markdown("---")
    st.sidebar.subheader("Analysis Parameters")

    params: dict = {}
    params["hu_tolerance"] = st.sidebar.number_input(
        "HU tolerance",
        min_value=0.0,
        value=float(base_params.get("hu_tolerance", cp_defaults.hu_tolerance)),
        step=1.0,
    )
    params["scaling_tolerance"] = st.sidebar.number_input(
        "Scaling tolerance (mm)",
        min_value=0.0,
        value=float(base_params.get("scaling_tolerance", cp_defaults.scaling_tolerance)),
        step=0.1,
    )
    params["slice_thickness_tolerance"] = st.sidebar.number_input(
        "Slice thickness tolerance (mm)",
        min_value=0.0,
        value=float(
            base_params.get("slice_thickness_tolerance", cp_defaults.slice_thickness_tolerance)
        ),
        step=0.1,
    )
    # Straddle widget: 'auto' or 0-3
    straddle_options = ["auto", "0", "1", "2", "3"]
    current_straddle = str(
        base_params.get("thickness_slice_straddle", cp_defaults.thickness_slice_straddle)
    )
    straddle_idx = (
        straddle_options.index(current_straddle) if current_straddle in straddle_options else 0
    )
    selected_straddle = st.sidebar.selectbox(
        "Thickness slice straddle",
        options=straddle_options,
        index=straddle_idx,
    )
    params["thickness_slice_straddle"] = (
        "auto" if selected_straddle == "auto" else int(selected_straddle)
    )
    params["x_adjustment"] = st.sidebar.number_input(
        "X adjustment (mm)",
        value=float(base_params.get("x_adjustment", cp_defaults.x_adjustment)),
        step=0.1,
    )
    params["y_adjustment"] = st.sidebar.number_input(
        "Y adjustment (mm)",
        value=float(base_params.get("y_adjustment", cp_defaults.y_adjustment)),
        step=0.1,
    )
    params["angle_adjustment"] = st.sidebar.number_input(
        "Angle adjustment (deg)",
        value=float(base_params.get("angle_adjustment", cp_defaults.angle_adjustment)),
        step=0.1,
    )
    params["roi_size_factor"] = st.sidebar.number_input(
        "ROI size factor",
        min_value=0.1,
        value=float(base_params.get("roi_size_factor", cp_defaults.roi_size_factor)),
        step=0.1,
    )
    params["scaling_factor"] = st.sidebar.number_input(
        "Scaling factor",
        min_value=0.1,
        value=float(base_params.get("scaling_factor", cp_defaults.scaling_factor)),
        step=0.1,
    )
    params["minimum_rois_seen"] = st.sidebar.number_input(
        "Minimum ROIs seen",
        min_value=0,
        value=int(base_params.get("minimum_rois_seen", cp_defaults.minimum_rois_seen)),
        step=1,
    )

    return params


def _handle_rerun(
    *,
    config: AppConfig,
    template_path: Path,
    machine_key: str,
    params: dict,
    prev_result: CatPhanAnalysisResult,
) -> CatPhanAnalysisResult | None:
    """7.9 Re-run analysis handler — invalidates cp_obj, calls cached run."""
    invalidate("cp", suffixes=("obj",))

    runfolder = Path(prev_result.runfolder_path)
    dicom_count = count_dicoms(runfolder)

    try:
        with st.spinner("Running CatPhan 504 analysis..."):
            result = run_cbct_analysis_cached(
                machine_id=machine_key,
                runfolder_path=str(runfolder),
                hu_tolerance=params["hu_tolerance"],
                scaling_tolerance=params["scaling_tolerance"],
                slice_thickness_tolerance=params["slice_thickness_tolerance"],
                thickness_slice_straddle=params["thickness_slice_straddle"],
                x_adjustment=params["x_adjustment"],
                y_adjustment=params["y_adjustment"],
                angle_adjustment=params["angle_adjustment"],
                roi_size_factor=params["roi_size_factor"],
                scaling_factor=params["scaling_factor"],
                minimum_rois_seen=params["minimum_rois_seen"],
                dicom_file_count=dicom_count,
                runfolder_mtime=runfolder_mtime(runfolder),
                expected_hu_values=config.cp_defaults.expected_hu_values,
            )
    except Exception:
        logging.exception("CatPhan re-run failed in Advanced mode")
        # 7.11 Full errors surfaced inline in Advanced mode
        import traceback

        st.error("Analysis failed. Full traceback:")
        st.code(traceback.format_exc())
        return prev_result

    # Detect cache short-circuit
    if result == prev_result:
        st.info("Result loaded from cache (parameters unchanged)")
    else:
        set_cached_result("cp", result)
    return result


def _handle_download(
    *,
    result: CatPhanAnalysisResult,
    config: AppConfig,
    template_path: Path,
) -> None:
    """7.10 Download xlsx handler."""
    machine = config.machines.get(result.machine_id)
    display_name = machine.display_name if machine else result.machine_id
    xlsx_path = write_cbct_session_output(
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


def _get_cp_obj(result: CatPhanAnalysisResult):  # type: ignore[no-untyped-def]
    """7.7 Lazily initialise the pylinac CatPhan504 object in session_state."""
    obj = get_cached_obj("cp")
    if obj is None:
        try:
            cp_obj = load_cbct_object(result.runfolder_path, result.params_used)
            set_cached_obj("cp", cp_obj)
            return cp_obj
        except Exception:
            logger.exception("Failed to load CatPhan object for plot overlays")
            return None
    return obj


def _render_overview_tab(result: CatPhanAnalysisResult) -> None:
    """7.2 Overview tab — summary metrics + pass/fail flags + montage."""
    import pandas as pd

    # Show session metadata
    st.write(
        f"**Machine:** {result.summary.get('machine_name', '?')}  |  "
        f"**Date:** {result.summary.get('session_date', '?')}  |  "
        f"**Images:** {result.summary.get('num_images', '?')}"
    )

    # Build dataframe of summary metrics (excluding metadata)
    meta_fields = {"machine_name", "session_date", "num_images"}
    flag_fields = {
        "hu_linearity_passed",
        "geometry_passed",
        "uniformity_passed",
        "thickness_passed",
    }
    rows = []
    for name in result.summary:
        if name in meta_fields:
            continue
        value = result.summary[name]
        status = ""
        if name in flag_fields:
            passed = bool(value)
            status = "[PASS]" if passed else "[FAIL]"
        rows.append({"Metric": name, "Value": value, "Status": status})

    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    # "Analysed with" summary line
    params = result.params_used
    param_str = ", ".join(f"{k}={v}" for k, v in sorted(params.items()) if v is not None)
    st.caption(f"Analysed with: {param_str}")

    # Montage figure
    cp_obj = _get_cp_obj(result)
    if cp_obj is not None:
        try:
            import matplotlib.pyplot as plt

            fig = cp_obj.plot_analyzed_image()
            if fig is not None:
                st.pyplot(fig, use_container_width=True)
                plt.close(fig)
        except Exception:
            logger.exception("Failed to render montage")
            st.warning("Could not render the analyzed image montage.")


def _render_ctp404_tab(result: CatPhanAnalysisResult) -> None:
    """7.3 CTP404 tab — HU linearity sub-image + ROIs table + geometry + thickness."""
    import pandas as pd

    # Sub-image
    cp_obj = _get_cp_obj(result)
    if cp_obj is not None:
        try:
            import matplotlib.pyplot as plt

            fig = cp_obj.plot_analyzed_subimage("linearity")
            if fig is not None:
                st.pyplot(fig, use_container_width=True)
                plt.close(fig)
        except Exception:
            logger.exception("Failed to render CTP404 sub-image")
            st.warning("Could not render the HU linearity sub-image.")

    # HU ROIs table (7 materials)
    hu_rois = result.ctp404.get("hu_rois", {})
    roi_rows = []
    for _name, roi in sorted(hu_rois.items()):
        roi_rows.append(
            {
                "Material": roi.get("name", _name),
                "Nominal": roi.get("nominal_value"),
                "Measured": roi.get("value"),
                "Difference": roi.get("difference"),
                "Stdev": roi.get("stdev"),
                "Passed": roi.get("passed"),
            }
        )
    if roi_rows:
        st.dataframe(pd.DataFrame(roi_rows), use_container_width=True)

    # Geometry summary
    st.write(f"**Avg line distance:** {result.ctp404.get('avg_line_distance_mm', '?')} mm")
    line_distances = result.ctp404.get("line_distances_mm", [])
    for i, dist in enumerate(line_distances):
        st.write(f"&nbsp;&nbsp;Line {i + 1}: {dist} mm", unsafe_allow_html=True)

    # Thickness info
    st.write(
        f"**Measured slice thickness:** {result.ctp404.get('measured_slice_thickness_mm', '?')} mm"
    )
    st.write(f"**Num slices combined:** {result.ctp404.get('thickness_num_slices_combined', '?')}")


def _render_ctp486_tab(result: CatPhanAnalysisResult) -> None:
    """7.4 CTP486 tab — uniformity sub-image + ROIs table + indices + NPS."""
    import pandas as pd

    # Sub-image
    cp_obj = _get_cp_obj(result)
    if cp_obj is not None:
        try:
            import matplotlib.pyplot as plt

            fig = cp_obj.plot_analyzed_subimage("uniformity")
            if fig is not None:
                st.pyplot(fig, use_container_width=True)
                plt.close(fig)
        except Exception:
            logger.exception("Failed to render CTP486 sub-image")
            st.warning("Could not render the uniformity sub-image.")

    # Uniformity ROIs table (5 regions)
    rois = result.ctp486.get("rois", {})
    roi_rows = []
    for _name, roi in sorted(rois.items()):
        roi_rows.append(
            {
                "Region": roi.get("name", _name),
                "Value": roi.get("value"),
                "Nominal": roi.get("nominal_value"),
                "Difference": roi.get("difference"),
                "Stdev": roi.get("stdev"),
                "Passed": roi.get("passed"),
            }
        )
    if roi_rows:
        st.dataframe(pd.DataFrame(roi_rows), use_container_width=True)

    # Uniformity indices
    st.write(f"**Uniformity index:** {result.ctp486.get('uniformity_index', '?')}")
    st.write(f"**Integral non-uniformity:** {result.ctp486.get('integral_non_uniformity', '?')}")

    # NPS summary
    st.write(f"**NPS avg power:** {result.ctp486.get('nps_avg_power', '?')}")
    st.write(f"**NPS max freq:** {result.ctp486.get('nps_max_freq', '?')}")


def _render_ctp528_tab(result: CatPhanAnalysisResult) -> None:
    """7.5 CTP528 tab — spatial resolution sub-image + Plotly MTF curve + MTF table."""
    import pandas as pd
    import plotly.graph_objects as go

    # Sub-image
    cp_obj = _get_cp_obj(result)
    if cp_obj is not None:
        try:
            import matplotlib.pyplot as plt

            fig = cp_obj.plot_analyzed_subimage("rmtf")
            if fig is not None:
                st.pyplot(fig, use_container_width=True)
                plt.close(fig)
        except Exception:
            logger.exception("Failed to render CTP528 sub-image")
            st.warning("Could not render the spatial resolution sub-image.")

    # Plotly MTF curve
    curve = result.mtf_curve
    if curve.get("x"):
        fig_mtf = go.Figure(
            data=go.Scatter(
                x=curve["x"],
                y=curve["y"],
                mode="lines+markers",
                hovertemplate="%{x}% MTF: %{y:.3f} lp/mm<extra></extra>",
            )
        )
        fig_mtf.update_layout(
            title="MTF Curve",
            xaxis_title="MTF (%)",
            yaxis_title="Resolution (lp/mm)",
        )
        st.plotly_chart(fig_mtf, use_container_width=True)

    # MTF table (9 rows)
    mtf_lp_mm = result.ctp528.get("mtf_lp_mm", {})
    mtf_rows = []
    for pct in range(10, 91, 10):
        mtf_rows.append({"MTF (%)": pct, "lp/mm": mtf_lp_mm.get(str(pct), "?")})
    st.dataframe(pd.DataFrame(mtf_rows), use_container_width=True)


def _render_ctp515_tab(result: CatPhanAnalysisResult) -> None:
    """7.6 CTP515 tab — low contrast sub-image + ROI table + num_rois_seen."""
    import pandas as pd

    # Sub-image
    cp_obj = _get_cp_obj(result)
    if cp_obj is not None:
        try:
            import matplotlib.pyplot as plt

            fig = cp_obj.plot_analyzed_subimage("low_contrast")
            if fig is not None:
                st.pyplot(fig, use_container_width=True)
                plt.close(fig)
        except Exception:
            logger.exception("Failed to render CTP515 sub-image")
            st.warning("Could not render the low contrast sub-image.")

    # ROI table (variable rows)
    roi_results = result.ctp515.get("roi_results", {})
    roi_rows = []
    for _key, roi in sorted(roi_results.items()):
        roi_rows.append(
            {
                "ROI": _key,
                "Contrast": roi.get("contrast"),
                "CNR": roi.get("cnr"),
                "SNR": roi.get("signal to noise"),
                "Visibility": roi.get("visibility"),
                "Threshold": roi.get("visibility threshold"),
                "Passed": roi.get("passed visibility"),
            }
        )
    if roi_rows:
        st.dataframe(pd.DataFrame(roi_rows), use_container_width=True)

    st.write(f"**ROIs seen:** {result.ctp515.get('num_rois_seen', '?')}")


# ---------------------------------------------------------------------------
# Page entry point (executed when Streamlit loads this page script)
_config = st.session_state.get("wl_config")
_template = st.session_state.get("cp_template_path", "templates/catphan_504.xltx")
if _config is not None:
    render(_config, Path(_template))
else:
    st.warning("Configuration not loaded. Return to the home page to initialise.")
