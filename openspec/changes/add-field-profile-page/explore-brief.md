# Explore Brief: Field Profile Analysis Page

## Alternatives Rejected

| Option | Why Rejected |
|--------|-------------|
| `pylinac.FieldProfileAnalysis` | 1D profile only; no 2D field image analysis; insufficient metrics for QA |
| `pylinac.planar_imaging` (Las Vegas, LeedsTOR) | Phantom-specific modules, not open-field flatness/symmetry analysis |
| Multiple images per analysis | User confirmed: single image per analysis, picked from dropdown |

## Chosen Approach

`pylinac.FieldAnalysis` with `Protocol.VARIAN`, one image at a time from a runfolder dropdown.

### Why
- 2D DICOM image input (matches how physicists acquire open-field images)
- VARIAN protocol matches the linac vendor (TrueBeam, EDGE)
- Full metric set: flatness, symmetry, field size, penumbra, CAX, slopes, ROI stats
- `from_demo_image()` available for tests (no synthetic generation needed)
- `results_data(as_dict=True)` for structured output

## Named Cells (30 total)

### Session Metadata (3)
| Cell | Source |
|------|--------|
| `machine_name` | machine_id from config |
| `session_date` | DICOM StudyDate or ContentDate |
| `image_name` | DICOM filename (stem only) |

### Protocol Metrics — VARIAN (4)
| Cell | pylinac path | Unit |
|------|-------------|------|
| `flatness_vertical` | `protocol_results.flatness_vertical` | % |
| `flatness_horizontal` | `protocol_results.flatness_horizontal` | % |
| `symmetry_vertical` | `protocol_results.symmetry_vertical` | % |
| `symmetry_horizontal` | `protocol_results.symmetry_horizontal` | % |

### Field Geometry (2)
| Cell | pylinac path | Unit |
|------|-------------|------|
| `field_size_vertical_mm` | top-level | mm |
| `field_size_horizontal_mm` | top-level | mm |

### Penumbra (4)
| Cell | pylinac path | Unit |
|------|-------------|------|
| `top_penumbra_mm` | top-level | mm |
| `bottom_penumbra_mm` | top-level | mm |
| `left_penumbra_mm` | top-level | mm |
| `right_penumbra_mm` | top-level | mm |

### CAX Offsets (4)
| Cell | pylinac path | Unit |
|------|-------------|------|
| `cax_to_top_mm` | top-level | mm |
| `cax_to_bottom_mm` | top-level | mm |
| `cax_to_left_mm` | top-level | mm |
| `cax_to_right_mm` | top-level | mm |

### Beam Center Offsets (4)
| Cell | pylinac path | Unit |
|------|-------------|------|
| `beam_center_to_top_mm` | top-level | mm |
| `beam_center_to_bottom_mm` | top-level | mm |
| `beam_center_to_left_mm` | top-level | mm |
| `beam_center_to_right_mm` | top-level | mm |

### Slopes (4)
| Cell | pylinac path | Unit |
|------|-------------|------|
| `top_slope_percent_mm` | top-level | %/mm |
| `bottom_slope_percent_mm` | top-level | %/mm |
| `left_slope_percent_mm` | top-level | %/mm |
| `right_slope_percent_mm` | top-level | %/mm |

### Central ROI (4)
| Cell | pylinac path | Unit |
|------|-------------|------|
| `central_roi_mean` | top-level | raw |
| `central_roi_max` | top-level | raw |
| `central_roi_min` | top-level | raw |
| `central_roi_std` | top-level | raw |

### Version (1)
| Cell | Source |
|------|--------|
| `template_version` | constant `"2026-06-fp"` |

**Total: 30 named cells** (29 metrics + 1 version stamp)

## FFF Auto-Detection (3-strategy priority)

1. **DICOM Radiation Energy tag** `(3002,0060)` — Varian stores "6", "6FFF", "10", "10FFF". If "FFF" in energy string → `is_FFF=True`
2. **String tag scan** — scan all string-valued DICOM tags for "FFF" substring (catches non-standard tag placements)
3. **Shape heuristic** — after loading, compute `central_roi_mean / edge_mean` ratio. If > 1.05 → FFF (flat fields ≈ 1.0, FFF typically > 1.05)
4. **Advanced mode override** — sidebar checkbox shows detected value, user can override

Priority: 1 → 2 → 3. First hit wins. Strategy 4 always available in Advanced mode.

## Image Dropdown Display

Each file in the runfolder shows a summary built from DICOM metadata:

