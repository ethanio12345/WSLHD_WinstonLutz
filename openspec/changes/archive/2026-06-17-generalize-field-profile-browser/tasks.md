# Tasks: generalize-field-profile-browser

## 1. Config decoupling

- [x] 1.1 In `core/config.py`: remove `field_profile` from `_KNOWN_MODULE_KEYS`; remove the `_validate_module_defaults` block that requires `analysis_defaults.field_profile` when a machine has `field_profile` dicom_root. `field_profile` becomes a forward-compat/ignored dicom_root key.
- [x] 1.2 In `core/config.py`: make `analysis_defaults.field_profile` optional — add a `fp_defaults_or_none` accessor (returns `FieldProfileDefaults` if the section exists, else `None`); keep `fp_defaults` for backwards-compat but have the page use the optional accessor. Add a top-level `field_profile: FieldProfilePageConfig` (with `browse_root: str = "/data"`) to `AppConfig`.
- [x] 1.3 In `core/config.py`: repurpose `has_field_profile()` to return `True` always (page always available). Add `fp_browse_root` property returning the configured/default root.
- [x] 1.4 In `app.py`: validate `templates/field_profile.xltx` unconditionally at startup (remove the `if config.has_field_profile()` condition for FP). Update the home-page module list to show FP as always available (no "not configured" caveat).
- [x] 1.5 Update `machines.yaml.example`: remove the `field_profile` dicom_root comment; add top-level `field_profile.browse_root` example; mark `analysis_defaults.field_profile` as optional.
- [x] 1.6 Update `tests/test_config.py`: remove the "fp_without_defaults_rejected" + "nonexistent_fp_dicom_root" tests (those checks are gone); add tests for optional defaults (absent → page works), legacy dicom_root ignored, browse_root default + override. Update the forward-compat test to re-include `field_profile` as an ignored key alongside `trajectory_log`.
- [x] 1.7 Run existing unit suite — all WL + CatPhan tests must pass (FP config tests updated).

## 2. Excel writer refactor (in-memory bytes)

- [x] 2.1 In `core/fp_excel_writer.py`: add `build_fp_xlsx_bytes(result, template_path) -> bytes` — loads the `.xltx`, populates 30 named cells + 4 data sheets (reuse the existing `_write_*_sheet` helpers), saves to `io.BytesIO`, returns bytes. No `output_root`, no session folder, no machine key.
- [x] 2.2 Keep or deprecate `write_fp_session_output`: mark it deprecated (not called by the page); keep for any external callers but the page won't use it. (Decision: remove it — nothing else calls it; the page is the only consumer.)
- [x] 2.3 Update `tests/test_fp_excel_writer.py`: replace path-based assertions with bytes-based — `build_fp_xlsx_bytes` returns bytes, load via `openpyxl.load_workbook(io.BytesIO(bytes))`, assert 30 named cells, 5 sheets, Profiles/Penumbra content, version stamp. Remove `output_root`/session-folder tests.

## 3. Cascading folder browser (page)

- [x] 3.1 In `pages/3_Field_Profile.py`: add a `render_folder_browser(browse_root) -> Path | None` helper that renders cascading selectboxes (subdirs only) sandboxed to `browse_root`, persists the path in `st.session_state["fp_browser_path"]`, and returns the selected folder. Changing a higher level truncates deeper levels.
- [x] 3.2 Replace the machine + runfolder dropdowns in `_render_simple` and `_advanced_initial_run` with the folder browser (rooted at `config.fp_browse_root`). Keep the image dropdown (populated from the selected folder).
- [x] 3.3 Handle empty/non-existent browse_root + empty selected folder with inline info messages (no crash).
- [x] 3.4 Sandbox check: the browser MUST NOT offer navigation above `browse_root` (no `..`, no absolute-path entry).

## 4. Page — in-browser result + download

- [x] 4.1 In `_render_simple`: remove the `write_fp_session_output` call + `fp_xlsx_path` session state. Replace the success card's "Output: <path>" line with a `st.download_button` ("Download xlsx") serving `build_fp_xlsx_bytes(result, template_path)` with `file_name="<IMAGE_STEM>.xlsx"`.
- [x] 4.2 In `_handle_download` (Advanced mode): replace `write_fp_session_output` with `build_fp_xlsx_bytes` + `st.download_button`. Remove the `output_root`/machine lookup.
- [x] 4.3 Remove now-unused imports (`build_session_folder`, `copy_template_to_session`, `MODULE_DISPATCH` if unused) from the page.

## 5. E2E tests

- [x] 5.1 Update `tests/e2e/conftest.py`: remove `field_profile` from the test machine's `dicom_roots` (it's decoupled); place the demo DICOM under a browse-root-relative path (e.g. `/data`-rooted tmp); add `field_profile.browse_root` to the test config pointing at it; keep `analysis_defaults.field_profile`.
- [x] 5.2 Update `tests/e2e/test_field_profile.py`: replace machine/runfolder navigation with cascading folder-browser navigation (selectbox clicks from browse_root to the image folder). Update download test to verify the browser download (no server file write / no `output_root` check).
- [x] 5.3 Add an e2e test verifying no files are written to `output_root` for FP.

## 6. Documentation

- [x] 6.1 `docs/CONFIGURATION.md`: document `field_profile` is decoupled (not a dicom_root key); add `field_profile.browse_root`; mark `analysis_defaults.field_profile` optional.
- [x] 6.2 `README.md` + project structure: note FP is a general-purpose browser tool (no per-machine config); update the FP bullet.
- [x] 6.3 `docs/DEPLOYMENT.md`: update FP troubleshooting (no server output; download via browser; browse_root config).

## 7. Verification

- [x] 7.1 Run full Python verification pipeline (`ruff format && ruff check --fix && mypy core/ && pytest tests/`).
- [x] 7.2 Cross-reference spec scenarios with tests — every scenario has ≥1 test.
- [x] 7.3 Run the FP e2e suite (`pytest -m e2e`) — cascading browser, in-browser result, download, no server writes.
