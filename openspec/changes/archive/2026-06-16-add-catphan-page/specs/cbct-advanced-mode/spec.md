## ADDED Requirements

### Requirement: Sidebar of pylinac analyze() parameters

Advanced mode SHALL expose a sidebar with widgets for every **scalar** `pylinac.CatPhan504.analyze()` parameter that affects the result: `hu_tolerance`, `scaling_tolerance`, `slice_thickness_tolerance`, `thickness_slice_straddle`, `x_adjustment`, `y_adjustment`, `angle_adjustment`, `roi_size_factor`, `scaling_factor`, `minimum_rois_seen`. Widget defaults SHALL match the values from `analysis_defaults.catphan`, or pylinac defaults if not configured. The dict-typed `expected_hu_values` parameter is NOT surfaced in the sidebar (config-only) — it's a dict and not amenable to a single widget.

#### Scenario: All scalar parameters available

- **WHEN** Advanced mode is rendered
- **THEN** the sidebar contains widgets for all 10 scalar parameters listed above, plus a "Re-run analysis" button and a "Download xlsx" button. No separate UI tolerance widget is present — CatPhan's pass/fail signal is the four pylinac-computed flags displayed on the Overview tab.

#### Scenario: Straddle widget accepts auto or integer

- **WHEN** the `thickness_slice_straddle` widget is rendered
- **THEN** it offers `'auto'` and integer options `0`, `1`, `2`, `3` (per pylinac API); selecting `'auto'` passes the string `'auto'` to `analyze()`

### Requirement: Re-run with adjusted parameters

Clicking "Re-run analysis" SHALL invoke pylinac's `analyze()` via the cached `run_cbct_analysis` function — with the actual execution gated by `@st.cache_data` (so identical inputs short-circuit to the cached result). The previous `CatPhanAnalysisResult` and `st.session_state["cp_obj"]` SHALL be invalidated before the new run begins (when the cache misses).

#### Scenario: Parameter change triggers re-run

- **WHEN** the user changes `hu_tolerance` from 40 to 35 and clicks "Re-run analysis"
- **THEN** a spinner shows "Running CatPhan 504 analysis..." and on completion the Overview and per-CTP tabs all reflect the new result

#### Scenario: Same parameters, click re-run

- **WHEN** the user clicks "Re-run analysis" without changing any parameter AND the underlying DICOM set is unchanged (same `dicom_file_count` and `runfolder_mtime`)
- **THEN** `@st.cache_data` short-circuits — the cached `CatPhanAnalysisResult` is returned, no analysis spinner appears, and the UI briefly notes "Result loaded from cache (parameters unchanged)"

### Requirement: Overview tab

The Overview tab SHALL display a static table of all aggregate pass/fail flags (`hu_linearity_passed`, `geometry_passed`, `uniformity_passed`, `thickness_passed`) and the primary summary metrics (`low_contrast_visibility`, `measured_slice_thickness_mm`, `avg_line_distance_mm`, `uniformity_index`, `integral_non_uniformity`, `mtf_50_lp_mm`, `nps_avg_power`, `catphan_roll_deg`, `num_rois_seen`). Pass/fail annotation SHALL be applied to the four flags only; all numeric metrics are displayed as values without pass/fail status. The tab SHALL also show a "Analysed with: hu_tolerance=40, scaling_tolerance=0.5, ..." summary line sourced from `params_used`, and SHALL include the pylinac montage figure (`cbct.plot_analyzed_image()` rendered via `st.pyplot`).

#### Scenario: All flags displayed

- **WHEN** the Overview tab renders
- **THEN** all four pass/fail flags are visible with their boolean status; the numeric metrics are shown as values

#### Scenario: Pass/fail annotation on flags

- **WHEN** `hu_linearity_passed = False` (others True)
- **THEN** the `hu_linearity_passed` row shows `[FAIL]` in red; the other three flag rows show `[PASS]` in green

#### Scenario: Montage figure rendered

- **WHEN** the Overview tab renders
- **THEN** the pylinac `plot_analyzed_image()` figure appears as a static `st.pyplot`, showing all four CTP modules in a single image

### Requirement: CTP404 tab

The CTP404 tab SHALL display: the HU linearity sub-image (`cbct.plot_analyzed_subimage('linearity')`), the HU ROIs table (7 rows for the 7 materials × columns: name, nominal, measured, difference, stdev, passed), the geometry summary (avg line distance + 4 individual line distances), and the slice thickness info (measured, num_slices_combined, straddle used).

#### Scenario: HU linearity table

- **WHEN** the CTP404 tab renders
- **THEN** a 7-row table appears with columns: material name (Air, PMP, LDPE, Poly, Acrylic, Delrin, Teflon), nominal HU, measured HU, difference, stdev, passed (boolean)

#### Scenario: Sub-image rendered

- **WHEN** the CTP404 tab renders
- **THEN** the HU linearity sub-image (matplotlib via `st.pyplot`) appears above the table

### Requirement: CTP486 tab

