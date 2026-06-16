## 1. Refactor — extract shared utilities from WL (no behavior change)

- [x] 1.1 Create `core/runfolder.py` — extract `find_newest_runfolder`, `count_dicoms`, `runfolder_mtime` from `core/wl_runner.py`. Verbatim move; no logic change.
- [x] 1.2 Create `core/session_io.py` — extract the existing `_session_folder` logic from `core/excel_writer.py:116` into `build_session_folder(output_root, machine_id, machine_display_name, module_dir, runfolder_name, file_prefix, category="Clinical QA", pylinac_subfolder="Pylinac")`. Add `copy_template_to_session(template_path, session_folder, output_stem)`. Add the `MODULE_DISPATCH = {"winston_lutz": ("WL", "WL"), "catphan": ("CatPhan", "CP")}` constant.
- [x] 1.3 Create `core/excel_helpers.py` — extract `set_named_cell` and `sanitise_sheet_name` from `core/excel_writer.py`. Verbatim move.
- [x] 1.4 Create `core/caching.py` — new thin wrappers around `st.session_state`: `init_session_state(key_prefix, defaults)`, `get_cached_obj(key_prefix)`, `invalidate(key_prefix)`. Use SHORT prefixes (`"wl"`, `"cp"`) — NOT semantic module names — so session_state keys are `wl_result`/`wl_obj`/`wl_params` (matching the EXISTING WL implementation, required for task 1.9 to pass) and `cp_result`/`cp_obj`/`cp_params` (matching design D4). (NEW abstraction per design D1 — simple but introduces a behavioral surface.)
- [x] 1.4b Write `tests/test_caching_helpers.py` — mock `st.session_state`, verify `init_session_state("cp", {...)` produces key `cp_result`, `invalidate("cp")` clears `cp_result`/`cp_obj`/`cp_params` but not `wl_result`, `get_cached_obj("wl")` returns the WL obj or None.
- [x] 1.5 Update `core/wl_runner.py` — replace inline `find_newest_runfolder`/`count_dicoms`/`runfolder_mtime` with imports from `core/runfolder.py`.
- [x] 1.6 Update `core/excel_writer.py` — replace `_session_folder` with call to `core.session_io.build_session_folder(..., module_dir="WL", file_prefix="WL", ...)`; replace `set_named_cell`/`sanitise_sheet_name` with imports from `core.excel_helpers`. Verify identical output path.
- [x] 1.7 Update `pages/1_Winston_Lutz.py` — replace inline `st.session_state["wl_result"] = ...` patterns with calls to `core.caching.init_session_state("wl", ...)`, `invalidate("wl")`, etc.
- [x] 1.8 Update `pages/1_Winston_Lutz.py` machine dropdown — filter to machines where `dicom_roots.winston_lutz` is configured (per MODIFIED wl-simple-mode spec).
- [x] 1.8b Add `tests/test_wl_dropdown_filter.py` — synthetic config with WL-only machine, CatPhan-only machine, both-modules machine, neither machine; assert WL dropdown contains only WL-configured machines (covers 4 MODIFIED wl-simple-mode scenarios).
- [x] 1.9 Run full WL test suite (`uv run ruff format && uv run ruff check --fix && rm -rf .mypy_cache && uv run mypy core/ && uv run pytest tests/ -v`) — ALL WL tests must pass with no modification. If any test fails, the refactor is wrong.

## 2. Multi-module config (machine-config MODIFIED spec)

- [x] 2.1 Update pydantic models in `core/config.py` — change `MachineConfig.dicom_roots` to a free-form `dict[str, Path]` (or pydantic model with `model_config = ConfigDict(extra="allow")`) so future module keys like `field_profile` are accepted without code changes. Apply known-module validation (`winston_lutz`, `catphan`) via a model validator; unknown keys pass through silently. Add `model_validator(mode="after")` requiring at least one module root per machine.
- [x] 2.2 Add `CatPhanDefaults` pydantic model — `hu_tolerance: float`, `scaling_tolerance: float`, `slice_thickness_tolerance: float` required; `thickness_slice_straddle: str | int = "auto"`, `expected_hu_values: dict[str, float] | None = None`, etc. optional.
- [x] 2.3 Update `AppConfig` — `analysis_defaults` now has both `winston_lutz: WLDefaults` (existing) and `catphan: CatPhanDefaults | None` (new, required iff any machine has `catphan` configured).
- [x] 2.4 Update config filesystem validation — verify each machine's `dicom_roots.catphan` (if present) exists on filesystem. Verify `templates/catphan_504.xltx` (if any machine has `catphan`) has all 19 named cells defined.
- [x] 2.5 Update `machines.yaml.example` — add a commented-out `catphan:` section under `dicom_roots` for `LA2`, plus the `analysis_defaults.catphan` block.
- [x] 2.6 Add tests to `tests/test_config.py` — valid with both modules; valid with WL only; valid with CatPhan only; machine with empty `dicom_roots` rejected; missing `analysis_defaults.catphan` when catphan configured; nonexistent catphan DICOM root; template missing 19 named cells; **forward-compat**: machine with `dicom_roots: { winston_lutz: ..., catphan: ..., field_profile: ... }` loads successfully (future key ignored).

