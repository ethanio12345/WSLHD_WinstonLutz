## Why

The app currently supports Winston-Lutz and CatPhan 504 QA modules. Medical
physicists at WSLHD also perform routine field profile (flatness and symmetry)
QA on Varian TrueBeam/EDGE linacs. This requires manually running pylinac's
`FieldAnalysis` in a Python REPL and copying results into spreadsheets. A
dedicated page with one-click analysis and MyQA-exportable xlsx output would
eliminate manual steps and match the workflow already established for WL and
CatPhan.

## What Changes

- Add a third module page (`pages/3_Field_Profile.py`) wrapping
  `pylinac.FieldAnalysis` with VARIAN protocol
- Unlike WL/CatPhan (one runfolder = one analysis), Field Analysis operates on
  a **single image** selected from a dropdown within the runfolder
- Auto-detect FFF mode from DICOM metadata (Radiation Energy tag) and pass
  `is_FFF=True` to pylinac when detected
- Produce paired `.xltx` + `.xlsx` with 30 named cells (flatness, symmetry,
  field size, penumbra, CAX/beam center offsets, slopes, central ROI stats)
- Simple mode (one-click) + Advanced mode (4 tabs: Overview, Profiles, Field
  Map, ROI & Penumbra)
- No pass/fail tolerances — just analysis reporting
- Config: add `field_profile` to `dicom_roots` and `analysis_defaults.field_profile`

## Capabilities

### New Capabilities

- `fp-simple-mode`: Simple mode UI — machine dropdown, runfolder dropdown, image dropdown, one-click analysis, FFF auto-detection, success card with flatness/symmetry/field size, hand-off to Advanced
- `fp-advanced-mode`: Advanced mode UI — sidebar with analyze params (protocol, centering, in-field ratio, penumbra, is_FFF override), 4 tabs (Overview, Profiles, Field Map, ROI & Penumbra), re-run, download xlsx
- `fp-result-export`: Excel output — paired xltx/xlsx with 30 named cells, per-machine output folder (`<output_root>/FP/<MACHINE>_FP_<image_stem>/`), 4 data sheets

### Modified Capabilities

- `machine-config`: Add `field_profile` to known module keys; add `FieldProfileDefaults` pydantic model (protocol, centering, in_field_ratio, penumbra, is_fff, interpolation, edge_detection_method); require `analysis_defaults.field_profile` if any machine has `field_profile` configured

## Impact

- **New files**: `pages/3_Field_Profile.py`, `core/fp_runner.py`, `core/fp_excel_writer.py`, `scripts/build_fp_xltx_template.py`, `templates/field_profile.xltx`
- **Modified files**: `core/config.py` (add FieldProfileDefaults), `core/result_types.py` (add FieldAnalysisResult), `core/session_io.py` (add field_profile to MODULE_DISPATCH), `app.py` (conditional template validation), `machines.yaml.example`
- **Dependencies**: No new dependencies (pylinac.FieldAnalysis already available)
- **Tests**: New unit tests for runner, excel writer, config; new e2e browser tests; skipped Field Profile scaffold tests in `tests/e2e/test_field_profile.py` activated
