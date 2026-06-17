# Template Updates

The app uses three xltx templates that define the named cells forming the
app↔MyQA contract. This document describes the update procedure for each.

## Winston-Lutz template (`templates/winston_lutz.xltx`)

### The 25 named cells

| Group | Cells |
|-------|-------|
| Session metadata (3) | `machine_name`, `session_date`, `num_total_images` |
| Clinical metrics (9) | `max_2d_cax_to_bb`, `median_2d_cax_to_bb`, `mean_2d_cax_to_bb`, `gantry_3d_iso`, `coll_2d_iso`, `couch_2d_iso`, `bb_shift_x`, `bb_shift_y`, `bb_shift_z` |
| Secondary metrics (12) | `max_2d_cax_to_epid`, `median_2d_cax_to_epid`, `mean_2d_cax_to_epid`, `gantry_coll_3d_iso`, `max_gantry_rms`, `max_coll_rms`, `max_couch_rms`, `max_epid_rms`, `num_gantry_images`, `num_coll_images`, `num_couch_images`, `num_gantry_coll_images` |
| Version stamp (1) | `template_version` |

### Update procedure

#### 1. Edit the template

Edit `templates/winston_lutz.xltx` in Excel or via the generator script:

```bash
# Regenerate from scratch (destructive — loses manual formatting)
uv run python scripts/build_xltx_template.py
```

Or edit in Excel: open the `.xltx`, add/move cells, but **keep all 25 defined
names intact** (use Formulas -> Name Manager).

#### 2. Run validation

```bash
uv run python -c "from core.config import validate_template; from pathlib import Path; validate_template(Path('templates/winston_lutz.xltx')); print('OK')"
```

If any of the 25 names are missing, this will report them and the app will
refuse to start.

#### 3. Test against MyQA staging

Upload the regenerated `.xlsx` from a test analysis run to MyQA staging (not
production). Verify all 25 fields import correctly.

#### 4. Bump `template_version`

Update the version stamp in the template (column B, row 2 of the summary
sheet, or via the generator script constant `TEMPLATE_VERSION`).

```python
# scripts/build_xltx_template.py
TEMPLATE_VERSION = "2026-07"  # bump the month
```

#### 5. Deploy

Copy the updated `.xltx` to the templates directory on the host:

```bash
cp templates/winston_lutz.xltx /mnt/hospital/RT_Templates/
docker compose restart winston_lutz
```

No image rebuild is required — the template is bind-mounted read-only.

## CatPhan template (`templates/catphan_504.xltx`)

### The 19 named cells

| Group | Cells |
|-------|-------|
| Session metadata (3) | `machine_name`, `session_date`, `num_images` |
| Pass/fail flags (4) | `hu_linearity_passed`, `geometry_passed`, `uniformity_passed`, `thickness_passed` |
| Geometry (2) | `measured_slice_thickness_mm`, `avg_line_distance_mm` |
| Uniformity (2) | `uniformity_index`, `integral_non_uniformity` |
| Contrast (2) | `low_contrast_visibility`, `num_rois_seen` |
| Resolution (2) | `mtf_50_lp_mm`, `mtf_90_lp_mm` |
| NPS (2) | `nps_avg_power`, `nps_max_freq` |
| Orientation (1) | `catphan_roll_deg` |
| Version stamp (1) | `template_version` |

### Update procedure

Same as WL — mirror the steps above:

```bash
# Regenerate from scratch
uv run python scripts/build_catphan_xltx_template.py

# Validate
uv run python -c "from core.config import validate_catphan_template; from pathlib import Path; validate_catphan_template(Path('templates/catphan_504.xltx')); print('OK')"
```

The CatPhan template version stamp uses a `-cp` suffix (`2026-06-cp`) to
distinguish it from WL's version (`2026-06`).

## Field Profile template (`templates/field_profile.xltx`)

### The 30 named cells

| Group | Cells |
|-------|-------|
| Session metadata (3) | `machine_name`, `session_date`, `image_name` |
| Protocol metrics (4) | `flatness_vertical`, `flatness_horizontal`, `symmetry_vertical`, `symmetry_horizontal` |
| Field geometry (2) | `field_size_vertical_mm`, `field_size_horizontal_mm` |
| Penumbra (4) | `top_penumbra_mm`, `bottom_penumbra_mm`, `left_penumbra_mm`, `right_penumbra_mm` |
| CAX offsets (4) | `cax_to_top_mm`, `cax_to_bottom_mm`, `cax_to_left_mm`, `cax_to_right_mm` |
| Beam center offsets (4) | `beam_center_to_top_mm`, `beam_center_to_bottom_mm`, `beam_center_to_left_mm`, `beam_center_to_right_mm` |
| Slopes (4) | `top_slope_percent_mm`, `bottom_slope_percent_mm`, `left_slope_percent_mm`, `right_slope_percent_mm` |
| Central ROI (4) | `central_roi_mean`, `central_roi_max`, `central_roi_min`, `central_roi_std` |
| Version stamp (1) | `template_version` |

The xlsx also contains 4 data sheets (Profiles, Penumbra, CAX Beam Center,
ROI) populated per analysis — for a total of 5 sheets.

### Update procedure

Same as WL — mirror the steps above:

```bash
# Regenerate from scratch
uv run python scripts/build_fp_xltx_template.py

# Validate
uv run python -c "from core.config import validate_fp_template; from pathlib import Path; validate_fp_template(Path('templates/field_profile.xltx')); print('OK')"
```

The Field Profile template version stamp uses a `-fp` suffix (`2026-06-fp`).

## Template drift detection

The `template_version` named cell is written to every `.xlsx`. If MyQA
encounters old `.xlsx` files with a different version, it can flag the
mismatch. This is a policy concern of MyQA, not the app.