## 3. CatPhan xltx template

- [x] 3.1 Write `scripts/build_catphan_xltx_template.py` — generates `templates/catphan_504.xltx` programmatically via openpyxl. Creates 5 sheets (Summary + CTP404 + CTP486 + CTP528 + CTP515). Defines 19 named cells on Summary. Sets `template_version` to `2026-06-cp`. Applies basic formatting (column widths, header bold).
- [x] 3.2 Run the script to produce `templates/catphan_504.xltx`. Verify with template validator (2.4) — all 19 named cells present.

## 4. CatPhan runner (`core/cbct_runner.py`)

- [x] 4.1 Add `CatPhanAnalysisResult` frozen dataclass to `core/result_types.py`
- [x] 4.2a-core Implement `run_cbct_analysis(...)` core in `core/cbct_runner.py`
- [x] 4.2a-mapping Implement the 19-cell summary mapping
- [x] 4.2b Implement Plotly-ready array precomputation
- [x] 4.3 Decorate `run_cbct_analysis` with `@st.cache_data(show_spinner="Running CatPhan 504 analysis...")`
- [x] 4.4 Write `tests/test_cbct_runner.py` — use `CatPhan504.from_demo_images()` to load synthetic data, write to tmp_path; test happy path, per-CTP-module dict population, 19-cell summary mapping completeness, Plotly arrays shape/values, picklability of `CatPhanAnalysisResult`.

## 5. CatPhan Excel writer (`core/cbct_excel_writer.py`)

- [x] 5.1-setup Implement `write_cbct_session_output(...)` setup — calls `session_io.build_session_folder(..., module_dir="CatPhan", file_prefix="CP", ...)` + `copy_template_to_session`, loads xltx via openpyxl.
- [x] 5.1-populate Implement the populate phase — populate 18 metric named cells + `template_version` via `excel_helpers.set_named_cell`, write 4 per-CTP-module sheets (CTP404 7-row HU linearity table + geometry + thickness; CTP486 5-row uniformity table + indices + NPS; CTP528 9-row MTF table; CTP515 variable-row low contrast table) as header-based tables via `excel_helpers.sanitise_sheet_name` for sheet names. Save as `.xlsx`.
- [x] 5.2 Write `tests/test_cbct_excel_writer.py` — verify all 19 named cells populated, sheet count = 5, per-module sheet contents (CTP404 has 7 materials, CTP486 has 5 regions, CTP528 has 9 MTF rows), no `tolerance_mm` field anywhere.

## 6. CatPhan Simple mode UI (`pages/2_CatPhan.py`)

- [x] 6.0 Verify shared UI helpers — `render_asset` and `render_mode_toggle` in `core/ui_utils.py` are already shared (untouched by refactor). Just import them; no new work needed.
- [x] 6.1 Implement sidebar machine dropdown — `st.selectbox` populated from `AppConfig.machines`, filtered to machines where `dicom_roots.catphan` is configured. Empty-state banner if no machines.
- [x] 6.2a Implement runfolder preview for the "has runfolders" case — calls `find_newest_runfolder` + `count_dicoms` (now from `core/runfolder.py`); displays "Will analyze: `<name>` (N DICOMs)" with run button enabled.
- [x] 6.2b Implement runfolder preview for the "no runfolders" and "empty runfolder" cases — "No runfolders found" disables the run button; "Runfolder is empty" keeps the run button enabled (user can retry after DICOM export completes). These are two distinct states per the cbct-simple-mode spec scenarios.
- [x] 6.3 Implement the "Shut Up and Give Me My MyQA Results" button — `st.button` calls `run_cbct_analysis` with `analysis_defaults.catphan` params.
- [x] 6.4 Implement success card — `st.success` showing output xlsx path, the four pass/fail flags, `low_contrast_visibility` as value, "View in Advanced mode" button.
- [x] 6.5 Implement error wrapper — `try/except Exception` around `run_cbct_analysis` and `write_cbct_session_output`; `logging.exception(...)` to stdout; render one-line user-safe message.
- [x] 6.6 Implement Simple→Advanced hand-off — on "View in Advanced mode" click, set `st.session_state["cp_result"] = result` via `caching.init_session_state`, `st.session_state["mode"] = "advanced"`, `st.rerun()`.

## 7. CatPhan Advanced mode UI (`pages/2_CatPhan.py` continued)

