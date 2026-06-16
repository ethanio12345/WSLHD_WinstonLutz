## Purpose

Provide interactive Winston-Lutz exploration for service investigations. Physicist can adjust pylinac `analyze()` parameters, re-run, and drill into per-image metrics, plotly plots, and detection overlays. Includes a UI-only pass/fail tolerance display.

## Requirements

### Requirement: Sidebar of pylinac analyze() parameters

Advanced mode SHALL expose a sidebar with widgets for every `pylinac.WinstonLutz.analyze()` parameter that affects the result: `bb_size_mm`, `machine_scale`, `low_density_bb`, `open_field`, `apply_virtual_shift`, `snap_tolerance`, `gantry_reference`, `collimator_reference`, `couch_reference`. Widget defaults SHALL match the values from `machines.yaml`'s `analysis_defaults.winston_lutz` section, or pylinac defaults if not configured.

#### Scenario: All parameters available

- **WHEN** Advanced mode is rendered
- **THEN** the sidebar contains widgets for all 9 parameters listed above, plus a "Re-run analysis" button and a "Download xlsx" button

#### Scenario: Tolerance display is UI-only

- **WHEN** the user adjusts the tolerance widget in the sidebar
- **THEN** the Overview tab pass/fail status updates immediately (without re-running analysis), and `tolerance_mm` is NOT passed to pylinac's `analyze()` — it is a display-only filter

### Requirement: Re-run with adjusted parameters

Clicking "Re-run analysis" SHALL invoke pylinac's `analyze()` via the cached `run_wl_analysis` function — with the actual execution gated by `@st.cache_data` (so identical inputs short-circuit to the cached result; see "Same parameters, click re-run" scenario). The previous `WLAnalysisResult` and `st.session_state["wl_obj"]` SHALL be invalidated before the new run begins (when the cache misses).

#### Scenario: Parameter change triggers re-run

- **WHEN** the user changes `bb_size_mm` from 5.0 to 3.0 and clicks "Re-run analysis"
- **THEN** a spinner shows "Running Winston-Lutz analysis..." and on completion the Overview, Per-image, Plots, and Detection overlay tabs all reflect the new result

#### Scenario: Same parameters, click re-run

- **WHEN** the user clicks "Re-run analysis" without changing any parameter AND the underlying DICOM set is unchanged (same `dicom_file_count` and `runfolder_mtime`)
- **THEN** `@st.cache_data` short-circuits — the cached `WLAnalysisResult` is returned, no analysis spinner appears, and the UI briefly notes "Result loaded from cache (parameters unchanged)"

### Requirement: Overview tab

The Overview tab SHALL display a static table of all aggregate metrics from `WLAnalysisResult.summary`. Pass/fail annotation SHALL be applied to `max_2d_cax_to_bb` only (the single metric with a defensible single-threshold policy per design D7); all other metrics are displayed as values without pass/fail status. The tab SHALL also show a "Analysed with: bb_size=5.0mm, scale=VARIAN_IEC, ..." summary line sourced from `WLAnalysisResult.params_used`.

#### Scenario: All metrics displayed

- **WHEN** the Overview tab renders
- **THEN** all 21 metric values from `summary` are visible (excluding the 3 metadata fields `machine_name`, `session_date`, `num_total_images` which are shown as a header)

#### Scenario: Pass/fail annotation on primary metric

- **WHEN** `max_2d_cax_to_bb = 1.21mm` and `tolerance_mm = 1.0`
- **THEN** the `max_2d_cax_to_bb` row shows `[FAIL]` in red; no other row has a pass/fail marker

#### Scenario: Other iso metrics show value only

- **WHEN** `gantry_3d_iso = 0.55mm` and `coll_2d_iso = 0.27mm` and `couch_2d_iso = 0.19mm`
- **THEN** those rows display the values without pass/fail markers (per-metric tolerances are an explicit Open Question in the design, deferred to a future change)

### Requirement: Per-image tab with axis filter

The Per-image tab SHALL display a sortable, filterable table of per-image data from `WLAnalysisResult.image_details`, with columns: image key, variable axis, gantry angle, collimator angle, couch angle, `cax2bb_distance`, `cax2epid_distance`. The tab SHALL provide an axis filter (dropdown: `gantry | collimator | couch`) and a numeric input — when both are set, the table filters to images matching that axis value.

