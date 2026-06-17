## Context

The app wraps pylinac modules for hospital physics QA. Winston-Lutz and
CatPhan 504 pages are implemented with a shared architecture: runner module
(wraps pylinac), excel writer (produces paired xltx/xlsx), page (Simple +
Advanced Streamlit modes). Shared utilities extracted during the CatPhan
refactor (`core/runfolder.py`, `core/session_io.py`, `core/excel_helpers.py`,
`core/caching.py`) are reusable as-is.

Key difference: Field Analysis operates on a **single DICOM image**, not a
runfolder of images. This adds an image-selection step to the UI flow.

## Goals / Non-Goals

**Goals:**
- One-click field profile analysis from the Streamlit UI
- VARIAN protocol flatness/symmetry + full geometry metrics in xlsx
- FFF auto-detection from DICOM metadata with manual override in Advanced mode
- Per-image analysis with a dropdown showing useful DICOM info (energy, RT label,
  dimensions, pixel spacing, filename)
- MyQA-importable xlsx with 30 named cells
- Same Simple/Advanced mode pattern as WL and CatPhan

**Non-Goals:**
- Pass/fail tolerances (just report values — user confirmed)
- Multi-protocol support in the UI (VARIAN only; SIEMENS/ELEKTA available in
  config but not exposed in Simple mode)
- Batch analysis of multiple images (one image at a time)
- FFF-specific flatness/symmetry algorithms beyond pylinac's `is_FFF` flag

## Decisions

### D1: Single-image input model (not runfolder)

Unlike WL (N DICOMs = 1 analysis) and CatPhan (N slices = 1 analysis),
FieldAnalysis takes ONE 2D image. The UI adds an image dropdown after the
runfolder dropdown. The dropdown shows a DICOM metadata summary:

```
6FFF  T2_OP  1024×768  0.392mm/px  (6MV_FFF_10x10.dcm)
6     T2_OP  1024×768  0.392mm/px  (6MV_10x10.dcm)
```

Built from `(3002,0060)` Radiation Energy, `(3002,0002)` RT Image Label,
Rows/Cols, Image Plane Pixel Spacing, and filename.

### D2: FFF auto-detection (2-strategy priority)

> **Revised during implementation (apply phase).** The original design specified
> a 3rd "shape heuristic" strategy (``central_roi_mean / edge_mean > 1.05``).
> This was **dropped** because no fixed-radius "periphery" sample reliably
> distinguishes FFF from flat without first knowing the field boundary —
> comparing the centre to the dose-free background outside the field flags
> every portal image as FFF (the demo flat beam returned a 39.7× ratio). The
> two tag-based strategies below cover all standard Varian RT images (which
> always carry tag ``3002,0060``). A flat-beam analysis run on an actual FFF
> image may fail or give incorrect symmetry; the user overrides via the
> Advanced-mode FFF checkbox and re-runs.

1. **DICOM Radiation Energy tag** `(3002,0060)` — Varian stores "6", "6FFF",
   "10", "10FFF". If "FFF" in energy → `is_FFF=True`
2. **String tag scan** — scan all string-valued DICOM tags for "FFF" substring
   (catches non-standard placements)

If neither matches, the image is treated as flat (`is_FFF=False`). Advanced
mode shows the detected value and allows override via sidebar checkbox.

### D3: 30 named cells (no pass/fail)

No `tolerance_mm` equivalent. All 29 metrics from pylinac's `results_data` are
written directly to named cells + `template_version`.

### D4: FieldAnalysisResult dataclass

Mirrors WL/CatPhan pattern:
```python
@dataclass(frozen=True)
class FieldAnalysisResult:
    machine_id: str
    image_path: str
    image_display_name: str
    session_date: str
    is_fff: bool
    summary: dict[str, float | int | str]  # 29 named-cell values
    vert_profile_values: list[float]       # for Plotly
    horiz_profile_values: list[float]      # for Plotly
    protocol_results: dict[str, float]     # flatness/symmetry sub-dict
    params_used: dict[str, Any]
```

### D5: Module dispatch entry

`core/session_io.py` MODULE_DISPATCH gains `"field_profile": ("FP", "FP")`.
Output path: `<machine.output_root>/FP/<MACHINE>_FP_<image_stem>/`.

### D6: Advanced mode tabs (4)

| Tab | Content |
|-----|---------|
| Overview | Summary table (29 metrics), protocol, FFF status, "Analysed with" |
| Profiles | Vertical + horizontal profile plots (Plotly from `vert_profile.values` / `horiz_profile.values`) |
| Field Map | 2D analyzed image from `fa.plot_analyzed_image()` |
| ROI & Penumbra | Central ROI stats + penumbra table (4 sides) |

### D7: Config schema

```yaml
analysis_defaults:
  field_profile:
    protocol: VARIAN
    centering: BEAM_CENTER
    in_field_ratio: 0.8
    penumbra: [20, 80]
    is_fff: false              # default; auto-detected per image
    interpolation: LINEAR
    edge_detection_method: INFLECTION_DERIVATIVE
```

Required iff any machine has `field_profile` in `dicom_roots`.

### D8: Template script

`scripts/build_fp_xltx_template.py` generates `templates/field_profile.xltx`
with Summary sheet (30 named cells) + 4 data sheets (Profiles, Penumbra,
CAX/Beam Center, ROI).

## Risks / Trade-offs

- **Profile data for Plotly**: `fa.vert_profile.values` and `fa.horiz_profile.values`
  are numpy arrays (3000+ points). Verified accessible after `analyze()`.
  Pre-slice to 500 points for Plotly rendering performance.
- **Non-RT DICOMs in folder**: If someone puts a CT image in the field profile
  folder, `FieldAnalysis` will fail at load. The error wrapper catches this and
  shows a physicist-friendly message in Simple mode.
- **FFF shape heuristic threshold**: The 1.05 ratio is empirical. It may need
  tuning for specific energies/detectors. The DICOM energy tag (strategy 1)
  is the primary detection; shape heuristic is a last resort.
- **pylinac API isolation**: `core/fp_runner.py` isolates all pylinac calls,
  matching the WL and CatPhan runner pattern. Future pylinac version changes
  require edits only here.
