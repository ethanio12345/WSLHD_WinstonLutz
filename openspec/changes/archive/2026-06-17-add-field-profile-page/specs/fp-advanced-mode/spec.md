## Requirement: Field profile Advanced mode sidebar

Advanced mode SHALL expose pylinac `FieldAnalysis.analyze()` parameters in the sidebar, repopulated from the current result's `params_used`.

### Scenario: All scalar parameters available

- **GIVEN** Advanced mode with a cached result
- **THEN** the sidebar SHALL show: Protocol, Centering, In-Field Ratio, Penumbra (lower/upper), Vertical Position, Horizontal Position, Vertical Width, Horizontal Width, Interpolation, Edge Detection Method, Slope Exclusion Ratio, Edge Smoothing Ratio, Hill Window Ratio

### Scenario: FFF override checkbox

- **GIVEN** Advanced mode sidebar
- **THEN** a checkbox SHALL be present showing "Force FFF analysis" with the auto-detected value pre-checked/unchecked
- **AND** changing it SHALL affect the next Re-run

## Requirement: Overview tab

The Overview tab SHALL show a summary table of all 29 metrics, the protocol name, FFF status, and the "Analysed with" parameters summary line.

### Scenario: Overview tab content

- **GIVEN** a field profile result in Advanced mode
- **WHEN** the Overview tab is active
- **THEN** a table SHALL render with all 29 metric names and values
- **AND** a line SHALL show "Protocol: VARIAN", "FFF: Yes/No"
- **AND** a caption SHALL show "Analysed with: protocol=VARIAN, is_FFF=True, ..."

## Requirement: Profiles tab

The Profiles tab SHALL show vertical and horizontal profile plots with the flatness and symmetry calculation overlays.

### Scenario: Profile plots render

- **GIVEN** a field profile result in Advanced mode
- **WHEN** the Profiles tab is active
- **THEN** a Plotly line chart SHALL render showing the vertical profile (x=position mm, y=normalized dose)
- **AND** a second Plotly line chart SHALL render showing the horizontal profile
- **AND** both charts SHALL have hover tooltips

## Requirement: Field Map tab

The Field Map tab SHALL show the 2D analyzed image with edges, beam center, and CAX marked.

### Scenario: Field map renders

- **GIVEN** a field profile result and a lazily-loaded pylinac FieldAnalysis object
- **WHEN** the Field Map tab is active
- **THEN** the `plot_analyzed_image()` figure SHALL render as a matplotlib figure
- **AND** the figure SHALL show profile lines, edges, and center markers

## Requirement: ROI & Penumbra tab

The ROI & Penumbra tab SHALL show the central ROI statistics and penumbra values in tabular form.

### Scenario: ROI table

- **GIVEN** a field profile result in Advanced mode
- **WHEN** the ROI & Penumbra tab is active
- **THEN** a table SHALL render with: Central ROI Mean, Max, Min, Std
- **AND** a table SHALL render with penumbra for all 4 sides (Top, Bottom, Left, Right) in mm
- **AND** slope values for all 4 sides SHALL be shown

## Requirement: Re-run analysis

The Re-run analysis button SHALL call the cached analysis function with the current sidebar parameters.

### Scenario: Re-run with changed protocol parameter

- **GIVEN** Advanced mode with a result
- **WHEN** the In-Field Ratio is changed from 0.8 to 0.6
- **AND** "Re-run analysis" is clicked
- **THEN** the analysis SHALL re-execute with the new in-field ratio
- **AND** the Overview tab SHALL update with the new results

## Requirement: Download xlsx

The Download xlsx button SHALL write the paired xltx/xlsx to the machine's output_root.

### Scenario: Download produces xlsx

- **GIVEN** Advanced mode with a result
- **WHEN** "Download xlsx" is clicked
- **THEN** the xlsx SHALL be written to `<machine.output_root>/FP/<MACHINE>_FP_<image_stem>/`
- **AND** a download button SHALL appear allowing the user to download the file

## Requirement: Full errors surfaced inline

Advanced mode SHALL show full tracebacks for analysis failures, unlike Simple mode which shows only user-friendly messages.

### Scenario: Error in Advanced mode

- **GIVEN** Advanced mode with an invalid parameter combination
- **WHEN** analysis fails
- **THEN** the full Python traceback SHALL be shown inline in the Streamlit page

## Requirement: Lazy field_analysis object

The Advanced mode tabs that need matplotlib plots (Field Map) SHALL lazily initialize the pylinac `FieldAnalysis` object via session_state, matching the WL/CatPhan pattern.

### Scenario: Lazy init on first tab access

- **GIVEN** Advanced mode with a cached result but no live FieldAnalysis object
- **WHEN** the Field Map tab is accessed
- **THEN** the FieldAnalysis object SHALL be created and cached
- **AND** subsequent tab switches SHALL reuse the cached object
