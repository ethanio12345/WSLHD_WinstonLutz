## REMOVED Requirements

### Requirement: Paired xltx/xlsx output

Replaced by "In-browser xlsx download (replaces paired xltx/xlsx disk output)".

### Requirement: 30 named cells populated

Consolidated into the "In-browser xlsx download" requirement's "30 named cells populated in downloaded xlsx" scenario.

### Requirement: Data sheets

Consolidated into the "In-browser xlsx download" requirement's "5 sheets present" scenario.

### Requirement: Template version stamp

Consolidated into the "In-browser xlsx download" requirement's "30 named cells populated in downloaded xlsx" scenario (template_version check).

### Requirement: Output path uses per-machine output_root

Removed — Field Profile no longer writes to any server-side output directory. See "Removed — server-side session output".

## ADDED Requirements

### Requirement: In-browser xlsx download (replaces paired xltx/xlsx disk output)

The Field Profile excel output SHALL be produced in-memory and served to the user's browser via a download button. The app SHALL NOT write any FP xlsx/xltx to a server-side output directory.

#### Scenario: build_fp_xlsx_bytes produces valid xlsx

- **GIVEN** a `FieldAnalysisResult`
- **WHEN** `build_fp_xlsx_bytes(result, template_path)` is called
- **THEN** it SHALL return `bytes` containing a valid xlsx workbook
- **AND** the bytes SHALL NOT be written to disk by this function

#### Scenario: 30 named cells populated in downloaded xlsx

- **GIVEN** a downloaded FP xlsx (from `build_fp_xlsx_bytes`)
- **THEN** all 30 required defined names (`REQUIRED_FP_TEMPLATE_NAMES`) SHALL resolve
- **AND** the 29 metric named cells SHALL be non-empty
- **AND** `template_version` SHALL equal the FP template version stamp

#### Scenario: 5 sheets present

- **GIVEN** a downloaded FP xlsx
- **THEN** it SHALL contain exactly 5 sheets: Summary, Profiles, Penumbra, CAX Beam Center, ROI
- **AND** the Profiles sheet SHALL contain both vertical and horizontal profile data
- **AND** the Penumbra sheet SHALL contain Top/Bottom/Left/Right rows

#### Scenario: Download filename keys on image stem

- **GIVEN** an analysis of `/data/LA2/FieldProfile/6MV_10x10.dcm`
- **WHEN** the download button is rendered
- **THEN** the `file_name` SHALL be `6MV_10x10.xlsx` (image stem + `.xlsx`)

### Requirement: Removed — server-side session output

The prior paired `.xltx`/`.xlsx` session-folder output (`<output_root>/FP/<MACHINE>_FP_<IMAGE_STEM>/`) is **REMOVED**. `build_session_folder` and `copy_template_to_session` SHALL NOT be called by the FP path.

#### Scenario: No FP files written to output_root

- **GIVEN** any FP analysis (Simple or Advanced, including download)
- **WHEN** the analysis/download completes
- **THEN** no files SHALL be created under any machine's `output_root` for FP
- **AND** no `FP/` subdirectory SHALL be created

### Requirement: Template still validated at startup

The `templates/field_profile.xltx` SHALL still be validated at app startup (all 30 named cells present) since the page always uses it for in-memory xlsx generation.

#### Scenario: FP template validated unconditionally

- **GIVEN** the app starts (regardless of machines/field_profile config)
- **WHEN** startup checks run
- **THEN** `templates/field_profile.xltx` SHALL be validated via `validate_fp_template`
- **AND** a missing/invalid template SHALL prevent startup with a clear error
