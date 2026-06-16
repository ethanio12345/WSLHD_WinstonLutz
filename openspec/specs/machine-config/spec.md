## Purpose

Configure machines, output paths, analysis defaults, and asset paths for the pylinac QA GUI. Loaded from `machines.yaml` at startup with pydantic validation and filesystem existence checks.

## Requirements

### Requirement: Pydantic-validated machines.yaml schema

The app SHALL load `machines.yaml` at startup and validate it against a pydantic schema. The schema SHALL enforce:

- `machines`: a map of machine key (e.g. `LA2`) to a machine object with `display_name` (str) and `dicom_roots` (dict keyed by module name with absolute path values)
- `output.root`: absolute path to the output directory (container path)
- `analysis_defaults.winston_lutz`: dict where `bb_size_mm` (float) and `machine_scale` (enum: `VARIAN_IEC`, `VARIAN_STANDARD`, `IEC61217` — consult pylinac's `MachineScale` enum for the authoritative list) are required, `tolerance_mm` (float, UI-only) is required, and all other pylinac `analyze()` parameters (`low_density_bb`, `open_field`, `apply_virtual_shift`, `snap_tolerance`, `gantry_reference`, `collimator_reference`, `couch_reference`) are optional and fall back to pylinac defaults if absent
- `assets.fry_meme_path` and `assets.logo_path`: absolute paths

Each machine's `dicom_roots.winston_lutz` path SHALL be present and SHALL exist on the filesystem at startup (the app refuses to start if any configured machine's WL root is missing).

#### Scenario: Valid config

- **WHEN** `machines.yaml` contains a valid schema-conformant config with all paths existing
- **THEN** the app starts normally and the machines are available in the dropdown

#### Scenario: Missing required key

- **WHEN** `analysis_defaults.winston_lutz.bb_size_mm` is absent
- **THEN** the app refuses to start, logging a pydantic validation error showing the missing key

#### Scenario: Optional pylinac parameter absent

- **WHEN** `analysis_defaults.winston_lutz` omits `apply_virtual_shift`
- **THEN** config validation succeeds; Simple and Advanced modes apply pylinac's default for `apply_virtual_shift` (False)

#### Scenario: Nonexistent DICOM root

- **WHEN** machine `LA2`'s `dicom_roots.winston_lutz` points to `/data/LA2/WinstonLutz` but that path does not exist on the filesystem
- **THEN** the app refuses to start, logging "Machine LA2: DICOM root /data/LA2/WinstonLutz does not exist"

### Requirement: Per-machine-per-module explicit DICOM roots

Each machine's `dicom_roots` SHALL be a dict keyed by module name. For v1, only `winston_lutz` is required; future modules (CatPhan, FieldProfile, TrajectoryLog) will add additional keys. The config loader SHALL NOT infer or default missing module roots — they must be explicit so misconfigurations surface at load time.

#### Scenario: Only WL configured

- **WHEN** `machines.yaml` defines `dicom_roots: { winston_lutz: /data/LA2/WinstonLutz }` for `LA2`
- **THEN** the WL page is available; future module pages (if any are added) will report "no DICOM root configured for `<module>` on `<machine>`" if selected

#### Scenario: Multiple modules configured for future-proofing

- **WHEN** `machines.yaml` defines `dicom_roots: { winston_lutz: ..., catphan: ... }`
- **THEN** the config loads successfully; the extra `catphan` key is ignored by v1 but available for future use

### Requirement: Config bind-mounted (no rebuild for updates)

The Docker Compose file SHALL bind-mount `machines.yaml` from the host into the container at `/app/machines.yaml:ro`. Updating the config (adding a machine, changing defaults) SHALL require only a host-side edit + container restart, not an image rebuild.

#### Scenario: Add a machine without rebuild

- **WHEN** the host edits `machines.yaml` to add `LA5` and restarts the container
- **THEN** `LA5` appears in the Simple mode dropdown after restart, without `docker compose build`

### Requirement: Centre-wide analysis defaults

`analysis_defaults.winston_lutz` SHALL be centre-wide (a single set of defaults applied to all machines). Per-machine overrides are out of scope for v1.

#### Scenario: Defaults applied to all machines

- **WHEN** `analysis_defaults.winston_lutz.bb_size_mm = 5.0`
- **THEN** Simple mode for `LA2`, `LA3`, and `LA4` all use `bb_size_mm = 5.0`

### Requirement: Asset path configuration

`assets.fry_meme_path` and `assets.logo_path` SHALL be configurable in `machines.yaml`. The app SHALL gracefully handle missing asset files (display a placeholder banner with the expected path).

#### Scenario: Asset present

- **WHEN** `assets.fry_meme_path = /assets/fry_money.png` and that file exists
- **THEN** the Fry meme renders in the UI

#### Scenario: Asset missing

- **WHEN** `assets.fry_meme_path = /assets/fry_money.png` and that file does not exist
- **THEN** the UI displays "Drop a meme image at: /assets/fry_money.png" in place of the image
