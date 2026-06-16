## Why

Physicists at the cancer centre run Winston-Lutz QA on multiple linacs but currently have no fast, low-friction path from DICOM acquisition to a MyQA-importable result file. Running pylinac directly requires CLI comfort, parameter knowledge, and manual result handling. A web GUI that wraps pylinac — with a one-click Simple mode for routine QA and an Advanced mode for service investigations — removes the friction and standardises the output format across machines.

## What Changes

- Add a new Streamlit web application that wraps pylinac's `WinstonLutz` module
- Provide a **Simple mode**: pick a machine → app selects newest runfolder by mtime → run analysis with centre defaults → write paired `.xlsx` + `.xltx` (named cells) to a per-session output folder → success card with quick metrics and a hand-off link to Advanced mode that **preserves the analysis result** (no re-run); failures show physicist-friendly messages with a clear next step and **never display pylinac stack traces** in Simple mode
- Provide an **Advanced mode**: re-run with full pylinac `analyze()` parameters, explore results across 4 tabs (overview / per-image with axis filter / plotly plots / detection overlay), plus a pass/fail tolerance display (UI-only — not passed to pylinac)
- Write xlsx files with: (1) summary sheet using ~24 named cells as the app↔MyQA contract, (2) one sheet per image keyed by axis (e.g. `G0B0P0`) sourced from pylinac's `keyed_image_details`
- Pair every xlsx with a copied `.xltx` template in the same session output folder (robust to deletion of a master template)
- Containerise via Docker Compose with: read-only DICOM share mount, read-write output share mount, bind-mounted `machines.yaml` + `templates/` + `assets/`
- Front the app with Caddy reverse proxy starting in HTTP + IP allowlist mode, with a Caddyfile structured so HTTPS / basic-auth / OIDC can be added later without rewrite
- Lay the groundwork (project layout, config schema, page conventions) for future pylinac module pages (CatPhan, Field Profile Analysis, Trajectory Log) — but **defer the page abstraction** until at least two modules exist

## Capabilities

### New Capabilities

- `wl-simple-mode`: One-click Winston-Lutz analysis flow — machine dropdown, automatic newest-runfolder detection by mtime, defaults-driven analysis, paired xlsx/xltx output, success card with quick metrics + hand-off to Advanced mode preserving the analysis result; failures produce physicist-friendly messages with clear next steps and never display raw pylinac stack traces
- `wl-advanced-mode`: Interactive Winston-Lutz exploration — sidebar of pylinac `analyze()` parameters plus a pass/fail tolerance display (UI-only, not passed to pylinac), re-run, four tabs (Overview / Per-image with axis filter / Plots via Plotly / Detection overlay), per-image drill-down, xlsx download
- `wl-result-export`: Excel output contract — paired `.xltx` + `.xlsx` per session, summary sheet with ~22 named cells, one sheet per image keyed by axis, session-folder naming convention
- `machine-config`: `machines.yaml` schema and loading — per-machine-per-module explicit DICOM roots, output paths, default analysis parameters, asset paths; validation and machine discovery
- `container-deployment`: Docker Compose deployment — two services (Streamlit + Caddy), volume mounts (DICOM `:ro`, output `:rw`, config/templates/assets `:ro`), IP allowlist at Caddy as initial auth mode

### Modified Capabilities

None — greenfield repository, no existing specs.

## Impact

- **New code**: Streamlit application, config loader, xlsx writer, WL runner wrapper, Dockerfile, docker-compose.yml, Caddyfile, tests
- **New dependencies**: `pylinac`, `streamlit`, `plotly`, `openpyxl`, `pyyaml`, `pydantic` (config validation)
- **External systems**: hospital DICOM network share (read), hospital output share (write), MyQA import (consumer of xlsx)
- **No existing code affected** — greenfield repo (`WSLHD_WinstonLutz/`)
- **Future modules** will reuse the project layout, config schema conventions, and deployment pattern — but no shared page abstraction is introduced in this change

## Non-goals

- **CBCT-based Winston-Lutz** (`pylinac.WinstonLutz.from_cbct`) — pylinac marks this experimental; deferred to a future change
- **Multi-machine batch runs** — Simple and Advanced modes operate on one machine at a time; YAGNI for v1
- **HTTPS, basic-auth, or OIDC** — v1 ships HTTP + IP allowlist at the reverse proxy; auth/transport-security escalation is a config change in a later change
- **Shared page abstraction across pylinac modules** — deferred until at least two module pages exist (rule of three); each future module (CatPhan, Field Profile Analysis, Trajectory Log) will be added concretely first
- **In-app trending / historical views** — trending is the responsibility of MyQA, which consumes the xlsx output; this app is per-session only