```
6FFF  T2_OP  1024×768  0.392mm/px  (6MV_FFF_10x10.dcm)
6     T2_OP  1024×768  0.392mm/px  (6MV_10x10.dcm)
10FFF T2_OP  1024×768  0.392mm/px  (10MV_FFF_10x10.dcm)
```

Built from (first available):
- `(3002,0060)` Radiation Energy → energy string
- `(3002,0002)` RT Image Label → label
- `(0028,0010)` / `(0028,0011)` Rows/Cols → dimensions
- `(3002,0011)` Image Plane Pixel Spacing → mm/pixel
- Filename → always shown

If tags are missing, show what's available + filename. Always show filename as the last element.

## Config Schema

```yaml
machines:
  LA2:
    dicom_roots:
      winston_lutz: /data/LA2/WinstonLutz
      catphan: /data/LA2/CatPhan
      field_profile: /data/LA2/FieldProfile    # NEW
    output_root: /data/LA2/output

analysis_defaults:
  winston_lutz: { ... }   # existing
  catphan: { ... }        # existing
  field_profile:           # NEW — required iff any machine has field_profile
    protocol: VARIAN       # VARIAN | SIEMENS | ELEKTA
    centering: BEAM_CENTER # BEAM_CENTER | CAX | GEOMETRIC_CENTER | MANUAL
    in_field_ratio: 0.8
    penumbra: [20, 80]     # lower/upper percentile for penumbra calc
    is_fff: false           # default; auto-detected per image at runtime
    interpolation: LINEAR
    edge_detection_method: INFLECTION_DERIVATIVE
```

## Cross-Module Data Flows

```
User selects image from dropdown
        │
        ▼
┌───────────────────────────┐
│ pages/3_Field_Profile.py  │
│   _run_simple_analysis()  │
│     1. Read DICOM metadata│──→ FFF detection (3-strategy)
│     2. Call run_fp_analysis│──→ core/fp_runner.py
│     3. Write xlsx          │──→ core/fp_excel_writer.py
│     4. Cache result        │──→ core/caching.py (prefix="fp")
│     5. Show success card   │
└───────────────────────────┘

core/fp_runner.py:
  FieldAnalysis(image_path)
    .analyze(protocol=VARIAN, is_FFF=detected, ...)
    .results_data(as_dict=True)
        │
        ├──→ protocol_results: {flatness_v, flatness_h, symmetry_v, symmetry_h}
        ├──→ top-level fields: field_size, penumbra, cax, beam_center, slopes, ROI
        └──→ FieldAnalysisResult dataclass (frozen, picklable)

core/fp_excel_writer.py:
  build_session_folder(output_root, "FP", machine_id, image_stem)
    .xltx copy + .xlsx populate 30 named cells
    .xlsx 4 data sheets (Profiles, Penumbra, CAX/Beam, ROI)
```

## Advanced Mode Tabs (4)

| Tab | Content | Source |
|-----|---------|--------|
| Overview | Summary table (all 29 metrics), "Analysed with" params, protocol, FFF status | result.summary + result.params_used |
| Profiles | Vertical + horizontal profile plots with flatness/symmetry overlays | pylinac `plot_analyzed_image()` + Plotly from raw profile data |
| Field Map | 2D analyzed image (edges, beam center, CAX marked) | pylinac `plot_analyzed_image()` |
| ROI & Penumbra | Central ROI stats table + penumbra table (4 sides) | result.top-level fields |

## Differences from WL/CatPhan

| Aspect | WL/CatPhan | FieldAnalysis |
|--------|-----------|---------------|
| Input | Runfolder (N DICOMs = 1 analysis) | Single image (1 DICOM = 1 analysis) |
| UI step | Machine → Runfolder → Analyze | Machine → Runfolder → **Image** → Analyze |
| FFF | N/A | Auto-detected per image |
| Protocol | Fixed per module | VARIAN/SIEMENS/ELEKTA selectable |
| Pass/fail | WL: tolerance_mm, CP: 4 flags | None (just report values) |
| Named cells | WL: 25, CP: 19 | 30 |
| Result type | Frozen dataclass + Plotly arrays | Frozen dataclass (Plotly built from raw profile arrays) |

## Open Questions

1. **Profile data access** — pylinac's `plot_analyzed_image()` renders the full image but doesn't expose individual profile data as arrays for Plotly. May need to access `fa.vertical_profile` / `fa.horizontal_profile` internal objects. Need to verify these are accessible after `analyze()`.
2. **Edge case: non-RT images** — If someone puts a CT or planar image in the field profile folder, `FieldAnalysis` will fail. Error handling should catch this gracefully.
3. **Multiple images with same energy** — If two 6MV images are in the folder, the dropdown needs to distinguish them (by filename + timestamp).