- [x] 7.1 Implement Advanced sidebar — `st.number_input`/`st.selectbox` for the 10 scalar analyze params (NO tolerance widget). Defaults from config OR from `session_state["cp_result"].params_used` on hand-off.
- [x] 7.2 Implement Overview tab — `st.dataframe` of `CatPhanAnalysisResult.summary` with pass/fail column on the four flags only; "Analysed with: ..." line; static `st.pyplot(cbct.plot_analyzed_image())` montage.
- [x] 7.3 Implement CTP404 tab — `st.pyplot(cbct.plot_analyzed_subimage('linearity'))` + HU ROIs table (7 materials × name/nominal/measured/difference/stdev/passed) + geometry summary + thickness info.
- [x] 7.4 Implement CTP486 tab — `st.pyplot(cbct.plot_analyzed_subimage('uniformity'))` + uniformity ROIs table (5 regions × name/value/nominal/difference/stdev/passed) + uniformity indices + NPS plot.
- [x] 7.5 Implement CTP528 tab — `st.pyplot(cbct.plot_analyzed_subimage('rmtf'))` + Plotly MTF curve (`st.plotly_chart`) + MTF table (9 rows × percentage/lp-per-mm).
- [x] 7.6 Implement CTP515 tab — `st.pyplot(cbct.plot_analyzed_subimage('low_contrast'))` + ROI table (per-ROI: size/contrast/CNR/SNR/visibility/threshold/passed).
- [x] 7.7 Implement lazy `cp_obj` init — on first Advanced render needing `cbct.plot_analyzed_subimage()`, populate `st.session_state["cp_obj"]` via `caching.get_cached_obj("catphan")` from `CatPhanAnalysisResult.runfolder_path` + params. **Should be implemented before 7.3–7.6** (per-CTP tabs depend on `cp_obj`).
- [x] 7.8 Implement hand-off reception — on Advanced entry, if `st.session_state["cp_result"]` is set, render Overview immediately without re-running; populate sidebar widgets from `params_used`.
- [x] 7.9 Implement "Re-run analysis" handler — invalidate `cp_obj` via `caching.invalidate("catphan")`, call cached `run_cbct_analysis` with new sidebar values, update `session_state["cp_result"]`; on cache short-circuit, show "Result loaded from cache (parameters unchanged)".
- [x] 7.10 Implement "Download xlsx" handler — call `write_cbct_session_output` with current `cp_result`, then `st.download_button`.
- [x] 7.11 Implement full-errors-inline behavior — when analysis fails in Advanced mode, render the full traceback inline (NOT the Simple mode one-line summary).

## 8. End-to-end tests

- [x] 8.1 Write `tests/integration/test_cbct_simple_mode_e2e.py` — use `CatPhan504.from_demo_images()` to populate a tmp_path runfolder, write a temporary `machines.yaml` with `catphan` configured, run `run_cbct_analysis` + `write_cbct_session_output`, verify the produced xlsx exists at the expected deep path, has 19 named cells populated, sheet count = 5.
- [x] 8.2 Write `tests/integration/test_cbct_advanced_mode_e2e.py` — simulate Simple→Advanced hand-off by directly populating `st.session_state["cp_result"]`; verify Advanced renders without re-running; verify re-run with new `hu_tolerance` produces different result; verify xlsx overwritten.
- [x] 8.3 Write `tests/test_cbct_error_handling.py` — feed corrupt DICOMs, missing template, read-only output dir; verify one-line user-safe message in Simple flow + full traceback in Advanced flow.

## 9. Documentation updates

- [x] 9.1 Update `README.md` — note the new CatPhan page, the optional `catphan:` config key, the new `templates/catphan_504.xltx` file.
- [x] 9.2 Update `docs/CONFIGURATION.md` — add `analysis_defaults.catphan` schema; show example machines.yaml with both modules.
- [x] 9.3 Update `docs/TEMPLATE_UPDATES.md` — add CatPhan template update procedure (mirror WL's).
- [x] 9.4 Update `docs/DEPLOYMENT.md` — note that operators must add `catphan:` under `dicom_roots` for machines that adopt CatPhan; document the canonical output path layout (deep path with `<CATEGORY>/<display>/<Pylinac>/<MODULE>/...`).

## 10. Verification

- [x] 10.1 Run full Python verification pipeline: `uv run ruff format`, `uv run ruff check --fix`, `rm -rf .mypy_cache && uv run mypy core/`, `uv run pytest tests/ -v` — all must pass. Pay particular attention to WL tests post-refactor.
- [x] 10.2 Verify all spec scenarios have at least one corresponding test (cross-reference `specs/*/spec.md` scenarios with `tests/**`). Pay particular attention to MODIFIED specs (machine-config + wl-simple-mode).
- [x] 10.3 Manual smoke test in Docker: container starts with both WL and CatPhan configured, WL page works as before, CatPhan page renders and produces xlsx, hand-off works on both pages, re-run works on CatPhan page.
