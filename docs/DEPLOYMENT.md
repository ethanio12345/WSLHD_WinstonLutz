# Deployment Ops Runbook

## Volume mount paths

| Container path | Host path | Mode | Purpose |
|----------------|-----------|------|---------|
| `/data` | `/mnt/hospital/RT_DICOM` | `:ro` | DICOM share (read-only) |
| `/out` | `/mnt/hospital/RT_Results` | `:rw` | Output share (xlsx/xltx writes) |
| `/app/machines.yaml` | `./machines.yaml` | `:ro` | Config (editable without rebuild) |
| `/app/templates` | `./templates` | `:ro` | xltx template (editable without rebuild) |
| `/assets` | `/mnt/hospital/RT_Assets` | `:ro` | Fry meme, logo |

## IP allowlist (Caddy)

The Caddyfile restricts access to RFC1918 private ranges by default:

```
10.0.0.0/8 172.16.0.0/12 192.168.0.0/16
```

To adjust, edit the `@allowed remote_ip` line in `Caddyfile`:

```caddy
@allowed remote_ip 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 203.0.113.0/24
```

Then: `docker compose restart caddy`

## Log access

All logs go to stdout (Docker convention):

```bash
# All services
docker compose logs -f

# Streamlit only
docker compose logs -f streamlit

# Last 100 lines
docker compose logs --tail 100 streamlit
```

Analysis failures log the full traceback via `logging.exception` — visible in
`docker logs` but **never** shown in the Simple mode UI.

## Common failure modes

### 1. Permission denied on startup

**Symptom:** `Cannot read /app/machines.yaml — ensure host file is readable by UID 1000`

**Cause:** The container runs as UID 1000 (`appuser`). If `machines.yaml` on
the host is owned by root with mode 0600, the container can't read it.

**Fix:**
```bash
sudo chown 1000:1000 machines.yaml
sudo chmod 644 machines.yaml
```

### 2. Mount missing

**Symptom:** `Output root /out does not exist — check the docker-compose volume mount`

**Cause:** The output share isn't mounted, or the host path doesn't exist.

**Fix:** Verify the volume mount in `docker-compose.yml` and that the host
directory exists:
```bash
ls -la /mnt/hospital/RT_Results
```

### 3. MyQA import failure

**Symptom:** MyQA rejects the `.xlsx` or reports missing fields.

**Cause:** Template drift — the `.xltx` was edited and a named cell was
removed or renamed.

**Fix:**
1. Run template validation: `uv run python -c "from core.config import validate_template; validate_template(Path('templates/winston_lutz.xltx'))"`
2. If names are missing, restore them via the generator: `uv run python scripts/build_xltx_template.py`
3. Test against MyQA staging before deploying to production
4. See [`TEMPLATE_UPDATES.md`](TEMPLATE_UPDATES.md) for the full procedure

### 4. DICOM root not found

**Symptom:** `Machine LA2: DICOM root /data/LA2/WinstonLutz does not exist`

**Cause:** The DICOM share isn't mounted, or the machine's subdirectory
doesn't exist yet.

**Fix:** Verify the mount and directory structure:
```bash
docker compose exec streamlit ls /data/LA2/WinstonLutz
```

### 5. CatPhan template missing

**Symptom:** `CatPhan template not found: templates/catphan_504.xltx`

**Cause:** A machine has `catphan` configured but the CatPhan xltx template
hasn't been generated yet.

**Fix:** Generate the template:
```bash
uv run python scripts/build_catphan_xltx_template.py
```

### 6. CatPhan module configured without defaults

**Symptom:** `catphan module configured for machine(s) but analysis_defaults.catphan is missing`

**Cause:** A machine has `catphan` under `dicom_roots` but the
`analysis_defaults.catphan` section is absent from `machines.yaml`.

**Fix:** Add the `catphan` defaults section to `machines.yaml`:
```yaml
analysis_defaults:
  catphan:
    hu_tolerance: 40
    scaling_tolerance: 0.5
    slice_thickness_tolerance: 0.5
```

### 7. Field Profile template missing

**Symptom:** `Field Profile template not found: templates/field_profile.xltx`

**Cause:** A machine has `field_profile` configured but the Field Profile xltx
template hasn't been generated yet.

**Fix:** Generate the template:
```bash
uv run python scripts/build_fp_xltx_template.py
```

### 8. Field Profile module configured without defaults

**Symptom:** `field_profile module configured for machine(s) but analysis_defaults.field_profile is missing`

**Cause:** A machine has `field_profile` under `dicom_roots` but the
`analysis_defaults.field_profile` section is absent from `machines.yaml`.

**Fix:** Add the `field_profile` defaults section to `machines.yaml`:
```yaml
analysis_defaults:
  field_profile:
    protocol: VARIAN
```

### 9. Field analysis fails (field edges not detected)

**Symptom:** Simple mode shows `Analysis failed: could not detect the field
edges...`

**Cause:** The selected image is not a valid RT portal image (e.g. a CT slice
mistakenly placed in the FieldProfile directory), or the image quality is too
poor for edge detection.

**Fix:** Switch to Advanced mode for the full traceback, verify the selected
image is a genuine RT portal image, or adjust the edge detection method /
in-field ratio in the Advanced sidebar and re-run. If the image is an FFF beam
mislabeled as flat (no Radiation Energy tag), tick "Force FFF analysis" in the
sidebar — note a flat-beam analysis on an FFF image may also fail; in that case
the FFF override resolves it.

## Enabling the CatPhan page

The CatPhan page (`pages/2_CatPhan.py`) is auto-discovered by Streamlit and
always appears in the sidebar. However, the machine dropdown will be empty
unless at least one machine has `catphan` configured.

To enable CatPhan for a machine:

1. Add `catphan:` under that machine's `dicom_roots` in `machines.yaml`
2. Add the `analysis_defaults.catphan` section
3. Ensure `templates/catphan_504.xltx` exists (run the generator if not)
4. Restart the container: `docker compose restart streamlit`

The CatPhan output path follows the same deep layout as WL:
`/out/<CATEGORY>/<DISPLAY>/Pylinac/CatPhan/<MACHINE>_CP_<RUNFOLDER>/`

## Enabling the Field Profile page

The Field Profile page (`pages/3_Field_Profile.py`) is auto-discovered by
Streamlit and always appears in the sidebar. However, the machine dropdown will
be empty unless at least one machine has `field_profile` configured.

To enable Field Profile for a machine:

1. Add `field_profile:` under that machine's `dicom_roots` in `machines.yaml`
   (pointing at the directory containing RT portal image runfolders)
2. Add the `analysis_defaults.field_profile` section (at minimum `protocol: VARIAN`)
3. Ensure `templates/field_profile.xltx` exists (run the generator if not)
4. Restart the container: `docker compose restart streamlit`

The Field Profile output path keys on the **image stem** (not the runfolder),
since Field Analysis operates on a single DICOM:
`<machine.output_root>/FP/<MACHINE>_FP_<IMAGE_STEM>/`

## Escalation paths

See [`README.md`](../README.md#auth--https-escalation) for enabling HTTPS,
basic auth, or OIDC at the Caddy reverse proxy.
