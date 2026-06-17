## Requirement: Machine supports field_profile module

The machine config SHALL accept `field_profile` as a key in `dicom_roots`, following the same multi-module pattern as `winston_lutz` and `catphan`. At least one module root is required per machine; `field_profile` is independently optional.

### Scenario: Machine with all three modules

- **GIVEN** a machines.yaml with LA2 having `winston_lutz`, `catphan`, and `field_profile` in `dicom_roots`
- **AND** `analysis_defaults` contains `winston_lutz`, `catphan`, and `field_profile` sections
- **WHEN** the config is loaded
- **THEN** the config loads successfully
- **AND** `config.has_field_profile()` returns True

### Scenario: Machine with field_profile only

- **GIVEN** a machines.yaml with LA4 having only `field_profile` in `dicom_roots`
- **AND** `analysis_defaults` contains only `field_profile`
- **WHEN** the config is loaded
- **THEN** the config loads successfully
- **AND** `config.has_winston_lutz()` returns False
- **AND** `config.has_catphan()` returns False

### Scenario: Field profile configured without defaults

- **GIVEN** a machines.yaml with LA2 having `field_profile` in `dicom_roots`
- **AND** `analysis_defaults` does NOT contain a `field_profile` section
- **WHEN** the config is loaded
- **THEN** a ConfigError SHALL be raised matching "field_profile module configured"

### Scenario: Field profile DICOM root validated

- **GIVEN** a machines.yaml with LA2 having `field_profile: /data/LA2/FieldProfile`
- **WHEN** the config is loaded
- **AND** `/data/LA2/FieldProfile` does not exist on the filesystem
- **THEN** a ConfigError SHALL be raised matching "DICOM root .* does not exist"

### Scenario: Field profile template validated at startup

- **GIVEN** at least one machine has `field_profile` configured
- **WHEN** the app starts
- **THEN** the app SHALL load `templates/field_profile.xltx` and verify all 30 required named cells are defined
- **AND** if any are missing, the app SHALL refuse to start with a clear error

## Requirement: FieldProfileDefaults model

The config SHALL include a `FieldProfileDefaults` pydantic model with required keys `protocol` (enum: VARIAN, SIEMENS, ELEKTA), and optional keys `centering`, `in_field_ratio`, `penumbra`, `is_fff`, `interpolation`, `edge_detection_method` that fall back to pylinac defaults.

### Scenario: Valid field_profile defaults

- **GIVEN** `analysis_defaults.field_profile` with `protocol: VARIAN`
- **WHEN** the config is loaded
- **THEN** the defaults load with VARIAN protocol
- **AND** optional keys use defaults (`centering=BEAM_CENTER`, `in_field_ratio=0.8`, `penumbra=[20,80]`, `is_fff=false`)

### Scenario: Invalid protocol

- **GIVEN** `analysis_defaults.field_profile` with `protocol: INVALID`
- **WHEN** the config is loaded
- **THEN** a validation error SHALL be raised

## Requirement: Per-machine output root applies to field_profile

The output path for field profile sessions SHALL follow `<machine.output_root>/FP/<MACHINE>_FP_<image_stem>/`, using the per-machine `output_root` (not a global output root).

### Scenario: Output path for field profile

- **GIVEN** machine LA2 with `output_root: /data/LA2/output`
- **AND** a field profile analysis of image `6MV_10x10.dcm`
- **WHEN** the xlsx is written
- **THEN** the output path SHALL be `/data/LA2/output/FP/LA2_FP_6MV_10x10/`
