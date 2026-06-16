## Why

The WL page is built and frozen, but it's currently the only module. Physicists also run CatPhan 504 CBCT QA on the same linacs and currently have no parallel web-GUI path. Adding CatPhan as the second module page also creates the moment to extract shared utilities (runfolder discovery, session-output path builder, paired-xltx writer, caching pattern) out of the WL implementation while the second use case is concrete — before the third page (FieldProfile) makes the duplication worse.

## What Changes

- Add `pages/2_CatPhan.py` providing Simple and Advanced modes for `pylinac.CatPhan504` analysis, mirroring the WL page's UX (one-click Simple mode with centre defaults; Advanced mode for service investigation with re-run and tabbed exploration)
- Refactor shared concerns out of the WL implementation into reusable modules under `core/`: `runfolder.py` (mtime-based newest-subdirectory discovery + DICOM count + mtime helpers), `session_io.py` (per-session output folder creation + paired xltx copy), `excel_helpers.py` (`set_named_cell` + `sanitise_sheet_name`), `caching.py` (the `@st.cache_data` + session_state lifecycle pattern). The WL page is updated to import from these modules — **no behavior change**
- Modify the `machine-config` schema so each machine's `dicom_roots` is a multi-module dict where `winston_lutz` and `catphan` are each independently optional, with validation that at least one module root is configured per machine; previously WL was required per machine, now both modules are independently optional
- Add `templates/catphan_504.xltx` with a summary sheet (~19 named cells: session metadata, pass/fail flags, key clinical scalars, NPS metrics, MTF metrics, template version) and four per-CTP-module sheets (CTP404, CTP486, CTP528, CTP515) using header-based tables
- Add `core/cbct_runner.py` wrapping `pylinac.CatPhan504`, returning a `CatPhanAnalysisResult` dataclass with the summary dict, per-CTP-module detail dicts, and plotly-ready arrays (MTF curve, ROI position scatter)
- Update Simple mode to hide the CatPhan page for machines where it is not configured (per-machine optional)
- Hardcode `CatPhan504` (no model selector) — the centre has 504 only

## Capabilities

### New Capabilities

- `cbct-simple-mode`: One-click CatPhan 504 analysis flow — machine dropdown (only machines with CatPhan configured are selectable on this page), automatic newest-runfolder detection by mtime, defaults-driven analysis, paired xlsx/xltx output, success card with quick metrics + hand-off to Advanced mode; failures produce physicist-friendly messages with clear next steps and never display raw pylinac stack traces
- `cbct-advanced-mode`: Interactive CatPhan 504 exploration — sidebar of pylinac `analyze()` parameters (10 scalar params; dict-typed `expected_hu_values` stays config-only), re-run, five tabs (Overview / CTP404 / CTP486 / CTP528 / CTP515), per-CTP-module drill-down including MTF curve and ROI tables, xlsx download. Full pylinac errors and tracebacks ARE surfaced inline in Advanced mode (contrasting with Simple mode's hidden-traceback posture). No separate UI tolerance widget — CatPhan's four pass/fail flags (`hu_linearity_passed`, `geometry_passed`, `uniformity_passed`, `thickness_passed`) are computed by pylinac from the per-test tolerances (`hu_tolerance`, `scaling_tolerance`, `slice_thickness_tolerance`) and are the canonical pass/fail signal; unlike WL's single `max_2d_cax_to_bb` metric, CatPhan has no single "primary metric" to gate against a separate UI tolerance.
- `cbct-result-export`: CatPhan 504 Excel output contract — paired `.xltx` + `.xlsx` per session at `/out/<CATEGORY>/<MACHINE_DISPLAY>/<PYLINAC_SUBFOLDER>/CatPhan/<MACHINE>_CP_<RUNFOLDER>/` (mirrors WL's path layout), summary sheet with 19 named cells (`machine_name`, `session_date`, `num_images`, `hu_linearity_passed`, `geometry_passed`, `uniformity_passed`, `thickness_passed`, `measured_slice_thickness_mm`, `avg_line_distance_mm`, `uniformity_index`, `integral_non_uniformity`, `low_contrast_visibility`, `num_rois_seen`, `mtf_50_lp_mm`, `mtf_90_lp_mm`, `nps_avg_power`, `nps_max_freq`, `catphan_roll_deg`, `template_version`), four per-CTP-module sheets with header-based tables (CTP404 HU linearity + geometry + thickness; CTP486 uniformity + NPS; CTP528 MTF table; CTP515 low contrast ROIs)

### Modified Capabilities

- `machine-config`: The `machines.<M>.dicom_roots` schema changes from "winston_lutz required per machine" to "multi-module dict where winston_lutz and catphan are each independently optional, validated such that at least one module root is configured per machine and each configured root exists on the filesystem at startup". The `analysis_defaults.catphan` section requires `hu_tolerance`, `scaling_tolerance`, `slice_thickness_tolerance` (all floats); all other pylinac CatPhan `analyze()` parameters are optional with pylinac fallback. The existing `analysis_defaults.winston_lutz` section (including its UI-only `tolerance_mm`) is unchanged.

## Impact

- **New code**: `pages/2_CatPhan.py`, `core/cbct_runner.py`, `core/runfolder.py`, `core/session_io.py`, `core/excel_helpers.py`, `core/caching.py`, `templates/catphan_504.xltx`, plus tests
- **Modified code**: `core/config.py` (multi-module schema), `pages/1_Winston_Lutz.py` (import from extracted utilities), `core/excel_writer.py` (now uses shared `excel_helpers`), `core/wl_runner.py` (now uses shared `runfolder` and `caching`)
- **New dependencies**: none beyond what WL already requires
- **External systems**: hospital DICOM share must contain per-machine `CatPhan/` subdirectories where applicable; hospital output share gets a `<CATEGORY>/<MACHINE_DISPLAY>/<PYLINAC_SUBFOLDER>/CatPhan/` subtree (mirroring WL's output layout); MyQA imports a new xlsx shape (the CatPhan summary sheet's 19 named cells)
- **Operator action required**: operators must add a `catphan:` key under `dicom_roots` in `machines.yaml` for each machine that adopts CatPhan QA; the WL config field remains unchanged for machines that don't adopt CatPhan
- **No regression** to WL — the refactor preserves behavior; WL specs remain the contract

## Non-goals

- **FieldProfile page** — separate future change (`add-field-profile-page`)
- **TrajectoryLog page** — deferred indefinitely; structurally different (no `analyze()` / `results_data()`)
- **Other CatPhan models (503, 600, 604)** — centre has 504 only; adding a model selector is YAGNI
- **Full `PageProtocol` abstraction** — premature; result types and parameter types differ too much per module. This change extracts utilities, not abstractions. The next change (FieldProfile) will revisit whether a protocol is warranted.
- **Per-machine CatPhan overrides** — centre-wide `analysis_defaults.catphan` (same posture as WL)
- **Refactoring the WL spec** — WL requirements are unchanged; only WL's implementation moves