#### Scenario: No filter

- **WHEN** the Per-image tab renders with no filter set
- **THEN** all images are shown, sorted by image key ascending

#### Scenario: Filter by gantry=0

- **WHEN** the axis filter is set to `gantry` and the value is `0`
- **THEN** the table shows only images where `gantry_reference` is 0 (e.g. `G0B0P0`, `G0B45P0`, `G0B270P0`), regardless of collimator or couch angle

#### Scenario: View image from a row

- **WHEN** the user clicks the "View image" button next to a row
- **THEN** the corresponding detection-overlay image renders inline below the table (drawing on `st.session_state["wl_obj"].images[i].plot()`)

### Requirement: Plots tab with three Plotly charts

The Plots tab SHALL render three Plotly charts: (1) a scatter of `cax2bb_distance` vs gantry angle, (2) a scatter of BB X deviation vs Y deviation coloured by axis, (3) a histogram of `cax2bb_distance` across all images. All three SHALL be sourced from precomputed arrays in `WLAnalysisResult` (no recomputation at render time).

#### Scenario: Plots render from cached result

- **WHEN** the Plots tab is rendered
- **THEN** all three Plotly charts appear within 1 second of tab selection (no spinner)

#### Scenario: Hover for values

- **WHEN** the user hovers a point on the deviation-vs-gantry scatter
- **THEN** a tooltip shows the image key, gantry angle, and `cax2bb_distance` value

### Requirement: Detection overlay tab

The Detection overlay tab SHALL render a grid of `wl.images[i].plot()` figures (one per image) so the physicist can confirm at a glance that pylinac correctly identified the field CAX, BB, and EPID center in every image. Clicking an image SHALL open a `st.dialog` (Streamlit ≥1.33) with a full-size version.

#### Scenario: Grid renders all images

- **WHEN** the Detection overlay tab renders for a 17-image WL session
- **THEN** 17 matplotlib figures appear in a grid (suggested: 4 columns), each annotated with the image key

#### Scenario: First-time render triggers WL object init

- **WHEN** the Detection overlay tab is selected for the first time in an Advanced session
- **THEN** `st.session_state["wl_obj"]` is lazily initialised from `WLAnalysisResult.runfolder_path` + params — a one-time 5-30s load acceptable per the design's risk-mitigation posture. Subsequent tab switches within the same session do not re-trigger this load.

#### Scenario: Click for full-size view

- **WHEN** the user clicks an image in the grid
- **THEN** a `st.dialog` opens containing the same `wl.images[i].plot()` call rendered at default matplotlib size, with a close button

### Requirement: xlsx download

The Advanced mode sidebar SHALL include a "Download xlsx" button that produces the same paired xltx+xlsx output as Simple mode, using the current `WLAnalysisResult` and writing to the same per-session output folder. The button SHALL also return a download link to the user's browser.

#### Scenario: Download after re-run

- **WHEN** the user re-runs analysis with `bb_size_mm=3.0` and clicks "Download xlsx"
- **THEN** the xlsx at `/out/<MACHINE>/WL/<MACHINE>_WL_<RUNFOLDER>/` is overwritten with the new result, paired with a fresh xltx copy, and a browser download begins

### Requirement: Hand-off reception from Simple mode

When Advanced mode is entered via Simple mode's "View in Advanced mode" button, the system SHALL read `st.session_state["wl_result"]` and render the Overview tab immediately. The sidebar parameter widgets SHALL be populated from `WLAnalysisResult.params_used`, not from config defaults.

#### Scenario: Hand-off does not re-run

- **WHEN** Advanced mode renders after a hand-off
- **THEN** no analysis runs; the Overview tab shows the Simple mode result within 1 second

#### Scenario: Sidebar reflects Simple params

- **WHEN** Simple mode ran with default `bb_size_mm=5.0` and the user hand-offs to Advanced
- **THEN** the sidebar `bb_size_mm` widget shows `5.0`, not whatever the Advanced default would have been
