# Configuration: `machines.yaml`

The app loads `machines.yaml` at startup and validates it against a pydantic
schema. This document describes every field.

## Top-level structure

```yaml
machines:             # map of machine key → machine config (required)
analysis_defaults:    # centre-wide analysis defaults (required)
field_profile:        # Field Profile page config (optional; page is always available)
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
| `output_root` | str (path) | yes | Per-machine output directory for WL/CatPhan session folders (must exist and be writable) |

`winston_lutz` and `catphan` are each independently optional per machine — a
machine may have either, both, or (when future modules ship) neither. At least
one module root must be configured per machine.

> **Note:** `field_profile` is **not** a per-machine `dicom_roots` key (the
> Field Profile page is decoupled from machines — see
> [`field_profile`](#field_profile-optional) below). A legacy
> `dicom_roots.field_profile` entry is silently ignored (forward-compat).

### One machine (WL + CatPhan)

```yaml
machines:
  LA2:
    display_name: "LA2 (TrueBeam)"
    dicom_roots:
      winston_lutz: /mnt/va_transfer_ro/05 LA2/DICOMRT/WinstonLutz
      catphan: /mnt/va_transfer_ro/05 LA2/DICOMRT/CatPhan
    output_root: /mnt/va_transfer_physics_qa/05 LA2/Pylinac
```

### Multiple machines with mixed modules

```yaml
machines:
  LA2:
    display_name: "LA2 (TrueBeam)"
    dicom_roots:
      winston_lutz: /mnt/va_transfer_ro/05 LA2/DICOMRT/WinstonLutz
      catphan: /mnt/va_transfer_ro/05 LA2/DICOMRT/CatPhan
    output_root: /mnt/va_transfer_physics_qa/05 LA2/Pylinac
  LA3:
    display_name: "LA3 (TrueBeam)"
    dicom_roots:
      winston_lutz: /mnt/va_transfer_ro/05 LA3/DICOMRT/WinstonLutz   # WL only
    output_root: /mnt/va_transfer_physics_qa/05 LA3/Pylinac
  LA4:
    display_name: "LA4 (Edge)"
    dicom_roots:
      catphan: /mnt/va_transfer_ro/05 LA4/DICOMRT/CatPhan             # CatPhan only
    output_root: /mnt/va_transfer_physics_qa/05 LA4/Pylinac
```

Each page's dropdown lists only machines with that module configured. The
dropdown lists machines sorted alphabetically by key.

## `output_root` (per machine)

Each machine has its own `output_root` — the directory where WL/CatPhan session
folders are written as subdirectories. This is a **per-machine** field, not a
global setting, so each machine can write to its own network share.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `machines.<key>.output_root` | str (path) | yes | Per-machine output directory (must exist and be writable) |

The app creates `<output_root>/<MODULE>/<MACHINE>_<PREFIX>_<RUNFOLDER>/` per session.
e.g. `/mnt/va_transfer_physics_qa/05 LA2/Pylinac/WL/LA2_WL_demo_clinical/`
     `/mnt/va_transfer_physics_qa/05 LA2/Pylinac/CatPhan/LA2_CP_2026-06-16_monthly/`

> **Note:** Field Profile does **not** write to `output_root`. The FP page is
> decoupled from per-machine output and serves results in-browser via a
> download button (see [`field_profile`](#field_profile-optional) below).

## `field_profile` (optional)

The Field Profile page is a **general-purpose standalone tool** decoupled from
per-machine config. It is always available; this optional top-level section
configures the cascading folder browser.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `field_profile.browse_root` | str (path) | no | `/data` | Root of the cascading folder browser |

The physicist navigates to any RT image folder by drilling down through
cascading selectboxes (no path typing). The browser is sandboxed to
`browse_root` — there is no affordance to navigate above it.

```yaml
field_profile:
  browse_root: /data    # default; point at your DICOM share
```

If `field_profile` is absent entirely, the page defaults to `browse_root: /data`.

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

## `analysis_defaults.field_profile` (optional)

Centre-wide Field Profile defaults. **Optional** — the Field Profile page is
always available, and if this section is absent the page uses `protocol: VARIAN`
+ pylinac defaults.

### Required keys (if the section is present)

| Key | Type | Description |
|-----|------|-------------|
| `protocol` | str | One of: `VARIAN`, `SIEMENS`, `ELEKTA` |

### Optional keys (fall back to pylinac defaults)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `centering` | str | `BEAM_CENTER` | Centering method name |
| `in_field_ratio` | float | `0.8` | In-field ratio for analysis |
| `penumbra` | list[float] | `[20, 80]` | `(lower, upper)` penumbra percentages |
| `is_fff` | bool | `false` | Default FFF mode (auto-detected per image) |
| `interpolation` | str | `LINEAR` | Interpolation method name |
| `edge_detection_method` | str | `INFLECTION_DERIVATIVE` | Edge detection method name |
| `vert_position` | float | `0.5` | Vertical profile position (0-1) |
| `horiz_position` | float | `0.5` | Horizontal profile position (0-1) |
| `vert_width` | float | `0.0` | Vertical profile width |
| `horiz_width` | float | `0.0` | Horizontal profile width |
| `slope_exclusion_ratio` | float | `0.2` | Slope exclusion ratio |
| `edge_smoothing_ratio` | float | `0.003` | Edge smoothing ratio |
| `hill_window_ratio` | float | `0.15` | Hill window ratio |

No pass/fail tolerances — Field Profile reports values only. FFF is
auto-detected per image from the DICOM Radiation Energy tag `(3002,0060)` and
string tag scan; the Advanced-mode sidebar exposes an FFF override checkbox.

```yaml
analysis_defaults:
  field_profile:
    protocol: VARIAN
    in_field_ratio: 0.8
    penumbra: [20, 80]
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
   (e.g. `catphan` configured requires `analysis_defaults.catphan`).
   Note: `field_profile` is decoupled — `analysis_defaults.field_profile` is
   optional centre-wide config (validated if present, but not required).
3. **DICOM roots**: each machine's configured `dicom_roots.*` paths exist
4. **Output roots**: each machine's `output_root` exists and is writable (probe-write)
5. **Templates**: `templates/winston_lutz.xltx` defines all 25 required named cells;
   `templates/catphan_504.xltx` defines all 19 required named cells (if CatPhan is configured);
   `templates/field_profile.xltx` defines all 30 required named cells (always —
   the FP page is always available and produces in-memory xlsx from this template)

If any check fails, the app refuses to start with a clear error message.
