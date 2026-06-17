## Requirement: Paired xltx/xlsx output

The Excel writer SHALL produce paired `.xltx` + `.xlsx` files for each field profile session, following the same pattern as WL and CatPhan.

### Scenario: First run for a session

- **GIVEN** a `FieldAnalysisResult` with machine_id="LA2" and image "6MV_10x10.dcm"
- **WHEN** `write_fp_session_output` is called
- **THEN** a session folder SHALL be created at `<machine.output_root>/FP/LA2_FP_6MV_10x10/`
- **AND** `LA2_FP_6MV_10x10.xltx` SHALL be copied from the template
- **AND** `LA2_FP_6MV_10x10.xlsx` SHALL be written with 30 named cells populated

### Scenario: Re-run overwrites same session

- **GIVEN** a session folder already exists for `LA2_FP_6MV_10x10`
- **WHEN** the same image is analyzed again with different parameters
- **THEN** the `.xlsx` SHALL be overwritten in-place
- **AND** the `.xltx` SHALL be overwritten in-place

## Requirement: 30 named cells populated

The xlsx SHALL define and populate exactly 30 named cells: 29 metrics + `template_version`.

### Scenario: All 30 named cells populated

- **GIVEN** a successfully written xlsx
- **THEN** every one of the 30 defined names SHALL resolve to a non-empty cell
- **AND** the named cells SHALL include:
  - Session metadata (3): `machine_name`, `session_date`, `image_name`
  - Protocol metrics (4): `flatness_vertical`, `flatness_horizontal`, `symmetry_vertical`, `symmetry_horizontal`
  - Field geometry (2): `field_size_vertical_mm`, `field_size_horizontal_mm`
  - Penumbra (4): `top_penumbra_mm`, `bottom_penumbra_mm`, `left_penumbra_mm`, `right_penumbra_mm`
  - CAX offsets (4): `cax_to_top_mm`, `cax_to_bottom_mm`, `cax_to_left_mm`, `cax_to_right_mm`
  - Beam center offsets (4): `beam_center_to_top_mm`, `beam_center_to_bottom_mm`, `beam_center_to_left_mm`, `beam_center_to_right_mm`
  - Slopes (4): `top_slope_percent_mm`, `bottom_slope_percent_mm`, `left_slope_percent_mm`, `right_slope_percent_mm`
  - Central ROI (4): `central_roi_mean`, `central_roi_max`, `central_roi_min`, `central_roi_std`
  - Version (1): `template_version`

## Requirement: Data sheets

The xlsx SHALL contain 5 sheets: Summary + 4 data sheets.

### Scenario: Sheet count

- **GIVEN** a written xlsx
- **THEN** the sheet count SHALL be exactly 5: Summary, Profiles, Penumbra, CAX Beam Center, ROI

### Scenario: Profiles sheet content

- **WHEN** the Profiles sheet is inspected
- **THEN** it SHALL contain vertical and horizontal profile data in tabular form (position mm, normalized dose)

### Scenario: Penumbra sheet content

- **WHEN** the Penumbra sheet is inspected
- **THEN** it SHALL contain a table with 4 rows (Top, Bottom, Left, Right) showing penumbra_mm and penumbra_percent_mm

## Requirement: Template validation

The xltx template SHALL be validated at app startup if any machine has `field_profile` configured.

### Scenario: Template missing names

- **GIVEN** `templates/field_profile.xltx` is missing 5 of the 30 required defined names
- **WHEN** the app starts with field_profile configured
- **THEN** a ConfigError SHALL be raised listing the missing names
- **AND** the app SHALL refuse to start

### Scenario: Template not found

- **GIVEN** no machine has `field_profile` configured
- **WHEN** the app starts
- **THEN** the field_profile template SHALL NOT be validated (no error if missing)

## Requirement: Template version stamp

The `template_version` named cell SHALL contain the version string from the template builder script.

### Scenario: Version stamped

- **GIVEN** a written xlsx with `TEMPLATE_VERSION = "2026-06-fp"`
- **THEN** the `template_version` cell SHALL contain `"2026-06-fp"`

## Requirement: Output path uses per-machine output_root

The output path SHALL use the machine's `output_root`, not a global output root.

### Scenario: Per-machine output path

- **GIVEN** machine LA2 with `output_root: /data/LA2/output`
- **AND** image `6MV_10x10.dcm`
- **WHEN** the xlsx is written
- **THEN** the path SHALL be `/data/LA2/output/FP/LA2_FP_6MV_10x10/LA2_FP_6MV_10x10.xlsx`
