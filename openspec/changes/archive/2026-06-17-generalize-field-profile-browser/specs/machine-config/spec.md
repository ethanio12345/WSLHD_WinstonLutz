## MODIFIED Requirements

### Requirement: Pydantic-validated machines.yaml schema

The app SHALL load `machines.yaml` at startup and validate it against a pydantic schema. The schema SHALL enforce:

- `machines`: a map of machine key (e.g. `LA2`) to a machine object with `display_name` (str) and `dicom_roots` (dict keyed by module name with absolute path values). Each machine's `dicom_roots` MUST contain at least one module root (currently `winston_lutz` and/or `catphan`); a machine with an empty `dicom_roots` is invalid. **Note: `field_profile` is NOT a validated `dicom_roots` key** — it has been decoupled from per-machine config (see "field_profile decoupled from per-machine config" below). A legacy `dicom_roots.field_profile` entry is silently ignored (forward-compat, same treatment as `trajectory_log`).
- `output.root`: absolute path to the output directory (container path)
- `analysis_defaults.winston_lutz`: dict where `bb_size_mm` (float) and `machine_scale` (enum: `VARIAN_IEC`, `VARIAN_STANDARD`, `IEC61217` — consult pylinac's `MachineScale` enum for the authoritative list) are required, `tolerance_mm` (float, UI-only) is required, and all other pylinac `analyze()` parameters (`low_density_bb`, `open_field`, `apply_virtual_shift`, `snap_tolerance`, `gantry_reference`, `collimator_reference`, `couch_reference`) are optional and fall back to pylinac defaults if absent
- `analysis_defaults.catphan`: dict where `hu_tolerance` (float), `scaling_tolerance` (float, mm), and `slice_thickness_tolerance` (float, mm) are required, and all other pylinac CatPhan `analyze()` parameters (`thickness_slice_straddle`, `expected_hu_values`, `x_adjustment`, `y_adjustment`, `angle_adjustment`, `roi_size_factor`, `scaling_factor`, `minimum_rois_seen`) are optional and fall back to pylinac defaults if absent. (No `tolerance_mm` UI-only field — CatPhan's pass/fail comes from pylinac's per-test tolerances, not a separate UI widget.) Required if any machine has `catphan` configured; otherwise absent.
- `analysis_defaults.field_profile`: **OPTIONAL** dict where `protocol` (enum: `VARIAN`, `SIEMENS`, `ELEKTA`) is required (if the section is present), and all other pylinac `FieldAnalysis.analyze()` parameters (`centering`, `in_field_ratio`, `penumbra`, `is_fff`, `interpolation`, `edge_detection_method`, `vert_position`, `horiz_position`, `vert_width`, `horiz_width`, `slope_exclusion_ratio`, `edge_smoothing_ratio`, `hill_window_ratio`) are optional and fall back to pylinac defaults if absent. (No pass/fail tolerances — field profile reports values only.) **If absent, the FP page uses `protocol: VARIAN` and pylinac defaults.** No longer conditional on any machine having `field_profile` configured.
- `field_profile` (top-level, optional): page config for the decoupled Field Profile page. Currently supports `browse_root` (path, default `/data`). See "field_profile.browse_root config" below.
- `assets.fry_meme_path` and `assets.logo_path`: absolute paths

Each machine's configured `dicom_roots.*` path SHALL exist on the filesystem at startup (the app refuses to start if any configured machine's root is missing). `winston_lutz` and `catphan` are each independently optional per machine; a machine may have any combination — but MUST have at least one module root configured.

#### Scenario: Valid config with both modules

- **WHEN** `machines.yaml` contains a valid schema-conformant config with all paths existing, `LA2` has both `winston_lutz` and `catphan` configured
- **THEN** the app starts normally; `LA2` appears in the dropdowns on both `pages/1_Winston_Lutz.py` and `pages/2_CatPhan.py`

#### Scenario: Valid config with WL only

- **WHEN** `LA3` has only `dicom_roots.winston_lutz` configured (no `catphan`)
- **THEN** `LA3` appears in the WL page's machine dropdown; `LA3` does NOT appear in the CatPhan page's machine dropdown

#### Scenario: Valid config with CatPhan only

- **WHEN** `LA4` has only `dicom_roots.catphan` configured (no `winston_lutz`)
- **THEN** `LA4` appears in the CatPhan page's machine dropdown; `LA4` does NOT appear in the WL page's machine dropdown

