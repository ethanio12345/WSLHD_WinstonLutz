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
| `dicom_roots.winston_lutz` | str (path) | yes | Container path to the WL DICOM directory |
| `dicom_roots.<other>` | str (path) | no | Future modules (CatPhan, FieldProfile) — ignored by v1 |

### One machine

```yaml
machines:
  LA2:
    display_name: "LA2 (TrueBeam)"
    dicom_roots:
      winston_lutz: /data/LA2/WinstonLutz
```

### Multiple machines

```yaml
machines:
  LA2:
    display_name: "LA2 (TrueBeam)"
    dicom_roots:
      winston_lutz: /data/LA2/WinstonLutz
  LA3:
    display_name: "LA3 (TrueBeam)"
    dicom_roots:
      winston_lutz: /data/LA3/WinstonLutz
  LA4:
    display_name: "LA4 (Edge)"
    dicom_roots:
      winston_lutz: /data/LA4/WinstonLutz
```

The dropdown lists machines sorted alphabetically by key.

## `output`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `root` | str (path) | yes | Container path for xlsx/xltx output (must exist and be writable) |

```yaml
output:
  root: /out
```

The app creates `/out/<MACHINE>/WL/<MACHINE>_WL_<RUNFOLDER>/` per session.

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
2. **DICOM roots**: each machine's `dicom_roots.winston_lutz` path exists
3. **Output root**: `output.root` exists and is writable (probe-write)
4. **Template**: `templates/winston_lutz.xltx` defines all 25 required named cells

If any check fails, the app refuses to start with a clear error message.