The CTP486 tab SHALL display: the uniformity sub-image (`cbct.plot_analyzed_subimage('uniformity')`), the uniformity ROIs table (5 rows: Top, Right, Bottom, Left, Center × columns: region name, value, nominal, difference, stdev, passed), the uniformity indices (uniformity_index, integral_non_uniformity), and the NPS summary (avg_power, max_freq) plus an NPS plot.

#### Scenario: Uniformity table

- **WHEN** the CTP486 tab renders
- **THEN** a 5-row table appears with columns: region name (Top, Right, Bottom, Left, Center), value (HU), nominal, difference, stdev, passed

#### Scenario: NPS plot rendered

- **WHEN** the CTP486 tab renders
- **THEN** the NPS plot (matplotlib via `st.pyplot`, equivalent to `cbct.ctp486.plot_noise_power_spectrum()`) appears below the table

### Requirement: CTP528 tab

The CTP528 tab SHALL display: the spatial resolution sub-image (`cbct.plot_analyzed_subimage('rmtf')`), an interactive MTF curve plot via Plotly (x = lp/mm, y = relative MTF, with hover tooltips), and the MTF table (9 rows: 10% to 90% in steps of 10, with lp/mm values).

#### Scenario: MTF curve interactive

- **WHEN** the CTP528 tab renders
- **THEN** a Plotly line chart appears with lp/mm on x-axis and relative MTF on y-axis; hovering a point shows the percentage and lp/mm value

#### Scenario: MTF table

- **WHEN** the CTP528 tab renders
- **THEN** a 9-row table appears below the chart with columns: percentage (10, 20, ..., 90), lp/mm value

### Requirement: CTP515 tab

The CTP515 tab SHALL display: the low contrast sub-image, the per-ROI table (variable rows: per-ROI size, contrast, CNR, SNR, visibility, visibility threshold, passed-visibility), and the `num_rois_seen` summary line.

#### Scenario: ROI table variable rows

- **WHEN** the CTP515 tab renders
- **THEN** a table appears with one row per low-contrast ROI that pylinac evaluated; columns include size, contrast, CNR, SNR, visibility, visibility threshold, passed visibility

### Requirement: Full errors surfaced in Advanced mode

Contrasting with Simple mode's hidden-traceback posture, Advanced mode SHALL surface full pylinac errors and tracebacks inline when analysis fails. The intended audience is a physicist doing service investigation who needs the technical detail.

#### Scenario: pylinac error shown inline

- **WHEN** the user clicks "Re-run analysis" and pylinac raises an exception (e.g. phantom not localised)
- **THEN** the full exception type, message, and traceback are rendered inline in the Advanced mode UI (not just a one-line summary); a "Adjust parameters and re-run" prompt appears

### Requirement: xlsx download

The Advanced mode sidebar SHALL include a "Download xlsx" button that produces the same paired xltx+xlsx output as Simple mode, using the current `CatPhanAnalysisResult` and writing to the same per-session output folder. The button SHALL also return a download link to the user's browser.

#### Scenario: Download after re-run

- **WHEN** the user re-runs analysis with `hu_tolerance=35` and clicks "Download xlsx"
- **THEN** the xlsx at the session folder is overwritten with the new result, paired with a fresh xltx copy, and a browser download begins

### Requirement: Hand-off reception from Simple mode

When Advanced mode is entered via Simple mode's "View in Advanced mode" button, the system SHALL read `st.session_state["cp_result"]` and render the Overview tab immediately. The sidebar parameter widgets SHALL be populated from `params_used`, not from config defaults.

#### Scenario: Hand-off does not re-run

- **WHEN** Advanced mode renders after a hand-off
- **THEN** no analysis runs; the Overview tab shows the Simple mode result within 1 second

#### Scenario: Sidebar reflects Simple params

- **WHEN** Simple mode ran with default `hu_tolerance=40` and the user hand-offs to Advanced
- **THEN** the sidebar `hu_tolerance` widget shows `40`, not whatever the Advanced default would have been

### Requirement: Lazy cbct object initialisation

The pylinac `CatPhan504` object is not picklable in all cases and is not stored in `@st.cache_data`. The Advanced mode SHALL lazily initialise `st.session_state["cp_obj"]` on first render that needs `cbct.plot_analyzed_image()` or `cbct.plot_analyzed_subimage()`. Subsequent tab switches within the same Advanced session SHALL NOT re-trigger DICOM loading.

#### Scenario: First overlay render triggers init

- **WHEN** the user first visits a tab requiring `cbct.plot_analyzed_subimage()` (e.g. CTP404)
- **THEN** `st.session_state["cp_obj"]` is lazily initialised from `CatPhanAnalysisResult.runfolder_path` + params — a one-time load per Advanced session

#### Scenario: Tab switching does not reload

- **WHEN** the user switches between CTP404, CTP486, CTP528, CTP515 tabs after the first overlay render
- **THEN** the `cp_obj` is already populated; no DICOM-loading spinner appears
