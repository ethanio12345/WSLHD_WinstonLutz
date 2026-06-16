# WSLHD Winston-Lutz QA

A Streamlit web GUI that wraps [pylinac](https://pylinac.readthedocs.io/)'s
`WinstonLutz` module for hospital physics QA. Provides a one-click **Simple
mode** for routine Winston-Lutz QA and an **Advanced mode** for service
investigations, producing MyQA-importable `.xlsx` output paired with a `.xltx`
template.

## Quickstart

### Docker (production)

```bash
# 1. Copy and edit the config
cp machines.yaml.example machines.yaml
# Edit machines.yaml: set DICOM roots, output path, machine details

# 2. Ensure host directories are readable by UID 1000
sudo chown -R 1000:1000 /mnt/hospital/RT_DICOM /mnt/hospital/RT_Results /mnt/hospital/RT_Assets

# 3. Start the stack
docker compose up -d
```

The app is reachable at `http://<host>:80/` (Caddy reverse proxy with IP
allowlist for RFC1918 ranges).

### Local development

```bash
# Install dependencies
uv sync

# Run the template generator (one-time)
uv run python scripts/build_xltx_template.py

# Create a machines.yaml for local testing
cp machines.yaml.example machines.yaml
# Edit paths to point to local DICOM directories

# Run the app
uv run streamlit run app.py
```

## How to populate `machines.yaml`

See [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) for the full schema. Key
sections:

- **`machines`**: one entry per linac, each with `display_name` and
  `dicom_roots.winston_lutz` (the path to the WL DICOM directory)
- **`output.root`**: where the paired `.xlsx`/`.xltx` files are written
- **`analysis_defaults.winston_lutz`**: centre-wide pylinac parameters
  (`bb_size_mm`, `machine_scale`, `tolerance_mm`, and optional params)
- **`assets`**: paths to the Fry meme and logo

## Host file ownership

The Docker container runs as **UID 1000** (`appuser`). All bind-mounted host
directories and files must be readable by UID 1000:

```bash
# Config file
sudo chown 1000:1000 machines.yaml

# Network shares (read-only mounts still need read permission)
sudo chown -R 1000:1000 /mnt/hospital/RT_DICOM
```

If the container can't read `machines.yaml`, it will refuse to start with a
clear permission error.

## Updating the Fry meme

The Fry meme lives at the path specified by `assets.fry_meme_path` in
`machines.yaml`. In Docker, this is bind-mounted from the hospital assets
share:

1. Replace the image file on the network share
   (e.g. `/mnt/hospital/RT_Assets/fry_money.png`)
2. Restart the container: `docker compose restart streamlit`

No image rebuild is required — the bind-mount overrides the baked-in default.

A default Fry meme is committed at `assets/fry_money.png` so the app works
out-of-the-box without the bind-mount.

## Auth / HTTPS escalation

v1 ships with **HTTP + IP allowlist** at the Caddy reverse proxy. To escalate:

- **HTTPS with hospital certs**: uncomment the `real_cert` block in `Caddyfile`
- **HTTP Basic Auth**: uncomment the `basic_auth` block
- **OIDC via Authelia/Keycloak**: uncomment the `forward_auth` block

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the ops runbook.

## Verification

```bash
uv run ruff format          # format
uv run ruff check --fix     # lint
uv run mypy core/           # typecheck
uv run pytest tests/ -v     # test (unit + integration)
uv run pytest tests/ -m integration -v  # Docker integration tests
```

## Project structure

```
WSLHD_WinstonLutz/
  app.py                      ← Streamlit entry (home page)
  pages/
    1_Winston_Lutz.py         ← WL page (Simple + Advanced modes)
  core/
    config.py                 ← machines.yaml loader + validator (pydantic)
    wl_runner.py              ← pylinac WinstonLutz wrapper
    excel_writer.py           ← xltx copy + named-cell writer + per-image sheets
    result_types.py           ← WLAnalysisResult frozen dataclass
    ui_utils.py               ← shared UI helpers (render_asset, mode toggle)
  templates/
    winston_lutz.xltx         ← Excel template (25 named cells)
  assets/
    fry_money.png             ← default Fry meme
  scripts/
    build_xltx_template.py    ← one-time template generator
  tests/
    test_config.py            ← config loading + template validation
    test_wl_runner.py         ← pylinac wrapper (synthetic DICOMs)
    test_excel_writer.py      ← xlsx output contract
    test_caching.py           ← @st.cache_data behaviour
    test_error_handling.py    ← error scenarios
    test_docker.py            ← Docker integration (@pytest.mark.integration)
    integration/
      test_simple_mode_e2e.py ← full Simple-mode pipeline
      test_advanced_mode_e2e.py ← Advanced-mode re-run
```
