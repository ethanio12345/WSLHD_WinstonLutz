## Requirement: Field profile Simple mode page

The app SHALL provide a Field Profile page (`pages/3_Field_Profile.py`) with a Simple mode that is a **general-purpose** standalone tool (decoupled from per-machine config). The physicist SHALL navigate to a folder containing RT images via a cascading selectbox browser, select an individual DICOM image, and run analysis with one click.

The page SHALL NOT require any per-machine `dicom_roots.field_profile` configuration. The page SHALL be always available (no enablement flag).

### Scenario: Page always available (decoupled)

- **GIVEN** `machines.yaml` has NO `field_profile` anywhere in any machine's `dicom_roots`
- **WHEN** the Field Profile page renders
- **THEN** the page SHALL render the folder browser normally (no "not configured" warning)

### Scenario: field_profile dicom_root ignored (forward compat)

- **GIVEN** a legacy config still has `dicom_roots.field_profile` on a machine
- **WHEN** the config loads
- **THEN** the `field_profile` key SHALL be ignored (forward-compat), and the page SHALL still render the folder browser rooted at `field_profile.browse_root`

## Requirement: Cascading folder browser

The page SHALL provide a cascading selectbox folder browser rooted at `field_profile.browse_root` (config, default `/data`). The physicist SHALL drill down folder-by-folder by clicking selectboxes; no path typing is required.

### Scenario: Cascading selectboxes render subdirs

- **GIVEN** `browse_root = /data`, with subdirs `LA2/`, `LA3/`, and `/data/LA2/FieldProfile/` exists
- **WHEN** the page renders
- **THEN** the first selectbox SHALL list `LA2`, `LA3` (immediate subdirs, sorted)
- **AND WHEN** the physicist selects `LA2`
- **THEN** a second selectbox SHALL list `FieldProfile` (and any other subdirs of `/data/LA2`)
- **AND WHEN** the physicist selects `FieldProfile`
- **THEN** the image dropdown SHALL populate with DICOM files in `/data/LA2/FieldProfile`

### Scenario: Browser is sandboxed to browse_root

- **GIVEN** the browser is at `/data/LA2/FieldProfile`
- **THEN** there SHALL be no affordance to navigate above `/data` (no `..`, no absolute-path entry)
- **AND** the page SHALL NOT enumerate directories outside `browse_root`

### Scenario: browse_root configurable

- **GIVEN** `machines.yaml` sets `field_profile.browse_root: /mnt/rt_images`
- **WHEN** the page renders
- **THEN** the first selectbox SHALL list immediate subdirs of `/mnt/rt_images`

### Scenario: browse_root missing or empty

- **GIVEN** `browse_root` does not exist or contains no subdirectories
- **WHEN** the page renders
- **THEN** an inline info message SHALL be shown (no crash)

## Requirement: Image dropdown with DICOM metadata

The page SHALL show an image dropdown listing all DICOM files in the selected (deepest) folder. Each entry SHALL display a summary built from DICOM metadata.

### Scenario: Multiple images in folder

- **GIVEN** the selected folder contains `6MV_10x10.dcm`, `6MV_FFF_10x10.dcm`, `10MV_10x10.dcm`
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

### Scenario: Successful analysis (in-browser, no server write)

- **GIVEN** a valid DICOM image is selected
- **WHEN** the button is clicked
- **THEN** the analysis SHALL run using `pylinac.FieldAnalysis` with VARIAN protocol
- **AND** NO file SHALL be written to any server-side output directory
- **AND** a success card SHALL appear showing flatness (V+H), symmetry (V+H), and field size

### Scenario: Analysis failure

- **GIVEN** a corrupt or non-field DICOM image is selected
- **WHEN** the button is clicked
- **THEN** the failure SHALL be caught
- **AND** a physicist-friendly error message SHALL be shown
- **AND** the full traceback SHALL be logged via `logging.exception`
- **AND** the error SHALL NOT be shown in the Simple mode UI

## Requirement: In-browser result + browser download

After analysis the result SHALL be shown in-browser and a download button SHALL serve the populated xlsx straight to the user's browser (Downloads).

### Scenario: Success card content

- **GIVEN** a successful field profile analysis
- **THEN** the success card SHALL show:
  - Flatness Vertical (%)
  - Flatness Horizontal (%)
  - Symmetry Vertical (%)
  - Symmetry Horizontal (%)
  - Field Size Vertical (mm)
  - Field Size Horizontal (mm)
  - FFF status
- **AND** a "Download xlsx" button SHALL appear
- **AND** NO server-side output path SHALL be shown (there is none)

### Scenario: Download button serves xlsx bytes

- **GIVEN** a successful analysis
- **WHEN** "Download xlsx" is clicked
- **THEN** the browser SHALL download a `<IMAGE_STEM>.xlsx` file
- **AND** the xlsx SHALL contain the 30 named cells (the MyQA contract) + 4 data sheets
- **AND** no file SHALL be written server-side by the download

## Requirement: Hand-off to Advanced mode

The success card SHALL include a button that switches to Advanced mode and passes the result via session_state.

### Scenario: Hand-off preserves result

- **GIVEN** a successful Simple mode analysis
- **WHEN** "View in Advanced mode" is clicked
- **THEN** the mode toggle SHALL switch to Advanced
- **AND** the Advanced mode SHALL display the result immediately without re-running analysis
