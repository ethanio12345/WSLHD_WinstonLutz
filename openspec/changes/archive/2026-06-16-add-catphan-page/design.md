## Context

The WL change shipped a single-page Streamlit app. Three structural facts drive this change:

1. The WL implementation has shared concerns interleaved with WL-specific logic (runfolder discovery, session-output paths, paired-xltx writer, caching pattern). FieldProfile is queued as the third page — duplicating these concerns a second time would be the rule-of-three violation.
2. The centre has CatPhan 504 only — no model selector, no per-model xltx variants.
3. The CatPhan result is structurally different from WL: nested by CTP module rather than flat-and-per-image. The xlsx contract reflects this (summary + per-module sheets).

Constraints from exploration:
- CatPhan root in `machines.yaml` is optional per machine (WL was previously required; both become independently optional with at-least-one validation).
- Centre-wide `analysis_defaults.catphan` (no per-machine overrides).
- Hardcoded `CatPhan504` class.
- Refactor preserves WL behavior exactly — the WL specs are canonical and unchanged.

## Goals / Non-Goals

**Goals:**
- Add the CatPhan 504 page (Simple + Advanced modes) producing a MyQA-importable xlsx
- Extract shared utilities from WL into `core/` modules so the third page (FieldProfile) builds on them
- Modify `machine-config` schema to support multi-module per machine
- Preserve WL behavior (refactor is implementation-only; WL specs unchanged)

**Non-Goals:**
- FieldProfile page (separate future change)
- TrajectoryLog page (deferred indefinitely)
- Other CatPhan models (503/600/604)
- Full `PageProtocol` abstraction (premature; this change extracts utilities, not abstractions)
- Per-machine CatPhan parameter overrides (centre-wide defaults only)
- Refactoring WL spec (WL requirements unchanged)

## Decisions

### D1: Refactor boundaries — extract utilities, not abstractions

Four utility modules extracted from the WL implementation:

```
core/
  runfolder.py         ← find_newest_runfolder, count_dicoms, runfolder_mtime
  session_io.py        ← build_session_folder, copy_template_to_session, ensure_session_folder
  excel_helpers.py     ← set_named_cell, sanitise_sheet_name
  caching.py           ← session_state lifecycle helpers (init_session_state, get_cached_obj, invalidate)
```

**Note on `caching.py`**: the existing WL code uses raw `st.session_state["wl_result"] = ...` patterns directly in `pages/1_Winston_Lutz.py`. Extracting `init_session_state` / `get_cached_obj` / `invalidate` helpers is therefore a **new abstraction layer**, not a pure code move. The WL page must be refactored to use these helpers, and the WL test suite must still pass post-refactor. The helpers are simple (thin wrappers around `st.session_state` access with consistent key naming), but they introduce a behavioural surface that D9's "no behavior change" claim relies on. Tests must cover the helper boundary.

**`core/ui_utils.py`** (already exists in the WL implementation, contains `render_asset` and `render_mode_toggle`) is NOT touched by this refactor — it remains shared as-is. Future FieldProfile page will reuse `render_asset` for the Fry meme and `render_mode_toggle` for the sidebar mode switch.

What stays per-page:
- The pylinac class instantiation (`WinstonLutz` vs `CatPhan504`)
- The pylinac `analyze()` parameter set (different per module)
- The result dataclass (`WLAnalysisResult` vs `CatPhanAnalysisResult`) — types differ too much to share
- The `write_session_output` function (metric mappings differ; helpers like `set_named_cell` are shared but the orchestration is per-module)
- The Advanced-mode tab structure (different per module)

**Why not a `PageProtocol`?** The Protocol would have to be structural (duck-typed) because parameter and result types differ. The cost of the abstraction exceeds the benefit for 3 pages. Extract concrete helpers; defer the Protocol until a clear common interface emerges.

