# Deployment Ops Runbook

## Volume mount paths

| Container path | Host path | Mode | Purpose |
|----------------|-----------|------|---------|
| `/mnt/va_transfer_ro` | `/mnt/va_transfer_ro` | `:ro` | DICOM share (read-only, top-level mount covers all machines) |
| `/mnt/va_transfer_physics_qa` | `/mnt/va_transfer_physics_qa` | `:rw` | Output share (top-level mount covers all machines' output_roots) |
| `/app/machines.yaml` | `./machines.yaml` | `:ro` | Config (editable without rebuild) |
| `/app/templates` | `./templates` | `:ro` | xltx template (editable without rebuild) |
| `/app/assets` | `./assets` | `:ro` | Fry meme, logo |

Each machine's `dicom_roots` and `output_root` in `machines.yaml` are subdirectories of
these top-level mounts (e.g. `/mnt/va_transfer_ro/05 LA2/DICOMRT/WinstonLutz`).

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

# App only
docker compose logs -f winston_lutz

# Last 100 lines
docker compose logs --tail 100 winston_lutz
```

Analysis failures log the full traceback via `logging.exception` — visible in
`docker logs` but **never** shown in the Simple mode UI.

## Common failure modes

### 1. Permission denied on startup

**Symptom:** `Cannot read /app/machines.yaml`

**Cause:** The container runs as root (UID 0). The CIFS share has
`uid=0,dir_mode=0755` so files inside `/mnt/va_transfer_*` are owned by root
and readable. However, `machines.yaml` on the host filesystem must still be
world-readable.

**Fix:**
```bash
sudo chmod 644 machines.yaml
```

### 2. Mount missing

**Symptom:** `Output root ... does not exist — check the docker-compose volume mount`

**Cause:** The output share isn't mounted, or the host path doesn't exist.

**Fix:** Verify the volume mount in `docker-compose.yml` and that the host
directory exists:
```bash
ls -la /mnt/va_transfer_physics_qa
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

**Symptom:** `Machine LA2: DICOM root /mnt/va_transfer_ro/05 LA2/DICOMRT/WinstonLutz does not exist`

**Cause:** The DICOM share isn't mounted, or the machine's subdirectory
doesn't exist yet.

**Fix:** Verify the mount and directory structure:
```bash
docker compose exec winston_lutz ls "/mnt/va_transfer_ro/05 LA2/DICOMRT/WinstonLutz"
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

## Enabling the CatPhan page

The CatPhan page (`pages/2_CatPhan.py`) is auto-discovered by Streamlit and
always appears in the sidebar. However, the machine dropdown will be empty
unless at least one machine has `catphan` configured.

To enable CatPhan for a machine:

1. Add `catphan:` under that machine's `dicom_roots` in `machines.yaml`
2. Add the `analysis_defaults.catphan` section
3. Ensure `templates/catphan_504.xltx` exists (run the generator if not)
4. Restart the container: `docker compose restart winston_lutz`

The CatPhan output path follows the same layout as WL:
`<machine.output_root>/CatPhan/<MACHINE>_CP_<RUNFOLDER>/`

## Escalation paths

See [`README.md`](../README.md#auth--https-escalation) for enabling HTTPS,
basic auth, or OIDC at the Caddy reverse proxy.
