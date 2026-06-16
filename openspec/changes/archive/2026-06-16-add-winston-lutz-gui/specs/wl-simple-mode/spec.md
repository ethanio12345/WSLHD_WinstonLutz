## ADDED Requirements

### Requirement: Machine selection via dropdown

The Simple mode UI SHALL present a dropdown of all machines defined in `machines.yaml`, displaying each machine's `display_name` and using the machine key (e.g. `LA2`) as the internal identifier.

#### Scenario: Single machine configured

- **WHEN** `machines.yaml` defines one machine (`LA2`)
- **THEN** the Simple mode dropdown contains exactly one entry: `LA2 (TrueBeam)` (or whatever `display_name` is configured)

#### Scenario: Multiple machines configured

- **WHEN** `machines.yaml` defines `LA2`, `LA3`, `LA4`
- **THEN** the dropdown lists all three entries, ordered by machine key alphabetically

#### Scenario: No machines configured

- **WHEN** `machines.yaml` has an empty `machines:` map
- **THEN** the dropdown is empty and a banner reads "No machines configured. Edit machines.yaml and reload."

### Requirement: Automatic newest-runfolder detection

When a machine is selected, the system SHALL scan that machine's `winston_lutz` DICOM root for immediate subdirectories and identify the one with the newest modification time (`st_mtime`). The selected runfolder path SHALL be displayed to the user before any analysis runs, alongside the count of `.dcm` files it contains.

#### Scenario: Runfolders present

- **WHEN** machine `LA2` is selected and `/data/LA2/WinstonLutz/` contains subdirectories `2026-06-16_143022/` (mtime T1) and `2026-06-23_151234/` (mtime T2 > T1)
- **THEN** the preview reads "Will analyze: `2026-06-23_151234/` (17 DICOMs)" (or whatever the actual count is)

#### Scenario: No runfolders

- **WHEN** machine `LA2` is selected and `/data/LA2/WinstonLutz/` contains no subdirectories
- **THEN** the preview reads "No runfolders found for LA2 at /data/LA2/WinstonLutz. Contact physics IT." and the run button is disabled

#### Scenario: DICOM export in progress

- **WHEN** the newest runfolder contains zero `.dcm` files (treatment machine is still exporting)
- **THEN** the preview reads "Runfolder `<name>` is empty. Wait for DICOM export to complete, then click the button again." and the run button remains enabled (user can retry)

### Requirement: One-click analysis trigger

The Simple mode UI SHALL present a single button labelled "Shut Up and Give Me My MyQA Results" (or a configurable label). Clicking the button SHALL run pylinac's `WinstonLutz(dicom_root).analyze()` using the parameters from `machines.yaml`'s `analysis_defaults.winston_lutz` section.

#### Scenario: Successful analysis

- **WHEN** the button is clicked with a valid, non-empty runfolder selected
- **THEN** a spinner displays "Running Winston-Lutz analysis..." for the duration of pylinac's run, and on completion a success card replaces the button

#### Scenario: Analysis failure

- **WHEN** pylinac raises any exception during analysis (e.g. BB not detected, corrupt DICOM)
- **THEN** the UI displays "Analysis failed: <single-line summary>. Switch to Advanced mode to debug." and the full traceback is written to the server log only — never to the UI

### Requirement: Defaults sourced from config

All pylinac `analyze()` parameters SHALL be populated from the `analysis_defaults.winston_lutz` section of `machines.yaml`, with pylinac defaults applied for any optional parameter not configured (see `machine-config` spec for the required vs optional split). Simple mode SHALL NOT expose any parameter overrides — that is the role of Advanced mode.

#### Scenario: Defaults applied

- **WHEN** `analysis_defaults.winston_lutz.bb_size_mm` is `5.0` and `machine_scale` is `VARIAN_IEC`
- **THEN** `wl.analyze(bb_size_mm=5.0, machine_scale=MachineScale.VARIAN_IEC, ...)` is called

#### Scenario: Missing default

- **WHEN** `analysis_defaults.winston_lutz` omits a required key (e.g. `bb_size_mm`)
- **THEN** config validation fails at load time and the app refuses to start, logging the missing key

### Requirement: Success card display

On successful analysis, the UI SHALL display a success card containing: the path of the written xlsx file, a quick summary showing `max_2d_cax_to_bb` with pass/fail status against the configured `tolerance_mm` alongside `median_2d_cax_to_bb` and `gantry_3d_iso` as values (no pass/fail markers on those), and a "View in Advanced mode" button.

#### Scenario: Primary metric passes

- **WHEN** analysis completes with `max_2d_cax_to_bb = 0.83mm` and `tolerance_mm = 1.0`
- **THEN** the success card shows `Max 2D dist: 0.83 mm [PASS]` alongside the output path, the values of `median_2d_cax_to_bb` and `gantry_3d_iso`, and the "View in Advanced mode" button

#### Scenario: Primary metric fails

- **WHEN** analysis completes with `max_2d_cax_to_bb = 1.21mm` and `tolerance_mm = 1.0`
- **THEN** the success card shows `Max 2D dist: 1.21 mm [FAIL]` (in a distinct colour) — analysis still completes and the xlsx is still written; failure is informational, not blocking

### Requirement: Hand-off to Advanced mode preserves the analysis result

When the user clicks "View in Advanced mode" from the Simple mode success card, the system SHALL switch the sidebar mode toggle to Advanced AND pass the `WLAnalysisResult` via `st.session_state["wl_result"]`. Advanced mode SHALL read this cached result on entry without re-running analysis.

#### Scenario: Hand-off preserves result

- **WHEN** "View in Advanced mode" is clicked after a Simple mode run
- **THEN** Advanced mode renders within 1 second (no analysis spinner) and the Overview tab shows the same metrics as the Simple mode success card

#### Scenario: Hand-off parameters retained

- **WHEN** Advanced mode is entered via hand-off
- **THEN** the sidebar parameter widgets display the values used by Simple mode (from `WLAnalysisResult.params_used`), not the defaults — so the user sees what was actually run

### Requirement: Physicist-friendly error messages

Simple mode SHALL catch all exceptions from pylinac and the excel writer, log the full traceback to the server log via `logging.exception`, and display only a one-line user-safe summary in the UI. Raw pylinac exception messages, stack traces, and internal paths MUST NOT appear in the Simple mode UI.

#### Scenario: pylinac BB detection failure

- **WHEN** pylinac raises `ValueError` or any image-analysis error
- **THEN** the UI shows "Analysis failed: could not detect the BB. Check image quality or switch to Advanced mode." and the server log contains the full traceback

#### Scenario: Excel write failure

- **WHEN** the output directory is read-only or full
- **THEN** the UI shows "Cannot write to `<path>`. Contact physics IT." and the server log contains the full traceback