#### Scenario: Machine with no module roots

- **WHEN** `LA5` has `dicom_roots: {}` (empty)
- **THEN** the app refuses to start, logging "Machine LA5: dicom_roots must contain at least one module root"

#### Scenario: Missing required WL key

- **WHEN** any machine has `winston_lutz` configured but `analysis_defaults.winston_lutz.bb_size_mm` is absent
- **THEN** the app refuses to start, logging a pydantic validation error showing the missing key

#### Scenario: Missing required CatPhan key

- **WHEN** any machine has `catphan` configured but `analysis_defaults.catphan.hu_tolerance` is absent
- **THEN** the app refuses to start, logging a pydantic validation error showing the missing key

#### Scenario: CatPhan configured without analysis_defaults.catphan

- **WHEN** machine `LA2` has `dicom_roots.catphan` configured but `analysis_defaults.catphan` section is absent from config
- **THEN** the app refuses to start, logging "catphan module configured for machine(s) but analysis_defaults.catphan is missing"

#### Scenario: Optional pylinac parameter absent (WL)

- **WHEN** `analysis_defaults.winston_lutz` omits `apply_virtual_shift`
- **THEN** config validation succeeds; Simple and Advanced modes apply pylinac's default for `apply_virtual_shift` (False)

#### Scenario: Optional pylinac parameter absent (CatPhan)

- **WHEN** `analysis_defaults.catphan` omits `thickness_slice_straddle`
- **THEN** config validation succeeds; Simple and Advanced modes apply pylinac's default for `thickness_slice_straddle` (`'auto'`)

#### Scenario: Nonexistent DICOM root (WL)

- **WHEN** machine `LA2`'s `dicom_roots.winston_lutz` points to `/data/LA2/WinstonLutz` but that path does not exist on the filesystem
- **THEN** the app refuses to start, logging "Machine LA2: DICOM root /data/LA2/WinstonLutz does not exist"

#### Scenario: Nonexistent DICOM root (CatPhan)

- **WHEN** machine `LA2`'s `dicom_roots.catphan` points to `/data/LA2/CatPhan` but that path does not exist on the filesystem
- **THEN** the app refuses to start, logging "Machine LA2: DICOM root /data/LA2/CatPhan does not exist"

#### Scenario: field_profile dicom_root ignored (legacy forward-compat)

- **WHEN** `machines.yaml` defines `dicom_roots: { winston_lutz: ..., field_profile: /data/LA2/FieldProfile }` for `LA2`
- **THEN** the config loads successfully; the `field_profile` key is ignored (not validated, directory existence not checked); the Field Profile page is still available (decoupled)

#### Scenario: analysis_defaults.field_profile absent loads successfully

- **WHEN** `analysis_defaults.field_profile` is absent from `machines.yaml`
- **THEN** the config loads successfully; the FP page uses `protocol: VARIAN` + pylinac defaults; no startup error

### Requirement: Per-machine-per-module explicit DICOM roots

Each machine's `dicom_roots` SHALL be a dict keyed by module name. Supported module keys are `winston_lutz` and `catphan`; future modules (TrajectoryLog) will add additional keys. The config loader SHALL NOT infer or default missing module roots — they must be explicit so misconfigurations surface at load time. Each module root is independently optional; at least one must be present per machine.

**Note: `field_profile` is no longer a per-machine `dicom_roots` key.** The Field Profile page is decoupled from per-machine config and uses a top-level `field_profile.browse_root` instead. A legacy `dicom_roots.field_profile` entry is silently ignored (forward-compat).

#### Scenario: Only WL configured

- **WHEN** `machines.yaml` defines `dicom_roots: { winston_lutz: /data/LA2/WinstonLutz }` for `LA2`
- **THEN** the WL page is available with `LA2` selectable; the CatPhan page is reachable but `LA2` is not in its machine dropdown

#### Scenario: Only CatPhan configured

- **WHEN** `machines.yaml` defines `dicom_roots: { catphan: /data/LA2/CatPhan }` for `LA4`
- **THEN** the CatPhan page is available with `LA4` selectable; the WL page is reachable but `LA4` is not in its machine dropdown

#### Scenario: Both modules configured

- **WHEN** `machines.yaml` defines `dicom_roots: { winston_lutz: ..., catphan: ... }` for `LA2`
- **THEN** both pages list `LA2` in their respective machine dropdowns

#### Scenario: Future module key ignored (forward compatibility)

