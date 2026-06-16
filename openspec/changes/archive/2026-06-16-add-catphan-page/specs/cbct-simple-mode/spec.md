## ADDED Requirements

### Requirement: Machine selection filtered to CatPhan-configured machines

The CatPhan page (`pages/2_CatPhan.py`) SHALL present a dropdown of only those machines where `dicom_roots.catphan` is present and exists on the filesystem. Machines without CatPhan configured SHALL NOT appear in this dropdown (but remain available on the WL page if WL is configured).

#### Scenario: Mixed configuration

- **WHEN** `LA2` has `catphan` configured, `LA3` does not, `LA4` has `catphan` configured
- **THEN** the CatPhan page dropdown lists `LA2` and `LA4`, alphabetically sorted; `LA3` is absent

#### Scenario: No machines with CatPhan

- **WHEN** no machine in `machines.yaml` has `catphan` configured
- **THEN** the dropdown is empty and a banner reads "No machines have CatPhan configured. Edit machines.yaml and reload."

### Requirement: Automatic newest-runfolder detection

When a machine is selected, the CatPhan page SHALL scan that machine's `catphan` DICOM root for immediate subdirectories and identify the one with the newest modification time (`st_mtime`). The selected runfolder path SHALL be displayed to the user before any analysis runs, alongside the count of `.dcm` files it contains.

#### Scenario: Runfolders present

- **WHEN** machine `LA2` is selected and `/data/LA2/CatPhan/` contains subdirectories `2026-06-16_monthly/` (mtime T1) and `2026-06-23_monthly/` (mtime T2 > T1)
- **THEN** the preview reads "Will analyze: `2026-06-23_monthly/` (N DICOMs)" (where N is the actual count)

#### Scenario: No runfolders

- **WHEN** machine `LA2` is selected and `/data/LA2/CatPhan/` contains no subdirectories
- **THEN** the preview reads "No runfolders found for LA2 at /data/LA2/CatPhan. Contact physics IT." and the run button is disabled

#### Scenario: Empty runfolder

- **WHEN** the newest runfolder contains zero `.dcm` files
- **THEN** the preview reads "Runfolder `<name>` is empty. Wait for DICOM export to complete, then click the button again." and the run button remains enabled

### Requirement: One-click analysis trigger

The CatPhan Simple mode UI SHALL present a single button labelled "Shut Up and Give Me My MyQA Results" (same label as WL). Clicking the button SHALL run `pylinac.CatPhan504(dicom_root).analyze()` using the parameters from `analysis_defaults.catphan`.

#### Scenario: Successful analysis

- **WHEN** the button is clicked with a valid, non-empty runfolder selected
- **THEN** a spinner displays "Running CatPhan 504 analysis..." for the duration of pylinac's run, and on completion a success card replaces the button

#### Scenario: Analysis failure

- **WHEN** pylinac raises any exception during analysis (e.g. phantom not localised, missing CTP module)
- **THEN** the UI displays "Analysis failed: <single-line summary>. Switch to Advanced mode to debug." and the full traceback is written to the server log only — never to the UI

### Requirement: Defaults sourced from config

All pylinac CatPhan `analyze()` parameters SHALL be populated from the `analysis_defaults.catphan` section of `machines.yaml`, with pylinac defaults applied for any optional parameter not configured. Simple mode SHALL NOT expose any parameter overrides — that is the role of Advanced mode.

#### Scenario: Required defaults applied

- **WHEN** `analysis_defaults.catphan.hu_tolerance = 40` and `scaling_tolerance = 0.5` and `slice_thickness_tolerance = 0.5`
- **THEN** `cbct.analyze(hu_tolerance=40, scaling_tolerance=0.5, slice_thickness_tolerance=0.5, ...)` is called

#### Scenario: Optional default absent

- **WHEN** `analysis_defaults.catphan` omits `thickness_slice_straddle`
- **THEN** `cbct.analyze(...)` is called without `thickness_slice_straddle`, and pylinac applies its default (`'auto'`)

### Requirement: Success card display

On successful analysis, the UI SHALL display a success card containing: the path of the written xlsx file, a quick summary showing the four pass/fail flags (`hu_linearity_passed`, `geometry_passed`, `uniformity_passed`, `thickness_passed`) and the primary metric `low_contrast_visibility` as a value, and a "View in Advanced mode" button.

#### Scenario: All flags pass

- **WHEN** analysis completes with all four pass/fail flags `True`
- **THEN** the success card shows `[PASS]` next to each of the four flags, the value of `low_contrast_visibility`, the output path, and the "View in Advanced mode" button

#### Scenario: One or more flags fail

- **WHEN** analysis completes with `hu_linearity_passed = False`
- **THEN** the success card shows `HU Linearity: [FAIL]` (in a distinct colour) alongside the other flags' statuses — analysis still completes and the xlsx is still written; failure is informational, not blocking

### Requirement: Hand-off to Advanced mode preserves the analysis result

When the user clicks "View in Advanced mode" from the Simple mode success card, the system SHALL switch the sidebar mode toggle to Advanced AND pass the `CatPhanAnalysisResult` via `st.session_state["cp_result"]`. Advanced mode SHALL read this cached result on entry without re-running analysis.

#### Scenario: Hand-off preserves result

- **WHEN** "View in Advanced mode" is clicked after a Simple mode run
- **THEN** Advanced mode renders within 1 second (no analysis spinner) and the Overview tab shows the same metrics as the Simple mode success card

#### Scenario: Hand-off parameters retained

- **WHEN** Advanced mode is entered via hand-off
- **THEN** the sidebar parameter widgets display the values used by Simple mode (from `CatPhanAnalysisResult.params_used`), not the defaults

### Requirement: Physicist-friendly error messages

Simple mode SHALL catch all exceptions from pylinac and the excel writer, log the full traceback to the server log via `logging.exception`, and display only a one-line user-safe summary in the UI. Raw pylinac exception messages, stack traces, and internal paths MUST NOT appear in the Simple mode UI.

#### Scenario: pylinac phantom localisation failure

- **WHEN** pylinac raises `ValueError` or any localisation error
- **THEN** the UI shows "Analysis failed: could not localise the phantom. Check phantom positioning or switch to Advanced mode." and the server log contains the full traceback

#### Scenario: Excel write failure

- **WHEN** the output directory is read-only or full
- **THEN** the UI shows "Cannot write to `<path>`. Contact physics IT." and the server log contains the full traceback
