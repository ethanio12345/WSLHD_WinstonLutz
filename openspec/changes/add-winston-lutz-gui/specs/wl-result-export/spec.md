## ADDED Requirements

### Requirement: Per-session paired xltx + xlsx

For every analysis run (Simple or Advanced), the system SHALL create a session output folder at `/out/<MACHINE>/WL/<MACHINE>_WL_<RUNFOLDER_NAME>/` containing two files: a copy of `templates/winston_lutz.xltx` renamed to `<MACHINE>_WL_<RUNFOLDER_NAME>.xltx`, and a filled `<MACHINE>_WL_<RUNFOLDER_NAME>.xlsx` produced by loading that copy via openpyxl, setting the named cells, and saving as `.xlsx`.

#### Scenario: First run for a session

- **WHEN** Simple mode runs for machine `LA2` against runfolder `2026-06-16_143022`
- **THEN** the folder `/out/LA2/WL/LA2_WL_2026-06-16_143022/` is created, containing `LA2_WL_2026-06-16_143022.xltx` (verbatim copy of the template) and `LA2_WL_2026-06-16_143022.xlsx` (filled)

#### Scenario: Re-run overwrites same session

- **WHEN** Advanced mode re-runs analysis with different parameters for the same machine + runfolder
- **THEN** the same folder is reused; both files are overwritten with the new result

### Requirement: Summary sheet with 24 named cells

The xlsx summary sheet (first sheet) SHALL define and populate 24 named cells organised in three groups:

- **Session metadata (3):** `machine_name`, `session_date`, `num_total_images`
- **Clinical metrics (9):** `max_2d_cax_to_bb`, `median_2d_cax_to_bb`, `mean_2d_cax_to_bb`, `gantry_3d_iso`, `coll_2d_iso`, `couch_2d_iso`, `bb_shift_x`, `bb_shift_y`, `bb_shift_z`
- **Secondary metrics (12):** `max_2d_cax_to_epid`, `median_2d_cax_to_epid`, `mean_2d_cax_to_epid`, `gantry_coll_3d_iso`, `max_gantry_rms`, `max_coll_rms`, `max_couch_rms`, `max_epid_rms`, `num_gantry_images`, `num_coll_images`, `num_couch_images`, `num_gantry_coll_images`

The xltx template SHALL pre-define these as Excel defined names. The xlsx writer SHALL populate them by resolving each defined name to its target cell and setting the cell value.

#### Scenario: All named cells populated

- **WHEN** the xlsx is written
- **THEN** every one of the 24 defined names resolves to a cell whose value matches the corresponding field in `WLAnalysisResult.summary`

#### Scenario: Named cell resolves correctly after template edit

- **WHEN** the xltx template is edited to move `max_2d_cax_to_bb` from cell `B4` to cell `C7`
- **THEN** the xlsx writer resolves the defined name to `C7` and writes the value there — no app code change required

#### Scenario: Missing named cell in template

- **WHEN** the xltx template is missing one of the 24 defined names
- **THEN** config validation catches this at app startup (the template is parsed once and checked against the required name set), and the app refuses to start with a clear error

### Requirement: Per-image sheets with header-based tables

The xlsx SHALL contain one additional sheet per image. Sheet titles SHALL be sourced from `WLAnalysisResult.image_keys` (e.g. `G0B0P0`, `G90B45P0`) — these keys are derived from pylinac's `keyed_image_details` ordering. Sheet contents SHALL be sourced from the parallel-array entry in `WLAnalysisResult.image_details` (i.e. sheet title `image_keys[i]` is populated from `image_details[i]`). Each per-image sheet SHALL contain a header-based table: field name in column A, value in column B. No per-image defined names SHALL be created.

#### Scenario: Sheet per image

- **WHEN** analysis produces 17 images
- **THEN** the xlsx contains 17 per-image sheets in addition to the summary sheet; sheet titles are the entries of `WLAnalysisResult.image_keys` (e.g. `G0B0P0`, `G90B0P0`, etc.)

#### Scenario: Per-image sheet contents

- **WHEN** sheet `G90B45P0` is opened
- **THEN** column A lists field names (`variable_axis`, `cax2bb_distance`, `cax2epid_distance`, `bb_location`, etc.) and column B lists the corresponding values from the `image_details[i]` entry whose key matches `G90B45P0`

#### Scenario: Title/content alignment

- **WHEN** `image_keys[i]` is `G90B45P0`
- **THEN** the sheet titled `G90B45P0` is populated from `image_details[i]` — the two arrays are parallel; indices never diverge

### Requirement: Excel sheet name sanitisation

Sheet names SHALL conform to Excel's constraints: ≤31 characters, no `\`, `/`, `?`, `*`, `[`, `]`, `:` characters. Pylinac axis keys (e.g. `G0B0P0`) typically satisfy these constraints, but the writer SHALL apply a defensive sanitisation pass that replaces forbidden characters with `_` and truncates to 31 chars with a `…` suffix if needed.

#### Scenario: Safe key passes through

- **WHEN** the pylinac key is `G0B0P0`
- **THEN** the sheet name is `G0B0P0` (no transformation)

#### Scenario: Hypothetically long key

- **WHEN** the pylinac key is hypothetically `G180B270P315_extra_metadata_beyond_31_chars`
- **THEN** the sheet name is `G180B270P315_extra_metadata_be…` (truncated to 30 chars + `…`, total 31)

### Requirement: Template version stamp

The xltx template SHALL include an additional named cell `template_version` (e.g. `2026-06`) that the writer populates from a value in the app's `pyproject.toml` or a dedicated constant. This allows MyQA-side detection of template drift if the template is updated and old xlsx files are re-imported.

#### Scenario: Version stamped

- **WHEN** the xlsx is written
- **THEN** the `template_version` defined name resolves to a cell containing the current template version string

### Requirement: Template validation at app startup

On startup, the app SHALL load `templates/winston_lutz.xltx`, enumerate its defined names, and verify that all 25 required names (24 metrics + `template_version`) are present. If any are missing, the app SHALL refuse to start and log the missing names.

#### Scenario: Template complete

- **WHEN** the template contains all 25 required defined names
- **THEN** the app starts normally

#### Scenario: Template missing names

- **WHEN** the template is missing `max_2d_cax_to_bb` and `template_version`
- **THEN** the app refuses to start, logging "WL template missing required defined names: max_2d_cax_to_bb, template_version"

### Requirement: Tolerance is not written to xlsx

The UI-only `tolerance_mm` value SHALL NOT be written to the xlsx. The xlsx represents the analysis result, not the pass/fail policy. Tolerances are a display concern of the Streamlit app and a policy concern of MyQA.

#### Scenario: Tolerance excluded

- **WHEN** the xlsx is written
- **THEN** no named cell or per-image field contains the tolerance value
