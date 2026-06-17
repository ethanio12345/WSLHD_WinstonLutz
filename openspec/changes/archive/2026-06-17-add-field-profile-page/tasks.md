## 1. Config + shared infrastructure

- [x] 1.1 Add `field_profile` to `core/session_io.py` MODULE_DISPATCH as `("FP", "FP")`
- [x] 1.2 Add `FieldProfileDefaults` pydantic model to `core/config.py` — required: `protocol` (enum VARIAN/SIEMENS/ELEKTA); optional: `centering`, `in_field_ratio`, `penumbra`, `is_fff`, `interpolation`, `edge_detection_method`, `vert_position`, `horiz_position`, `vert_width`, `horiz_width`, `slope_exclusion_ratio`, `edge_smoothing_ratio`, `hill_window_ratio`
- [x] 1.3 Update `AppConfig._validate_module_defaults` to validate `field_profile` section if any machine has `field_profile` configured
- [x] 1.4 Add `has_field_profile()` method and `fp_defaults` property to `AppConfig`
- [x] 1.5 Add `validate_fp_template()` function + `REQUIRED_FP_TEMPLATE_NAMES` constant (30 names) to `core/config.py`
- [x] 1.6 Update `app.py` to conditionally validate `templates/field_profile.xltx` when field_profile is configured
- [x] 1.7 Update `machines.yaml.example` — add commented-out `field_profile:` under dicom_roots + `analysis_defaults.field_profile` block
- [x] 1.8 Add tests to `tests/test_config.py` for field_profile config scenarios (valid, missing defaults, bad root, template validation)
- [x] 1.9 Run full existing test suite — all WL + CatPhan tests must pass with no modification

## 2. Result type + template

- [x] 2.1 Add `FieldAnalysisResult` frozen dataclass to `core/result_types.py` — `machine_id`, `image_path`, `image_display_name`, `session_date`, `is_fff`, `summary` (29-cell dict), `vert_profile_values`, `horiz_profile_values`, `protocol_results`, `params_used`
- [x] 2.2 Write `scripts/build_fp_xltx_template.py` — generate `templates/field_profile.xltx` with Summary sheet (30 named cells) + 4 data sheets (Profiles, Penumbra, CAX Beam Center, ROI)
- [x] 2.3 Run the script to produce `templates/field_profile.xltx`. Verify with `validate_fp_template` — all 30 named cells present

## 3. Runner

- [x] 3.1 Implement `run_fp_analysis(...)` in `core/fp_runner.py` — wraps `pylinac.FieldAnalysis(path).analyze(protocol=VARIAN, is_FFF=detected, ...)`, calls `results_data(as_dict=True)`, maps to 29-cell summary dict
- [x] 3.2 Implement FFF auto-detection: `_detect_fff(dicom_path)` — **2-strategy** (revised from 3 during apply): strategy 1 check `(3002,0060)` Radiation Energy for "FFF"; strategy 2 scan string tags. Shape heuristic (strategy 3) dropped as unreliable without field-boundary detection (see design D2 revised).
- [x] 3.3 Implement DICOM metadata extraction: `_extract_dicom_info(dicom_path)` — returns dict with energy, RT label, dimensions, pixel spacing, display string, is_fff flag
- [x] 3.4 Implement `load_fp_object(image_path, params)` for Advanced mode lazy init (returns live FieldAnalysis object for `plot_analyzed_image()`)
- [x] 3.5 Write `tests/test_fp_runner.py` — happy path (demo image), summary mapping completeness (29 cells), FFF detection (tag/string), picklability, profile data arrays populated

## 4. Excel writer

- [x] 4.1 Implement `write_fp_session_output(...)` in `core/fp_excel_writer.py` — calls `build_session_folder(output_root, machine_id, "FP", image_stem, "FP")` + `copy_template_to_session`, loads xltx, populates 29 metric named cells + `template_version`, writes 4 data sheets, saves as `.xlsx`
- [x] 4.2 Write `tests/test_fp_excel_writer.py` — 30 named cells populated, sheet count = 5, profiles sheet has V+H data, penumbra sheet has 4 rows, version stamped, paired xltx exists, output path layout

## 5. Page — Simple mode

- [x] 5.0 Create `pages/3_Field_Profile.py` with imports and mode toggle
- [x] 5.1 Machine dropdown — filter to machines with `field_profile` configured
- [x] 5.2 Runfolder dropdown — newest-first, auto-select newest
- [x] 5.3 Image dropdown — list DICOMs in runfolder with metadata display (energy + RT label + dimensions + spacing + filename)
- [x] 5.4 FFF detection display — show "FFF detected: Yes/No" after image selection
- [x] 5.5 One-click analysis button ("Shut Up and Give Me My MyQA Results") with error wrapping
- [x] 5.6 Success card — flatness V+H, symmetry V+H, field size V+H, output path, FFF status, hand-off button

## 6. Page — Advanced mode

- [x] 6.1 Advanced sidebar — all analyze params repopulated from `result.params_used` + FFF override checkbox
- [x] 6.2 Overview tab — summary table (29 metrics), protocol, FFF status, "Analysed with" caption
- [x] 6.3 Profiles tab — Plotly V+H profile line charts from `vert_profile_values` / `horiz_profile_values` (downsampled to ~500 points)
- [x] 6.4 Field Map tab — `fa.plot_analyzed_image()` rendered as matplotlib figure (lazy `load_fp_object`)
- [x] 6.5 ROI & Penumbra tab — central ROI stats table + penumbra table (4 sides) + slopes table
- [x] 6.6 Hand-off reception — read `fp_result` from session_state, don't re-run
- [x] 6.7 Re-run handler — invalidate `fp_obj`, call cached run with new params
- [x] 6.8 Download handler — write xlsx, show download button
- [x] 6.9 Full errors inline — show full traceback on analysis failure in Advanced mode
- [x] 6.10 Lazy `fp_obj` — `_get_fp_obj()` lazily creates and caches the FieldAnalysis object

## 7. E2E browser tests

- [x] 7.1 Update `tests/e2e/conftest.py` — add field_profile demo DICOMs to test config + output_root
- [x] 7.2 Activate `tests/e2e/test_field_profile.py` — remove `pytest.skip`, write Simple mode full pipeline (image dropdown → button → success card → hand-off)
- [x] 7.3 Add Advanced mode tests — Re-run with changed param, Download, all 4 tabs clicked and verified

## 8. Documentation

- [x] 8.1 Update `README.md` — add Field Profile to modules list, project structure
- [x] 8.2 Update `docs/CONFIGURATION.md` — add `field_profile` dicom_root + `analysis_defaults.field_profile` schema
- [x] 8.3 Update `docs/TEMPLATE_UPDATES.md` — add Field Profile template section (30 named cells)
- [x] 8.4 Update `docs/DEPLOYMENT.md` — add field_profile troubleshooting

## 9. Verification

- [x] 9.1 Run full Python verification pipeline (`ruff format && ruff check --fix && mypy core/ && pytest tests/`)
- [x] 9.2 Cross-reference spec scenarios with tests — every scenario has at least one corresponding test
- [x] 9.3 Manual smoke test in Docker (if available) — verify both WL and Field Profile pages work side by side
