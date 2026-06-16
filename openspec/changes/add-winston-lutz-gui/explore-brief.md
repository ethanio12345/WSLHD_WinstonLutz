# Explore Brief — add-winston-lutz-gui

## What we're building

A Streamlit-based web GUI wrapping pylinac's Winston-Lutz module for a hospital radiation-oncology department. Two modes:

- **Simple mode**: one-button ("Shut Up and Give Me My MyQA Results") — pick a machine, app auto-selects newest runfolder by mtime, runs WL with centre defaults, writes xlsx paired with xltx template.
- **Advanced mode**: interactive — re-run with parameters, per-image drill-down, plotly plots, detection overlay review. For service / physicist debugging.

Deployed via Docker Compose + Caddy reverse proxy. Read-only mount for DICOM share, read-write mount for output share.

## Alternatives rejected

| Alternative | Why rejected |
|---|---|
| Plotly Dash / FastAPI+React | Streamlit chosen for simplicity; advanced mode uses plotly-within-streamlit, good enough for the "did detection work?" use case |
| One xltx per output directory (shared validator) | Rejected — paired xltx-per-xlsx is more robust to deletion |
| Flat output naming (`LA2_WL_*.xlsx`) | Rejected — hierarchical `/out/<machine>/<module>/<session>/` scales better as modules are added |
| Auto-abstract a "page protocol" now | Rejected — rule of three: build WL concretely first, abstract after CatPhan is added |
| HTTPS with self-signed / Caddy-internal CA | Deferred — start HTTP+IP allowlist; structured Caddyfile allows escalation without rewrite |
| CBCT-WL analysis (`from_cbct`) | Out of scope v1 — pylinac marks it experimental |
| Multi-machine batch run | YAGNI — single-machine at a time |

## Chosen architecture (decisions locked)

- **Repo layout**: flat (Streamlit convention) — `app.py`, `pages/`, `core/`, `templates/`, `assets/`, `machines.yaml`. Package name inside generalizes for future modules.
- **Config**: `machines.yaml` with explicit per-machine-per-module DICOM roots. Bind-mounted (no rebuild for config changes).
- **Templates**: `templates/winston_lutz.xltx` hand-crafted, bind-mounted, uses **named cells** as the app↔MyQA contract.
- **Output pairing**: each session writes a folder `/out/<MACHINE>/WL/<MACHINE>_WL_<RUNFOLDER>/` containing a copied `.xltx` + filled `.xlsx`.
- **xlsx structure**: Sheet 1 = summary with ~22 named cells (machine metadata + all WL aggregate metrics + bb_shift_x/y/z). Subsequent sheets = one per image from `keyed_image_details`, named by axis key (e.g. `G0B0P0`, `G90B0P0`).
- **Simple mode UX**: machine dropdown → preview of runfolder to be analyzed → single button → success card with metrics + "View in Advanced" hand-off.
- **Advanced mode UX**: 4 tabs (Overview / Per-image / Plots / Detection overlay) + sidebar with analyze() knobs (bb_size, machine_scale, low_density_bb, open_field, apply_virtual_shift, reference axes, snap_tolerance) + pass/fail tolerance (UI-only). Per-image tab supports axis filter (e.g. "show all gantry=0").
- **Caching**: `@st.cache_data` keyed on `(machine, runfolder, bb_size, machine_scale, low_density_bb, open_field, apply_virtual_shift, snap_tolerance, references)` — analysis reuses across simple→advanced hand-off via `st.session_state`.
- **Deployment**: docker-compose with two services (streamlit + caddy). Volumes: DICOM share `:ro`, output share `:rw`, machines.yaml `:ro`, templates `:ro`, assets `:ro`. No auth in v1 (IP allowlist at Caddy).
- **Error handling**: simple-mode shows physicist-friendly messages with clear next steps; advanced-mode shows full errors + retry path. Never show pylinac stack traces in simple mode.
- **Future modules**: CatPhan (Shape 1: multi-DICOM directory), Field Profile Analysis (Shape 2: single DICOM), Trajectory Log (Shape 3: non-DICOM). Page abstraction deferred.

## Named cells contract (full list)

**Session metadata**: `machine_name`, `session_date`, `num_total_images`
**Clinical metrics**: `max_2d_cax_to_bb`, `median_2d_cax_to_bb`, `mean_2d_cax_to_bb`, `gantry_3d_iso`, `coll_2d_iso`, `couch_2d_iso`, `bb_shift_x`, `bb_shift_y`, `bb_shift_z`
**Secondary metrics**: `max_2d_cax_to_epid`, `median_2d_cax_to_epid`, `mean_2d_cax_to_epid`, `gantry_coll_3d_iso`, `max_gantry_rms`, `max_coll_rms`, `max_couch_rms`, `max_epid_rms`, `num_gantry_images`, `num_coll_images`, `num_couch_images`, `num_gantry_coll_images`

## Open questions (non-blocking, can be captured in design)

1. Should pass/fail tolerance be a single `tolerance_mm` applied to `max_2d_cax_to_bb`, or per-metric tolerances?
2. Per-image sheet naming: use pylinac's `keyed_image_details` key (e.g. `G0B45P0`) verbatim, or sanitized variant for Excel's 31-char sheet-name limit?
3. Session date source: parse from runfolder name (if convention exists) or use DICOM AcquisitionDate?
4. Should "view in advanced mode" hand-off preserve the simple-mode analysis result, or re-run with defaults in advanced mode? (Recommended: preserve via session_state.)
5. Test fixtures: use pylinac's `generate_winstonlutz` for synthetic DICOMs, or commit a real-world anonymised sample?
