# cbct-result-export Specification

## Purpose
TBD - created by archiving change add-catphan-page. Update Purpose after archive.
## Requirements
### Requirement: Per-session paired xltx + xlsx

For every CatPhan analysis run (Simple or Advanced), the system SHALL create a session output folder at `/out/<CATEGORY>/<MACHINE_DISPLAY>/<PYLINAC_SUBFOLDER>/CatPhan/<MACHINE>_CP_<RUNFOLDER_NAME>/` (where `CATEGORY` defaults to `"Clinical QA"`, `MACHINE_DISPLAY` is the machine's `display_name`, `PYLINAC_SUBFOLDER` defaults to `"Pylinac"`) — mirroring the WL page's output layout with `CatPhan/` substituted for `WL/` and `_CP_` for `_WL_`. The folder SHALL contain two files: a copy of `templates/catphan_504.xltx` renamed to `<MACHINE>_CP_<RUNFOLDER_NAME>.xltx`, and a filled `<MACHINE>_CP_<RUNFOLDER_NAME>.xlsx` produced by loading that copy via openpyxl, setting the named cells, and saving as `.xlsx`.

#### Scenario: First run for a session

- **WHEN** Simple mode runs for machine `LA2` (display_name `"LA2 (TrueBeam)"`) against runfolder `2026-06-16_monthly`
- **THEN** the folder `/out/Clinical QA/LA2 (TrueBeam)/Pylinac/CatPhan/LA2_CP_2026-06-16_monthly/` is created, containing `LA2_CP_2026-06-16_monthly.xltx` (verbatim copy of the template) and `LA2_CP_2026-06-16_monthly.xlsx` (filled)

#### Scenario: Re-run overwrites same session

- **WHEN** Advanced mode re-runs analysis with different parameters for the same machine + runfolder
- **THEN** the same folder is reused; both files are overwritten with the new result

### Requirement: Summary sheet with 19 named cells

The CatPhan xlsx summary sheet (first sheet) SHALL define and populate 19 named cells organised in nine groups:

- **Session metadata (3):** `machine_name`, `session_date`, `num_images`
- **Pass/fail flags (4):** `hu_linearity_passed`, `geometry_passed`, `uniformity_passed`, `thickness_passed`
- **Geometry (2):** `measured_slice_thickness_mm`, `avg_line_distance_mm`
- **Uniformity (2):** `uniformity_index`, `integral_non_uniformity`
- **Contrast (2):** `low_contrast_visibility`, `num_rois_seen`
- **Resolution (2):** `mtf_50_lp_mm`, `mtf_90_lp_mm`
- **NPS (2):** `nps_avg_power`, `nps_max_freq`
- **Orientation (1):** `catphan_roll_deg`
- **Template version (1):** `template_version`

The xltx template SHALL pre-define these as Excel defined names. The xlsx writer SHALL populate them by resolving each defined name to its target cell and setting the cell value.

#### Scenario: All named cells populated

- **WHEN** the xlsx is written
- **THEN** every one of the 19 defined names resolves to a cell whose value matches the corresponding field in `CatPhanAnalysisResult.summary`

#### Scenario: Named cell resolves correctly after template edit

- **WHEN** the xltx template is edited to move `mtf_50_lp_mm` from cell `B12` to cell `D8`
- **THEN** the xlsx writer resolves the defined name to `D8` and writes the value there — no app code change required

#### Scenario: Missing named cell in template

- **WHEN** the xltx template is missing one of the 19 defined names AND any machine has `catphan` configured
- **THEN** config validation catches this at app startup (the template is parsed once and checked against the required name set), and the app refuses to start with a clear error

### Requirement: Per-CTP-module sheets with header-based tables

The CatPhan xlsx SHALL contain four additional sheets — one per CTP module — sourced from the corresponding field of `CatPhanAnalysisResult`:

- Sheet `CTP404` populated from `result.ctp404` (HU linearity table: 7 materials × name/nominal/measured/difference/stdev/passed; geometry: avg + 4 line distances; thickness: measured, num_slices_combined, straddle used)
- Sheet `CTP486` populated from `result.ctp486` (uniformity ROIs: 5 regions × name/value/nominal/difference/stdev/passed; uniformity indices; NPS summary)
- Sheet `CTP528` populated from `result.ctp528` (MTF table: 9 rows for 10%–90% in steps of 10, with lp/mm values)
- Sheet `CTP515` populated from `result.ctp515` (low contrast ROIs: variable rows × size/contrast/CNR/SNR/visibility/threshold/passed)

Each per-module sheet SHALL contain a header-based table (column headers in row 1, values in subsequent rows). No per-ROI defined names SHALL be created.

#### Scenario: One sheet per CTP module

- **WHEN** the xlsx is written
- **THEN** it contains exactly 5 sheets: summary + `CTP404` + `CTP486` + `CTP528` + `CTP515`

#### Scenario: CTP404 sheet contents

- **WHEN** sheet `CTP404` is opened
- **THEN** it contains the HU linearity table with all 7 materials (Air, PMP, LDPE, Poly, Acrylic, Delrin, Teflon), the geometry summary, and the slice thickness fields

#### Scenario: CTP528 sheet contents

- **WHEN** sheet `CTP528` is opened
- **THEN** it contains the MTF table with 9 rows (10% to 90% in steps of 10) and their corresponding lp/mm values

### Requirement: Template version stamp

The xltx template SHALL include the named cell `template_version`. The writer SHALL populate it from a constant in the app (suggested: `2026-06-cp` — module-suffixed to distinguish from WL's `2026-06`). This allows MyQA-side detection of template drift.

#### Scenario: Version stamped

- **WHEN** the xlsx is written
- **THEN** the `template_version` defined name resolves to a cell containing `2026-06-cp`

### Requirement: Template validation at app startup

At startup, if any machine in `machines.yaml` has `catphan` configured, the app SHALL load `templates/catphan_504.xltx`, enumerate its defined names, and verify that all 19 required names are present. If any are missing, the app SHALL refuse to start and log the missing names. If no machine has `catphan` configured, the template is not required and not validated.

#### Scenario: Template complete

- **WHEN** the template contains all 19 required defined names AND at least one machine has `catphan` configured
- **THEN** the app starts normally and the CatPhan page is available

#### Scenario: Template missing names

- **WHEN** the template is missing `mtf_50_lp_mm` and `template_version`, and at least one machine has `catphan` configured
- **THEN** the app refuses to start, logging "CatPhan template missing required defined names: mtf_50_lp_mm, template_version"

#### Scenario: CatPhan not configured, template absent

- **WHEN** no machine has `catphan` configured and `templates/catphan_504.xltx` does not exist
- **THEN** the app starts normally; the CatPhan page is reachable but renders with an empty machine dropdown and a "No machines have CatPhan configured" banner (Streamlit auto-discovers `pages/`, so the page is always present in the sidebar)

### Requirement: No tolerance field exists for CatPhan

Unlike WL (which has a UI-only `tolerance_mm` that must be excluded from the xlsx), CatPhan has no equivalent UI tolerance field. The xlsx SHALL NOT contain any field named `tolerance_mm` or similar UI-tolerance in any sheet. The four pass/fail flags (`hu_linearity_passed`, `geometry_passed`, `uniformity_passed`, `thickness_passed`) written to the summary sheet come from pylinac's own per-test tolerances (`hu_tolerance`, `scaling_tolerance`, `slice_thickness_tolerance`), which are analysis parameters but are NOT separately written to the xlsx (the per-CTP-module sheets contain measured values, not the tolerance inputs).

#### Scenario: No tolerance field written

- **WHEN** the xlsx is written
- **THEN** no field named `tolerance_mm` or similar UI-tolerance appears in any sheet (because no such field exists in the CatPhan config or UI)

