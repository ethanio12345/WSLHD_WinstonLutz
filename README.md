# WSLHD Winston-Lutz QA

A Streamlit web GUI that wraps [pylinac](https://pylinac.readthedocs.io/)'s
`WinstonLutz` and `CatPhan504` modules for hospital physics QA. Provides a
one-click **Simple mode** for routine QA and an **Advanced mode** for service
investigations, producing MyQA-importable `.xlsx` output paired with a `.xltx`
template.

## Modules

- **Winston-Lutz** (`pages/1_Winston_Lutz.py`) — one-click WL analysis, 4-tab
  Advanced mode with detection overlays and Plotly charts
- **CatPhan 504** (`pages/2_CatPhan.py`) — one-click CBCT analysis, 5-tab
  Advanced mode with per-CTP-module drill-down (CTP404/486/528/515)
- **Field Profile** (`pages/3_Field_Profile.py`) — general-purpose
  flatness/symmetry tool (decoupled from per-machine config). Navigate to any
  RT image folder via a cascading browser, analyse one image, and download
  the MyQA-ready xlsx in-browser. 4-tab Advanced mode (Overview, Profiles,
  Field Map, ROI & Penumbra) with FFF auto-detection from DICOM metadata
- *Coming soon:* Trajectory Log

## Quickstart

### Docker (production)

```bash
# 1. Copy and edit the config
cp machines.yaml.example machines.yaml
# Edit machines.yaml: set DICOM roots, per-machine output_root, machine details

# 2. Start the stack
docker compose up -d
```

The app is reachable at `http://<host>:8080/wl/` (Caddy reverse proxy on port
8080 with path-based routing and IP allowlist for RFC1918 ranges).

> If behind a corporate proxy, ensure `no_proxy` and `NO_PROXY` env vars
> include the Caddy and app service hostnames to bypass the proxy for
> internal container networking.

### Local development

```bash
# Install dependencies
uv sync

# Run the template generators (one-time)
uv run python scripts/build_xltx_template.py
uv run python scripts/build_catphan_xltx_template.py  # only if using CatPhan

# Create a machines.yaml for local testing
cp machines.yaml.example machines.yaml
# Edit paths to point to local DICOM directories

# Run the app
uv run streamlit run app.py
```

## How to populate `machines.yaml`

See [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) for the full schema. Key
sections:

- **`machines`**: one entry per linac, each with `display_name`,
  `dicom_roots` (paths to DICOM directories — `winston_lutz` and/or `catphan`),
  and `output_root` (per-machine output directory for WL/CatPhan; Field
  Profile serves downloads in-browser)
- **`field_profile`** (optional, top-level): configures the Field Profile
  page's cascading folder browser root (`browse_root`, default `/data`). The
  FP page is a general-purpose standalone tool — no per-machine config needed.
- **`analysis_defaults.winston_lutz`**: centre-wide WL pylinac parameters
  (`bb_size_mm`, `machine_scale`, `tolerance_mm`, and optional params)
- **`analysis_defaults.catphan`**: centre-wide CatPhan pylinac parameters
  (`hu_tolerance`, `scaling_tolerance`, `slice_thickness_tolerance`, and optional
  params) — required if any machine has `catphan` configured
- **`analysis_defaults.field_profile`** (optional): centre-wide Field Profile
  pylinac parameters (`protocol`, and optional params). If absent, the page
  uses `protocol: VARIAN` + pylinac defaults
- **`assets`**: paths to the Fry meme and logo

## Updating the Fry meme

The Fry meme lives at the path specified by `assets.fry_meme_path` in
`machines.yaml`. In Docker, this is bind-mounted from the host:

1. Replace the image file at the bind-mounted host path
2. Restart the container: `docker compose restart winston_lutz`

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
    2_CatPhan.py              ← CatPhan 504 page (Simple + Advanced modes)
    3_Field_Profile.py        ← FP page (Simple + Advanced; general-purpose, decoupled)
  core/
    config.py                 ← machines.yaml loader + validator (pydantic)
    wl_runner.py              ← pylinac WinstonLutz wrapper
    cbct_runner.py            ← pylinac CatPhan504 wrapper
    fp_runner.py              ← pylinac FieldAnalysis wrapper
    excel_writer.py           ← WL xltx copy + named-cell writer
    cbct_excel_writer.py      ← CatPhan xltx copy + per-CTP-module sheets
    fp_excel_writer.py        ← Field Profile in-memory xlsx bytes (browser download)
    result_types.py           ← WL/CatPhan/FieldAnalysis result dataclasses
    runfolder.py              ← shared runfolder discovery utilities
    session_io.py             ← shared session output folder builder
    excel_helpers.py          ← shared set_named_cell + sanitise_sheet_name
    caching.py                ← shared st.session_state lifecycle helpers
    ui_utils.py               ← shared UI helpers (render_asset, mode toggle)
  templates/
    winston_lutz.xltx         ← WL Excel template (25 named cells)
    catphan_504.xltx          ← CatPhan Excel template (19 named cells)
    field_profile.xltx        ← FP Excel template (30 named cells)
  assets/
    fry_money.png             ← default Fry meme
  scripts/
    build_xltx_template.py    ← WL template generator
    build_catphan_xltx_template.py ← CatPhan template generator
    build_fp_xltx_template.py ← FP template generator
  tests/
    ...                       ← unit + integration tests for all modules
```