- **WHEN** `machines.yaml` defines `dicom_roots: { winston_lutz: ..., catphan: ..., trajectory_log: ... }`
- **THEN** the config loads successfully; the extra `trajectory_log` key is ignored until the TrajectoryLog page is added in a future change

#### Scenario: Legacy field_profile key ignored

- **WHEN** `machines.yaml` defines `dicom_roots: { winston_lutz: ..., field_profile: /data/LA2/FieldProfile }` (legacy config)
- **THEN** the config loads successfully; the `field_profile` key is silently ignored (it is no longer a per-machine module key); the directory existence is NOT checked; the Field Profile page is still available via the decoupled top-level config

### Requirement: Centre-wide analysis defaults

`analysis_defaults.winston_lutz` and `analysis_defaults.catphan` SHALL each be centre-wide (a single set of defaults applied to all machines that have the respective module configured). Per-machine overrides are out of scope.

`analysis_defaults.field_profile` is **optional** centre-wide config. If present, it provides centre-wide defaults for the Field Profile page. If absent, the page uses `protocol: VARIAN` and pylinac defaults. It is no longer conditional on any machine having `field_profile` configured (the page is decoupled).

#### Scenario: WL defaults applied to all machines with WL

- **WHEN** `analysis_defaults.winston_lutz.bb_size_mm = 5.0` and machines `LA2`, `LA3` both have `winston_lutz` configured
- **THEN** Simple mode on the WL page for both `LA2` and `LA3` uses `bb_size_mm = 5.0`

#### Scenario: CatPhan defaults applied to all machines with CatPhan

- **WHEN** `analysis_defaults.catphan.hu_tolerance = 40` and machines `LA2`, `LA4` both have `catphan` configured
- **THEN** Simple mode on the CatPhan page for both `LA2` and `LA4` uses `hu_tolerance = 40`

#### Scenario: Defaults do not leak across modules

- **WHEN** `analysis_defaults.winston_lutz.bb_size_mm = 5.0` is set but `analysis_defaults.catphan.hu_tolerance` is absent
- **THEN** CatPhan analysis does NOT inherit `bb_size_mm`; the app refuses to start with the missing CatPhan required key (per the Pydantic-validated schema requirement)

#### Scenario: Field Profile defaults optional

- **WHEN** `analysis_defaults.field_profile` is absent from `machines.yaml`
- **THEN** the config loads successfully; the FP page uses `protocol: VARIAN` + pylinac defaults; no startup error occurs

## ADDED Requirements

### Requirement: field_profile decoupled from per-machine config

The `field_profile` module SHALL be decoupled from per-machine configuration. It SHALL NOT be a validated `dicom_roots` key. The Field Profile page SHALL be a standalone general-purpose tool with no machine association.

#### Scenario: field_profile removed from dicom_roots validation

- **GIVEN** `machines.yaml` has `dicom_roots: { field_profile: /data/LA2/FieldProfile }` on a machine (legacy)
- **WHEN** the config loads
- **THEN** the `field_profile` key SHALL be ignored (forward-compat, like `trajectory_log`)
- **AND** the config SHALL load successfully
- **AND** the page SHALL still render (it does not depend on this key)

#### Scenario: No field_profile anywhere still works

- **GIVEN** no machine has `field_profile` in `dicom_roots`
- **WHEN** the config loads and the page renders
- **THEN** the Field Profile page SHALL be available and functional

### Requirement: field_profile.browse_root config

A new top-level optional config `field_profile.browse_root` (path) SHALL set the root of the cascading folder browser. If absent, it SHALL default to `/data`.

#### Scenario: browse_root configured

- **GIVEN** `field_profile.browse_root: /mnt/rt_images`
- **WHEN** the FP page renders
- **THEN** the folder browser SHALL be rooted at `/mnt/rt_images`

#### Scenario: browse_root absent (default)

- **GIVEN** no `field_profile.browse_root` in config
- **WHEN** the FP page renders
- **THEN** the folder browser SHALL be rooted at `/data`

### Requirement: FP template validation unconditional

The FP xltx template SHALL be validated at startup unconditionally (the page always needs it for in-memory xlsx generation), regardless of config.

#### Scenario: Template validated on every startup

- **GIVEN** the app starts
- **WHEN** startup checks run
- **THEN** `templates/field_profile.xltx` SHALL be validated (30 named cells)
- **AND** a missing template SHALL prevent startup
