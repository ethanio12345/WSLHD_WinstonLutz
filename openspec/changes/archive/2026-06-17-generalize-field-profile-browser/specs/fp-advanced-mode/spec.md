## MODIFIED Requirements

### Requirement: Overview tab

The Overview tab SHALL show a summary table of all 29 metrics, the protocol name, FFF status, and the "Analysed with" parameters summary line.

#### Scenario: Overview tab content

- **WHEN** the Overview tab renders
- **THEN** it SHALL show a summary table (all metrics), the protocol, FFF status, and an "Analysed with: ..." caption listing all params

### Requirement: Profiles tab

The Profiles tab SHALL show vertical and horizontal profile plots.

#### Scenario: Profile plots render

- **WHEN** the Profiles tab renders
- **THEN** Plotly line charts for vertical + horizontal profiles SHALL render from `vert_profile_values` / `horiz_profile_values` (downsampled to ~500 points)

### Requirement: Field Map tab

The Field Map tab SHALL show the 2D analyzed image via a lazily-initialised pylinac FieldAnalysis object.

#### Scenario: Field map renders (lazy fp_obj)

- **WHEN** the Field Map tab renders
- **THEN** `fa.plot_analyzed_image()` SHALL render as a matplotlib figure via a lazily-initialised `fp_obj` in session_state

#### Scenario: Lazy fp_obj invalidation on re-run

- **GIVEN** an existing `fp_obj` in session_state
- **WHEN** "Re-run analysis" is clicked with changed parameters
- **THEN** the cached `fp_obj` SHALL be invalidated (it no longer matches the new params)

### Requirement: ROI & Penumbra tab

The ROI & Penumbra tab SHALL show the central ROI statistics, penumbra values, and slopes in tabular form.

#### Scenario: ROI tab content

- **WHEN** the ROI & Penumbra tab renders
- **THEN** it SHALL show central ROI stats (Mean/Max/Min/Std), a penumbra table (Top/Bottom/Left/Right), and a slopes table

## REMOVED Requirements

### Requirement: Field profile Advanced mode sidebar

Replaced by "Field profile Advanced mode page" (broadened to include the shared folder browser; the sidebar params are now one aspect of the page requirement).

### Requirement: Re-run analysis

Replaced by "Re-run with changed parameters" (renamed for clarity; same behavior).

### Requirement: Download xlsx

Replaced by "Download (in-browser, no server write)" — the old requirement wrote to `<machine.output_root>/FP/...`; the new one serves bytes in-browser with no server write.

### Requirement: Full errors surfaced inline

Replaced by "Full errors inline" (renamed; same behavior).

### Requirement: Lazy field_analysis object

Replaced by "Folder browser shared with Simple mode" — the lazy-init behavior is now captured as a scenario under the Field Map tab (MODIFIED above); the new requirement documents the shared folder browser instead.

## ADDED Requirements

### Requirement: Field profile Advanced mode page

The Field Profile page SHALL provide an Advanced mode with a sidebar of all pylinac `FieldAnalysis.analyze()` parameters and four tabs (Overview, Profiles, Field Map, ROI & Penumbra). The folder browser is shared with Simple mode (same cascading selectboxes). (Hand-off from Simple mode is the primary entry; a direct run from the sidebar is also supported.)

#### Scenario: Advanced sidebar params repopulated

- **GIVEN** a result handed off from Simple mode (or a direct Advanced run)
- **WHEN** the Advanced sidebar renders
- **THEN** each scalar analyze parameter SHALL be repopulated from `result.params_used`
- **AND** an "Force FFF analysis" checkbox SHALL be pre-checked from the detected value

#### Scenario: All scalar parameters available

- **WHEN** the Advanced sidebar renders
- **THEN** the following SHALL be present: Protocol, Centering, In-field ratio, Penumbra (lower/upper), Vertical/Horizontal position, Vertical/Horizontal width, Interpolation, Edge detection method, Slope exclusion ratio, Edge smoothing ratio, Hill window ratio, Force FFF checkbox

### Requirement: Re-run with changed parameters

The Re-run analysis button SHALL call the cached analysis function with the current sidebar parameters.

#### Scenario: Re-run produces new result

- **GIVEN** a result in Advanced mode
- **WHEN** a parameter is changed and "Re-run analysis" is clicked
- **THEN** the analysis SHALL re-run with the new parameters
- **AND** all tabs SHALL refresh with the new result

### Requirement: Download (in-browser, no server write)

The Download xlsx button SHALL serve the xlsx in-browser via `st.download_button` using in-memory bytes. No file SHALL be written to any server-side output directory.

#### Scenario: Download xlsx serves bytes

- **WHEN** "Download xlsx" is clicked in Advanced mode
- **THEN** the browser SHALL download a `<IMAGE_STEM>.xlsx` (30 named cells + 4 data sheets)
- **AND** no file SHALL be written to any server-side output directory

### Requirement: Full errors inline

Advanced mode SHALL show full tracebacks for analysis failures, unlike Simple mode which shows only user-friendly messages.

#### Scenario: Advanced error display

- **GIVEN** an analysis failure in Advanced mode (initial run or re-run)
- **WHEN** the failure occurs
- **THEN** the full traceback SHALL be shown inline (Advanced mode is for debugging)

### Requirement: Folder browser shared with Simple mode

The Advanced mode SHALL use the same cascading selectbox folder browser as Simple mode (D1). When a result is handed off from Simple mode, the browser state SHALL reflect the folder/image that produced the result.

#### Scenario: Hand-off preserves browser context

- **GIVEN** a Simple mode analysis of `/data/LA2/FieldProfile/6MV_10x10.dcm`
- **WHEN** "View in Advanced mode" is clicked
- **THEN** the Advanced folder browser SHALL show the same folder/image selected
- **AND** the result SHALL display without re-running
