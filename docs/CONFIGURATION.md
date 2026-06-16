# Configuration: `machines.yaml`

The app loads `machines.yaml` at startup and validates it against a pydantic
schema. This document describes every field.

## Top-level structure

```yaml
machines:             # map of machine key → machine config (required)
output:               # output directory config (required)
analysis_defaults:    # centre-wide analysis defaults (required)
assets:               # asset paths (required)
```

## `machines`

A map of machine keys (e.g. `LA2`) to machine config objects. Each machine
requires:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `display_name` | str | yes | Human-readable name shown in the dropdown |
| `dicom_roots` | dict | yes | Module-keyed paths; at least one module required per machine |
| `dicom_roots.winston_lutz` | str (path) | optional | Container path to the WL DICOM directory |
| `dicom_roots.catphan` | str (path) | optional | Container path to the CatPhan DICOM directory |

`winston_lutz` and `catphan` are each independently optional per machine — a
machine may have either, both, or (when future modules ship) neither. At least
one module root must be configured per machine. Unknown keys (e.g.
`field_profile`) pass through silently for forward compatibility.

### One machine (WL + CatPhan)

```yaml
machines:
  LA2:
    display_name: "LA2 (TrueBeam)"
    dicom_roots:
      winston_lutz: /data/LA2/WinstonLutz
      catphan: /data/LA2/CatPhan
```

### Multiple machines with mixed modules

```yaml
machines:
  LA2:
    display_name: "LA2 (TrueBeam)"
    dicom_roots:
      winston_lutz: /data/LA2/WinstonLutz
      catphan: /data/LA2/CatPhan
  LA3:
    display_name: "LA3 (TrueBeam)"
    dicom_roots:
      winston_lutz: /data/LA3/WinstonLutz   # WL only
  LA4:
    display_name: "LA4 (Edge)"
    dicom_roots:
      catphan: /data/LA4/CatPhan             # CatPhan only
```

Each page's dropdown lists only machines with that module configured. The
dropdown lists machines sorted alphabetically by key.

## `output`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `root` | str (path) | yes | Container path for xlsx/xltx output (must exist and be writable) |

```yaml
output:
  root: /out
```

The app creates `/out/<CATEGORY>/<DISPLAY>/<PYLINAC_SUBFOLDER>/<MODULE>/<MACHINE>_<PREFIX>_<RUNFOLDER>/`
per session. e.g. `/out/Clinical QA/LA2 (TrueBeam)/Pylinac/WL/LA2_WL_2026-06-16_143022/`
or `/out/Clinical QA/LA2 (TrueBeam)/Pylinac/CatPhan/LA2_CP_2026-06-16_143022/`.

## `analysis_defaults.winston_lutz`

Centre-wide defaults applied to all machines.

### Required keys

| Key | Type | Description |
|-----|------|-------------|
| `bb_size_mm` | float | BB diameter in mm |
| `machine_scale` | str | One of: `VARIAN_IEC`, `VARIAN_STANDARD`, `IEC61217` |
| `tolerance_mm` | float | UI-only pass/fail threshold for `max_2d_cax_to_bb` (not passed to pylinac) |

### Optional keys (fall back to pylinac defaults)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `low_density_bb` | bool | `false` | Enable low-density BB detection |
| `open_field` | bool | `false` | Treat as open field |
| `apply_virtual_shift` | bool | `false` | Virtually shift the BB |
| `snap_tolerance` | float | pylinac default | Axis snap tolerance |
| `gantry_reference` | float | pylinac default | Gantry reference angle |
| `collimator_reference` | float | pylinac default | Collimator reference angle |
| `couch_reference` | float | pylinac default | Couch reference angle |

```yaml
analysis_defaults:
  winston_lutz:
    bb_size_mm: 5.0
    machine_scale: VARIAN_IEC
    tolerance_mm: 1.0
    apply_virtual_shift: false
```

## `analysis_defaults.catphan`

Centre-wide CatPhan 504 defaults. **Required if any machine has `catphan`
configured**; absent otherwise.

### Required keys

| Key | Type | Description |
|-----|------|-------------|
| `hu_tolerance` | float | HU tolerance for both HU uniformity and linearity |
| `scaling_tolerance` | float | Scaling tolerance in mm (geometric nodes on CTP404) |
| `slice_thickness_tolerance` | float | Thickness tolerance in mm (wire ramps in CTP404) |

### Optional keys (fall back to pylinac defaults)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `thickness_slice_straddle` | str or int | `auto` | Extra slices on each side for thickness (`auto`, `0`, `1`, `2`, `3`) |
| `expected_hu_values` | dict or null | null | Override HU linearity values (config-only; not in Advanced sidebar) |
| `x_adjustment` | float | `0.0` | Fine-tune phantom x-coordinate (mm) |
| `y_adjustment` | float | `0.0` | Fine-tune phantom y-coordinate (mm) |
| `angle_adjustment` | float | `0.0` | Fine-tune phantom angle (deg) |
| `roi_size_factor` | float | `1.0` | ROI size scaling factor |
| `scaling_factor` | float | `1.0` | Phantom magnification scaling factor |
| `minimum_rois_seen` | int | `3` | Number of low-contrast ROIs needed to pass |

No `tolerance_mm` UI-only field for CatPhan — pass/fail comes from pylinac's
four computed flags (`hu_linearity_passed`, `geometry_passed`,
`uniformity_passed`, `thickness_passed`).

```yaml
analysis_defaults:
  catphan:
    hu_tolerance: 40
    scaling_tolerance: 0.5
    slice_thickness_tolerance: 0.5
    minimum_rois_seen: 3
```

## `assets`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `fry_meme_path` | str (path) | yes | Path to the Fry meme image |
| `logo_path` | str (path) | yes | Path to the logo image |

```yaml
assets:
  fry_meme_path: /assets/fry_money.png
  logo_path: /assets/logo.png
```

If an asset file doesn't exist, the app displays a placeholder banner with
the expected path instead of crashing.

## Validation

At startup, the app validates:

1. **Schema**: all required keys present, types correct (pydantic)
2. **Module defaults**: each configured module's `analysis_defaults` section present
   (e.g. `catphan` configured requires `analysis_defaults.catphan`)
3. **DICOM roots**: each machine's configured `dicom_roots.*` paths exist
4. **Output root**: `output.root` exists and is writable (probe-write)
5. **Templates**: `templates/winston_lutz.xltx` defines all 25 required named cells;
   `templates/catphan_504.xltx` defines all 19 required named cells (if CatPhan is configured)

If any check fails, the app refuses to start with a clear error message.
