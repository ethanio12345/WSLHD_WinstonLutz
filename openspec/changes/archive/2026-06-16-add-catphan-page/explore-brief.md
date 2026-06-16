# Explore Brief — add-catphan-page

## What we're building

Second module page for the pylinac GUI: CatPhan 504 CBCT QA. Mirrors the WL page's Simple/Advanced mode pattern. Also extracts shared utilities from the WL implementation so the third page (FieldProfile, future change) can build on them.

## Scope

- Add `pages/2_CatPhan.py` (Simple + Advanced modes for CatPhan 504)
- Refactor shared concerns out of WL into reusable modules (runfolder discovery, session-output path builder, paired xltx+xlsx writer pattern, cache decorator)
- Modify `machine-config` to support per-machine multi-module configuration (WL root currently required → both WL and CatPhan become independently optional per machine)
- NO behavior change to existing WL page (only implementation moves)
- FieldProfile and TrajectoryLog are future changes

## Alternatives rejected

| Alternative | Why rejected |
|---|---|
| One mega-change adding all 3 remaining modules | Too big; CatPhan is closest in shape to WL and gives cleanest abstraction signal. Build incrementally. |
| Pure additive CatPhan (no refactor) | Duplicated runfolder discovery, session-output builder, paired-writer, etc. Make the change do the refactor while signal is fresh. |
| Full `PageProtocol` abstraction now | Premature. Result types and parameter types differ too much per module for a tight Protocol. Extract utilities, not abstractions. |
| TrajectoryLog in this change | Wrong shape (no `analyze()`, no `results_data()`); user confirmed deferral. |
| Other CatPhan models (503, 600, 604) | Centre has 504 only. Hardcoding avoids a model selector and simplifies the xltx contract. |
| Flat named-cells xlsx for CatPhan | ~50+ cells across 4 CTP modules is unmaintainable. Use summary sheet (~18 cells) + per-CTP-module sheets. |
| CatPhan per-machine DICOM root required | WL is required (existing centres depend); CatPhan should be optional per machine so the change is purely additive for sites that haven't adopted it. |

## Chosen architecture (decisions locked)

- **One xltx + one xlsx per session** at `/out/<MACHINE>/CatPhan/<MACHINE>_CP_<RUNFOLDER>/`, paired (same as WL pattern).
- **Summary sheet with ~18 named cells** (metadata, pass/fail flags, key scalars) + **4 per-CTP-module sheets** (CTP404, CTP486, CTP528, CTP515) using header-based tables (no per-ROI named cells).
- **Config schema**: `machines.<M>.dicom_roots` is a dict; `winston_lutz` and `catphan` are both optional, with validation that at least one is present per machine. Each configured root must exist at startup. `analysis_defaults.catphan` follows the same required/optional split pattern as `winston_lutz` (`hu_tolerance`, `scaling_tolerance`, `slice_thickness_tolerance` required; others optional with pylinac defaults).
- **Hardcoded `CatPhan504`** class (no runtime model selector).
- **Advanced mode tabs**: Overview / CTP404 / CTP486 / CTP528 / CTP515 (5 tabs — module-driven, not WL-driven).
- **Refactor scope**:
  - Extract `core/runfolder.py` (find_newest_runfolder, count_dicoms, runfolder_mtime)
  - Extract `core/session_io.py` (build_session_folder_path, copy_template_to_session, ensure_session_folder)
  - Extract `core/excel_helpers.py` (set_named_cell, sanitise_sheet_name) — keep `write_session_output` per-module since metric mappings differ
  - Extract `core/caching.py` (the `@st.cache_data` decorator pattern + session_state lifecycle helpers)
  - WL page imports these utilities (no behavior change)
- **Caching key for CatPhan**: `(machine_id, runfolder_path, hu_tolerance, scaling_tolerance, slice_thickness_tolerance, thickness_slice_straddle, dicom_file_count, runfolder_mtime)` + the optional override params if set.
- **Result type**: new `CatPhanAnalysisResult` dataclass (NOT shoehorned into WL's). Holds summary dict, per-CTP-module dicts, plotly-ready arrays (MTF curve, ROI positions).
- **Error handling**: same posture as WL (Simple = friendly messages + log; Advanced = full errors).
- **Hand-off**: same Simple→Advanced pattern via `st.session_state["cp_result"]`.

## Named cells contract (summary sheet, ~18 cells)

**Session metadata (3):** `machine_name`, `session_date`, `num_images`
**Pass/fail flags (4):** `hu_linearity_passed`, `geometry_passed`, `uniformity_passed`, `thickness_passed`
**Geometry (2):** `measured_slice_thickness_mm`, `avg_line_distance_mm`
**Uniformity (2):** `uniformity_index`, `integral_non_uniformity`
**Contrast (2):** `low_contrast_visibility`, `num_rois_seen`
**Resolution (2):** `mtf_50_lp_mm`, `mtf_90_lp_mm`
**NPS (2):** `nps_avg_power`, `nps_max_freq`
**Orientation (1):** `catphan_roll_deg`
**Template version (1):** `template_version`

Total: 19 named cells (3 + 4 + 2 + 2 + 2 + 2 + 2 + 1 + 1). Each per-CTP-module sheet is a header-based table (no named cells within).

## Open questions (non-blocking, can be captured in design)

1. Should `low_contrast_visibility` and `num_rois_seen` both be in summary, or just one? (Recommend both — different clinical meanings.)
2. MTF in summary: 50% and 90% are conventional; should we also include 30% and 70%? (Recommend just 50% and 90% in summary; full 10–90 table in CTP528 sheet.)
3. Should `template_version` be `2026-06-cp` (module-suffixed) to distinguish from the WL template version? (Recommend yes — MyQA can disambiguate.)
4. `thickness_slice_straddle` default — `auto` (pylinac default) or `1` (deterministic)? (Recommend `auto` per pylinac default; surface as Advanced-mode override.)
5. For machines where CatPhan is not configured, should the CatPhan page be hidden from the module selector, or shown-but-disabled? (Recommend hidden — cleaner UI.)
