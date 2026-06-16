# Template Updates

The xltx template (`templates/winston_lutz.xltx`) defines the 25 named cells
that form the app↔MyQA contract. This document describes the update procedure.

## The 25 named cells

| Group | Cells |
|-------|-------|
| Session metadata (3) | `machine_name`, `session_date`, `num_total_images` |
| Clinical metrics (9) | `max_2d_cax_to_bb`, `median_2d_cax_to_bb`, `mean_2d_cax_to_bb`, `gantry_3d_iso`, `coll_2d_iso`, `couch_2d_iso`, `bb_shift_x`, `bb_shift_y`, `bb_shift_z` |
| Secondary metrics (12) | `max_2d_cax_to_epid`, `median_2d_cax_to_epid`, `mean_2d_cax_to_epid`, `gantry_coll_3d_iso`, `max_gantry_rms`, `max_coll_rms`, `max_couch_rms`, `max_epid_rms`, `num_gantry_images`, `num_coll_images`, `num_couch_images`, `num_gantry_coll_images` |
| Version stamp (1) | `template_version` |

## Update procedure

### 1. Edit the template

Edit `templates/winston_lutz.xltx` in Excel or via the generator script:

```bash
# Regenerate from scratch (destructive — loses manual formatting)
uv run python scripts/build_xltx_template.py
```

Or edit in Excel: open the `.xltx`, add/move cells, but **keep all 25 defined
names intact** (use Formulas → Name Manager).

### 2. Run validation

```bash
uv run python -c "from core.config import validate_template; from pathlib import Path; validate_template(Path('templates/winston_lutz.xltx')); print('OK')"
```

If any of the 25 names are missing, this will report them and the app will
refuse to start.

### 3. Test against MyQA staging

Upload the regenerated `.xlsx` from a test analysis run to MyQA staging (not
production). Verify all 25 fields import correctly.

### 4. Bump `template_version`

Update the version stamp in the template (column B, row 2 of the summary
sheet, or via the generator script constant `TEMPLATE_VERSION`).

```python
# scripts/build_xltx_template.py
TEMPLATE_VERSION = "2026-07"  # bump the month
```

### 5. Deploy

Copy the updated `.xltx` to the templates directory on the host:

```bash
cp templates/winston_lutz.xltx /mnt/hospital/RT_Templates/
docker compose restart streamlit
```

No image rebuild is required — the template is bind-mounted read-only.

## Template drift detection

The `template_version` named cell is written to every `.xlsx`. If MyQA
encounters old `.xlsx` files with a different version, it can flag the
mismatch. This is a policy concern of MyQA, not the app.