**Alternatives considered:**
- *Full `PageProtocol` now*: rejected — premature; result types and parameter types differ too much
- *Pure additive CatPhan (no refactor)*: rejected — duplicates runfolder discovery, session-io, excel helpers; the third page (FieldProfile) would duplicate again
- *Separate refactor-only change first*: rejected — refactor without a second user can go wrong; doing it as part of CatPhan means the refactor is informed by the second use case
- *Keep raw `st.session_state` access (don't extract `caching.py`)*: rejected — duplicates the session_state key naming convention across pages; a thin wrapper ensures consistency

### D2: Multi-module `machines.yaml` schema

```yaml
machines:
  LA2:
    display_name: "LA2 (TrueBeam)"
    dicom_roots:
      winston_lutz: /data/LA2/WinstonLutz    # now optional
      catphan: /data/LA2/CatPhan              # now optional, new
      # field_profile: /data/LA2/FieldProfile  (future change)

output:
  root: /out

analysis_defaults:
  winston_lutz:                               # unchanged from WL change
    bb_size_mm: 5.0
    machine_scale: VARIAN_IEC
    tolerance_mm: 1.0
  catphan:                                    # new
    hu_tolerance: 40                          # required
    scaling_tolerance: 0.5                    # required (mm)
    slice_thickness_tolerance: 0.5            # required (mm)
    thickness_slice_straddle: auto            # optional (int or 'auto'; pylinac default 'auto')
    # optional: expected_hu_values (dict), x_adjustment, y_adjustment,
    # angle_adjustment, roi_size_factor, scaling_factor, minimum_rois_seen
    # NOTE: no tolerance_mm UI field for CatPhan — see D4.

assets:
  fry_meme_path: /assets/fry_money.png
  logo_path: /assets/logo.png
```

**Validation rules:**
- `dicom_roots` is required per machine
- `dicom_roots` must contain at least one of `winston_lutz`, `catphan` (extensible to future module keys)
- Each configured root must exist on the filesystem at startup
- For each configured module, the corresponding `analysis_defaults.<module>` section must be present in config with all required keys

**Migration**: existing `machines.yaml` files (WL only) load without modification — WL stays where it was; CatPhan is purely additive. Operators add a `catphan:` key under `dicom_roots` for machines that adopt CatPhan QA.

**Alternatives considered:**
- *Keep WL required, CatPhan optional*: rejected — locks existing centres into a WL-only model; some machines may have CatPhan but not WL (different QA cadences)
- *Allow empty `dicom_roots`*: rejected — a machine with no modules configured serves no purpose

### D3: CatPhan 504 page structure (Simple mode) — separate page

Per the proposal, CatPhan is a separate Streamlit page (`pages/2_CatPhan.py`), NOT a unified page with a module dropdown. Streamlit's multi-page app convention auto-discovers `pages/` next to the entry file.

```
Sidebar (pages/2_CatPhan.py):
  Mode: ( Simple | Advanced )
  Machine: dropdown — only machines with `dicom_roots.catphan` configured

Main area:
  [preview of newest CatPhan runfolder + DICOM count]
  [Shut Up and Give Me My MyQA Results button]
  [success card with metrics + hand-off]
```

**Machine dropdown filtering**: the CatPhan page's machine dropdown lists only machines where `dicom_roots.catphan` is present and exists. Machines without CatPhan configured are not selectable from this page (but remain selectable from `pages/1_Winston_Lutz.py` if WL is configured).

**Button label**: identical to WL's (`"Shut Up and Give Me My MyQA Results"`) for centre-wide consistency. Not configurable per module (dropped from earlier draft — adds config surface for no real value).

**Navigation between pages**: Streamlit's sidebar shows the page list (`1_Winston_Lutz`, `2_CatPhan`). The user clicks the page they want. There is no in-app module selector.

**Future modules**: when FieldProfile is added, it becomes `pages/3_Field_Profile.py` with the same pattern. The page abstraction question (whether to extract a shared page-render helper) is deferred until at least 3 module pages exist.

**Alternatives considered:**
- *Unified page with Module dropdown*: rejected — contradicts proposal's separate-page model; Streamlit's `pages/` convention is the natural fit for multi-module
- *Per-module button label*: rejected — centre-wide consistency > per-module flavour; adds config surface for no real value

### D4: CatPhan 504 Advanced mode — 5 tabs

Module-driven tabs (not WL's 4-tab structure):

```
Tab: Overview       → summary metrics table (the 19 named-cell values, minus metadata)
                        + the four pylinac-computed pass/fail flags
                        + "Analysed with: ..." params_used line

Tab: CTP404         → HU linearity sub-image (matplotlib via st.pyplot)
                        + HU ROIs table (7 materials × value/nominal/diff/passed)
                        + geometry (avg_line_distance + 4 line distances)
                        + slice thickness info

Tab: CTP486         → uniformity sub-image
                        + 5 ROIs table (Top/Right/Bottom/Left/Center)
                        + uniformity_index, integral_non_uniformity
                        + NPS plot (ct.plot_noise_power_spectrum equivalent)

Tab: CTP528         → spatial resolution sub-image
                        + MTF curve plot (plotly; x=lp/mm, y=relative MTF)
                        + MTF table (10% to 90% in steps of 10)

Tab: CTP515         → low contrast sub-image
                        + ROI table (per-ROI visibility, contrast, CNR, SNR, passed)
                        + num_rois_seen summary
```

**Sidebar (Advanced)**:
```
Machine:           LA2 ▼
Runfolder:         2026-06-16_143022 ▼
── Analysis parameters ──
HU tolerance:      [40]
Scaling tolerance: [0.5]  (mm)
Slice thickness:   [0.5]  (mm)
Straddle:          [auto ▼]   (auto | 0 | 1 | 2 | 3)
X adjustment:      [0]
Y adjustment:      [0]
Angle adjustment:  [0]
ROI size factor:   [1.0]
Scaling factor:    [1.0]
Min ROIs seen:     [3]
[▶ Re-run analysis]
[💾 Download xlsx]
```

**No separate UI tolerance widget** (contrast with WL's `tolerance_mm`). CatPhan's four pass/fail flags (`hu_linearity_passed`, `geometry_passed`, `uniformity_passed`, `thickness_passed`) are computed by pylinac from the per-test tolerances above (`hu_tolerance`, `scaling_tolerance`, `slice_thickness_tolerance`) and are the canonical pass/fail signal. Unlike WL's `max_2d_cax_to_bb` which needs a UI tolerance to gate pass/fail, CatPhan has no single "primary metric" — the four flags cover it.

**`expected_hu_values` is config-only**: this parameter is a dict (e.g. `{"Air": -999, "PMP": -203}`) and is not surfaced in the Advanced sidebar. To override material HU values, operators edit `machines.yaml` and restart.

**`st.session_state` keys for CatPhan** (mirroring WL's pattern, namespaced):
- `cp_result` — `CatPhanAnalysisResult` (Simple→Advanced hand-off payload)
- `cp_obj` — live `pylinac.CatPhan504` instance (lazy-init on first Advanced render)
- `cp_params` — current sidebar parameters

**Alternatives considered:**
- *4 tabs like WL*: rejected — CatPhan's data is naturally per-CTP-module; collapsing into fewer tabs hurts navigation
- *6 tabs (add "All Modules" montage tab)*: rejected — pylinac's `plot_analyzed_image()` already produces the montage; the Overview tab can include it as a static figure

### D5: `CatPhanAnalysisResult` dataclass (in `core/result_types.py`)

Lives alongside the existing `WLAnalysisResult` in `core/result_types.py` — same file, sibling class.

```python
@dataclass(frozen=True)
class CatPhanAnalysisResult:
    # Identity
    machine_id: str
    runfolder_path: str
    session_date: str                      # ISO 8601, from first DICOM's AcquisitionDate
    # Summary (the 19 named-cell values, flat dict)
    summary: dict[str, float | int | str | bool]
    # Per-CTP-module detail dicts (from results_data(as_dict=True))
    ctp404: dict                           # hu_rois, geometry, thickness
    ctp486: dict                           # rois, uniformity, NPS
    ctp528: dict                           # mtf_lp_mm, roi_settings
    ctp515: dict                           # roi_results, num_rois_seen
    # Plotly-ready arrays (precomputed)
    mtf_curve: dict                        # {x: lp/mm values, y: relative MTF values}
    hu_linearity_scatter: dict             # {nominal: [...], measured: [...], names: [...]}
    # Parameters used
    params_used: dict
```

Frozen dataclass — **picklable** (which is what `@st.cache_data` actually requires; it does not need hashable since the cache key is computed from the input args, not the return value). Same property as the existing `WLAnalysisResult`.

**MTF curve precomputation**: pylinac exposes `mtf_lp_mm` as a dict `{10: 0.748, 20: 0.65, ...}`. We reformat into `{x: [10, 20, ..., 90], y: [0.748, 0.65, ...]}` for plotly line plot.

**HU linearity scatter precomputation**: from `ctp404.hu_rois`, build `{nominal: [...], measured: [...], names: [...]}` for a nominal-vs-measured scatter with hover labels.

### D6: Paired xltx + xlsx pattern (shared helper, faithful extraction)

The session-output writer pattern is extracted from the existing `_session_folder` in `core/excel_writer.py` (NOT redesigned). The existing layout is canonical and matches the (now-corrected) `wl-result-export` spec:

```
/out/<CATEGORY>/<MACHINE_DISPLAY>/<PYLINAC_SUBFOLDER>/<MODULE>/<MACHINE>_<PREFIX>_<RUNFOLDER>/

e.g. /out/Clinical QA/LA2 (TrueBeam)/Pylinac/WL/LA2_WL_2026-06-16_143022/
     /out/Clinical QA/LA2 (TrueBeam)/Pylinac/CatPhan/LA2_CP_2026-06-16_143022/
```

The extracted helper:

```python
# core/session_io.py
def build_session_folder(
    output_root: Path,
    machine_id: str,
    machine_display_name: str,
    module_dir: str,                       # "WL" | "CatPhan"  (literal folder names)
    runfolder_name: str,
    file_prefix: str,                      # "WL" | "CP"
    category: str = "Clinical QA",
    pylinac_subfolder: str = "Pylinac",
) -> Path:
    """Build per-session folder.

    Mirrors the existing _session_folder in core/excel_writer.py but
    parameterised over module so both WL and CatPhan share the layout.
    """
    folder = (
        Path(output_root)
        / category
        / machine_display_name
        / pylinac_subfolder
        / module_dir
        / f"{machine_id}_{file_prefix}_{runfolder_name}"
    )
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def copy_template_to_session(
    template_path: Path,
    session_folder: Path,
    output_stem: str,                      # e.g. "LA2_CP_2026-06-16_143022"
) -> Path:
    """Copy the xltx template into the session folder, renamed to <stem>.xltx."""
    dst = session_folder / f"{output_stem}.xltx"
    shutil.copy(template_path, dst)
    return dst
```

**Module dispatch**: a small constant dict in `session_io.py` maps `module_id → (module_dir, file_prefix)`:
- `"winston_lutz" → ("WL", "WL")`
- `"catphan" → ("CatPhan", "CP")`

Future modules add entries here. The existing `_session_folder` in `core/excel_writer.py` is replaced by a call to `build_session_folder(..., module_dir="WL", file_prefix="WL", ...)` — same arguments, same output path, no behavior change.

The per-module `write_session_output` (one in `core/excel_writer.py` for WL, one new in `core/cbct_excel_writer.py` for CatPhan) then:
1. Calls `build_session_folder` + `copy_template_to_session`
2. Loads the copied xltx via openpyxl
3. Sets named cells via `excel_helpers.set_named_cell`
4. Writes per-module sheets (per-image for WL, per-CTP-module for CatPhan)
5. Saves as `.xlsx` with the same stem

**Alternatives considered:**
- *Redesign the path layout (flat `/out/<MACHINE>/<MODULE>/...`)*: rejected — would break the deployed WL behaviour and the (corrected) `wl-result-export` spec; also loses the human-friendly category/display_name grouping that MyQA-side browsing benefits from
- *Single `write_session_output` for both modules*: rejected — metric mappings differ; sharing introduces conditionals that obscure intent

### D7: Caching strategy for CatPhan

```python
@st.cache_data(show_spinner="Running CatPhan 504 analysis...")
def run_cbct_analysis(
    machine_id: str,
    runfolder_path: str,
    hu_tolerance: float,
    scaling_tolerance: float,
    slice_thickness_tolerance: float,
    thickness_slice_straddle: str | int,
    x_adjustment: float,
    y_adjustment: float,
    angle_adjustment: float,
    roi_size_factor: float,
    scaling_factor: float,
    minimum_rois_seen: int,
    dicom_file_count: int,                 # stale-cache mitigation
    runfolder_mtime: float,                # stale-cache mitigation
) -> CatPhanAnalysisResult:
    ...
```

Cache key includes all 10 analyze parameters + machine_id + the two stale-cache mitigations. Same pattern as WL.

**Note on `thickness_slice_straddle`**: pylinac accepts `'auto'` (string) or an integer. The cache key handles both via the value's hashability (strings and ints are both hashable).

### D8: xlsx template structure

`templates/catphan_504.xltx` defines:

```
Sheet 1 "Summary":
  - Session metadata row (3 cells: machine_name, session_date, num_images)
  - Pass/fail flags row (4 cells)
  - Clinical metrics table (10 cells across geometry/uniformity/contrast/resolution/NPS/orientation)
  - template_version cell (1 cell)
  → All 19 cells as Excel defined names
```

The 19 named cells (locked contract — enumerated in proposal, repeated here for design completeness):

| Group | Cells |
|---|---|
| Session metadata (3) | `machine_name`, `session_date`, `num_images` |
| Pass/fail flags (4) | `hu_linearity_passed`, `geometry_passed`, `uniformity_passed`, `thickness_passed` |
| Geometry (2) | `measured_slice_thickness_mm`, `avg_line_distance_mm` |
| Uniformity (2) | `uniformity_index`, `integral_non_uniformity` |
| Contrast (2) | `low_contrast_visibility`, `num_rois_seen` |
| Resolution (2) | `mtf_50_lp_mm`, `mtf_90_lp_mm` |
| NPS (2) | `nps_avg_power`, `nps_max_freq` |
| Orientation (1) | `catphan_roll_deg` |
| Template version (1) | `template_version` |

Per-module sheets:

```
Sheet 2 "CTP404":
  - HU linearity table (7 rows × 5 cols: name, nominal, measured, difference, passed)
  - Geometry summary (avg + 4 individual line distances)
  - Thickness (measured, num_slices_combined, straddle used)

Sheet 3 "CTP486":
  - Uniformity ROIs table (5 rows: Top/Right/Bottom/Left/Center)
  - Uniformity indices (uniformity_index, integral_non_uniformity)
  - NPS summary (avg_power, max_freq)

Sheet 4 "CTP528":
  - MTF table (9 rows: 10% to 90% in steps of 10, with lp/mm values)

Sheet 5 "CTP515":
  - Low contrast ROIs table (variable rows; per-ROI: size, contrast, CNR, SNR, visibility, passed)
```

Per-module sheets use header-based tables (no named cells within) — consistent with WL's per-image sheets.

**No tolerance to exclude** (contrast with WL): WL has a UI-only `tolerance_mm` that must be excluded from the xlsx; CatPhan has no equivalent UI tolerance (per D4), so there is nothing to exclude. The four pass/fail flags written to the summary sheet come from pylinac's own per-test tolerances, not from any UI widget.

**Template generation**: a one-time setup script `scripts/build_catphan_xltx_template.py` generates the xltx programmatically via openpyxl (same approach as WL's template). Sets `template_version` to `2026-06-cp` (module-suffixed to distinguish from WL's `2026-06`).

**Template validation at startup**: same pattern as WL — `core/config.py` load also validates `templates/catphan_504.xltx` has all 19 named cells defined. If the template is missing or incomplete AND any machine has `catphan` configured, the app refuses to start.

**Alternatives considered:**
- *Flat named cells for everything (~50 cells)*: rejected — unmaintainable template, pollution of MyQA namespace
- *One sheet per ROI within each CTP module*: rejected — header-based tables within a single per-module sheet is enough for browsing

### D9: Refactor migration path

The refactor touches 4 existing WL files:

| File | Change |
|---|---|
| `pages/1_Winston_Lutz.py` | Replace inline `find_newest_runfolder` call with `from core.runfolder import find_newest_runfolder`; replace inline session-state init with `from core.caching import init_session_state`; etc. |
| `core/wl_runner.py` | Replace inline `find_newest_runfolder` + `count_dicoms` + `runfolder_mtime` with `core.runfolder` imports |
| `core/excel_writer.py` | Replace inline `set_named_cell` + `sanitise_sheet_name` with `core.excel_helpers` imports; keep `write_session_output` here |
| `core/config.py` | Update pydantic models for multi-module schema (the only behavior-affecting change; covered by `machine-config` spec modification) |

**No behavior change guarantee**: the refactor must produce identical Simple-mode output and identical Advanced-mode UX for WL. The WL test suite (frozen) must pass without modification after the refactor. If a test fails, the refactor is wrong, not the test.

**Migration order**: do the refactor first (small commits, run WL tests after each), then layer CatPhan on top. Captured in tasks.md.

## Risks / Trade-offs

- **[Refactor breaks WL]** Extracting utilities may introduce subtle behavior changes.
  → Mitigation: WL test suite (frozen) must pass after refactor; CI gate. Tasks explicitly require running WL tests post-refactor before any CatPhan code is added.

- **[CatPhan DICOM directory shape]** CatPhan scans produce many DICOMs (often 100+ slices). The `count_dicoms` cache key is still meaningful but the count is large; this is fine.
  → No mitigation needed beyond the existing cache pattern.

- **[Per-machine optional CatPhan]** A machine may have WL configured but not CatPhan. The CatPhan page must hide that machine from its dropdown.
  → Mitigation: the CatPhan page's machine dropdown filters to machines with `dicom_roots.catphan` configured (D3). Documented in `cbct-simple-mode` spec.

- **[Template validation false-negative]** If `catphan` is configured for any machine but `templates/catphan_504.xltx` is missing, the app refuses to start — correct behaviour but operators need to know.
  → Mitigation: clear error message; documented in deployment runbook.

- **[Multi-module cache pollution]** `@st.cache_data` is global; WL and CatPhan cache keys must not collide.
  → Mitigation: cache functions are named differently (`run_wl_analysis` vs `run_cbct_analysis`) and Streamlit namespaces caches by function identity. No collision possible.

- **[Centering-change UX confusion]** Existing users see only `pages/1_Winston_Lutz.py` in the sidebar; after this change they also see `pages/2_CatPhan.py`. Streamlit shows the page list in the sidebar by default.
  → Mitigation: page names are descriptive (`1_Winston_Lutz`, `2_CatPhan`); no defaults to manage. Document the new page in the deployment runbook.

## Open Questions

1. **`minimum_rois_seen` default** — pylinac doesn't enforce a default; what's the centre's policy? (Recommend 3 — conventional for monthly CatPhan QA.)
2. **MTF metrics in summary** — locked to 50% and 90%; should we add 30% and 70% for clinical flexibility? (Recommend no — full table in CTP528 sheet; summary stays lean.)
3. **`thickness_slice_straddle` UI** — should `auto` be exposed as a string dropdown option, or as a checkbox "Auto" that disables the integer input? (Recommend string dropdown: `auto | 0 | 1 | 2 | 3`.)
4. **Test fixtures for CatPhan** — pylinac's `CatPhan504.from_demo_images()` provides a known-good synthetic dataset; use that as the test fixture? (Recommend yes — deterministic, no committed binary.)
5. **CatPhan session date source** — first DICOM's AcquisitionDate or runfolder mtime? (Recommend AcquisitionDate per WL pattern; fall back to mtime if missing.)
