## Requirement: Field profile Simple mode page

The app SHALL provide a Field Profile page (`pages/3_Field_Profile.py`) with a Simple mode that allows a physicist to select a machine, runfolder, and individual DICOM image, then run analysis with one click.

### Scenario: Machine dropdown filtered to field_profile machines

- **GIVEN** machines LA2 (WL+CP+FP) and LA3 (WL only) are configured
- **WHEN** the Field Profile page renders
- **THEN** the machine dropdown SHALL show only LA2 (the machine with `field_profile` configured)

### Scenario: No machines with field_profile

- **GIVEN** no machines have `field_profile` in `dicom_roots`
- **WHEN** the Field Profile page renders
- **THEN** a warning SHALL be shown: "No machines have Field Profile configured"

## Requirement: Runfolder dropdown

The page SHALL show a runfolder dropdown listing all immediate subdirectories of the selected machine's `field_profile` DICOM root, sorted newest-first.

### Scenario: Runfolders present

- **GIVEN** machine LA2 with `field_profile: /data/LA2/FieldProfile`
- **AND** subdirectories `2026-06-16_monthly` and `2026-06-01_monthly` exist
- **WHEN** the page renders
- **THEN** the runfolder dropdown SHALL list both, with the newest selected by default

### Scenario: No runfolders

- **GIVEN** the field_profile DICOM root exists but has no subdirectories
- **WHEN** the page renders
- **THEN** an error SHALL be shown indicating no runfolders were found

## Requirement: Image dropdown with DICOM metadata

The page SHALL show an image dropdown listing all DICOM files in the selected runfolder. Each entry SHALL display a summary built from DICOM metadata.

### Scenario: Multiple images in runfolder

- **GIVEN** runfolder contains `6MV_10x10.dcm`, `6MV_FFF_10x10.dcm`, `10MV_10x10.dcm`
- **WHEN** the image dropdown renders
- **THEN** each entry SHALL show energy, RT image label, dimensions (cols×rows), pixel spacing, and filename
- **AND** the format SHALL be e.g. `6FFF T2_OP 1024×768 0.392mm/px (6MV_FFF_10x10.dcm)`

### Scenario: DICOM metadata missing

- **GIVEN** an image with no Radiation Energy or RT Image Label tags
- **WHEN** the dropdown entry renders
- **THEN** the entry SHALL show available info + filename (no crash for missing tags)

## Requirement: FFF auto-detection

The page SHALL auto-detect whether the selected image is a flattened or FFF beam and pass `is_FFF` to the analysis.

### Scenario: FFF detected from Radiation Energy tag

- **GIVEN** an image with DICOM tag `(3002,0060)` Radiation Energy = "6FFF"
- **WHEN** the image is selected
- **THEN** the page SHALL display "FFF detected: Yes"
- **AND** the analysis SHALL be called with `is_FFF=True`

### Scenario: Flat beam detected

- **GIVEN** an image with Radiation Energy = "6"
- **WHEN** the image is selected
- **THEN** the page SHALL display "FFF detected: No"
- **AND** the analysis SHALL be called with `is_FFF=False`

### Scenario: FFF detected from string tag scan (fallback)

- **GIVEN** an image without `(3002,0060)` but with "FFF" in SeriesDescription
- **WHEN** the image is selected
- **THEN** the page SHALL detect FFF from the string scan and display "FFF detected: Yes"

## Requirement: One-click analysis button

The page SHALL provide a button labeled "Shut Up and Give Me My MyQA Results" that runs the field profile analysis on the selected image.

### Scenario: Successful analysis

- **GIVEN** a valid DICOM image is selected
- **WHEN** the button is clicked
- **THEN** the analysis SHALL run using `pylinac.FieldAnalysis` with VARIAN protocol
- **AND** the xlsx SHALL be written to the machine's output_root
- **AND** a success card SHALL appear showing flatness (V+H), symmetry (V+H), and field size

### Scenario: Analysis failure

- **GIVEN** a corrupt or non-field DICOM image is selected
- **WHEN** the button is clicked
- **THEN** the failure SHALL be caught
- **AND** a physicist-friendly error message SHALL be shown
- **AND** the full traceback SHALL be logged via `logging.exception`
- **AND** the error SHALL NOT be shown in the Simple mode UI

## Requirement: Success card

After a successful analysis, a success card SHALL display the key metrics.

### Scenario: Success card content

- **GIVEN** a successful field profile analysis
- **THEN** the success card SHALL show:
  - Flatness Vertical (%)
  - Flatness Horizontal (%)
  - Symmetry Vertical (%)
  - Symmetry Horizontal (%)
  - Field Size Vertical (mm)
  - Field Size Horizontal (mm)
  - Output xlsx path
  - FFF status
- **AND** a "View in Advanced mode" button SHALL appear

## Requirement: Hand-off to Advanced mode

The success card SHALL include a button that switches to Advanced mode and passes the result via session_state.

### Scenario: Hand-off preserves result

- **GIVEN** a successful Simple mode analysis
- **WHEN** "View in Advanced mode" is clicked
- **THEN** the mode toggle SHALL switch to Advanced
- **AND** the Advanced mode SHALL display the result immediately without re-running analysis
