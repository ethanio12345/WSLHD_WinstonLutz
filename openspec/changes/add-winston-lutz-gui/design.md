## Context

Greenfield repository (`WSLHD_WinstonLutz/`). No existing code, no existing specs, no deployment history. The change wraps `pylinac.WinstonLutz` (v3.45+ — axis-data handling changed) for use by hospital physicists via a web browser. Consumers of the output are: physicists (advanced-mode UI) and MyQA (xlsx import).

Constraints from exploration:
- Deployed on a hospital server via Docker Compose
- DICOM data lives on a hospital network share (read-only access from container)
- Output lives on the same network share, different folder (read-write access)
- No hospital TLS CA available — start with HTTP + IP allowlist
- MyQA accepts any xlsx format as long as it is consistent and the `.xltx` template sits alongside the `.xlsx` at upload time
- Physicist UX priority: Simple mode is one click from machine selection to result file on disk

## Goals / Non-Goals

**Goals:**
- One-click Simple-mode WL analysis producing a MyQA-importable xlsx paired with xltx
- Interactive Advanced-mode exploration with re-run, axis-filtered per-image view, plotly plots, and detection-overlay review
- Containerised deployment with bind-mounted config / templates / assets (no rebuild for routine updates)
- Reverse proxy structured to escalate from IP allowlist → basic auth → OIDC without rewrite
- Foundation (project layout, config schema, deployment pattern) reusable for future pylinac module pages without a shared abstraction in v1

**Non-Goals:**
- CBCT-WL (`from_cbct`) support
- Multi-machine batch runs
- HTTPS / basic-auth / OIDC (v1 — Caddyfile structured for later escalation)
- Shared page protocol abstraction (deferred per rule of three)
- In-app trending / historical views (MyQA's responsibility)

## Decisions

### D1: Streamlit multi-page app, flat layout (no `src/` package)

Streamlit's multi-page convention auto-discovers `pages/` next to the entry file. Packaging under `src/rt_qa_ui/` would force `streamlit run src/rt_qa_ui/app.py` and complicate the auto-discovery. For an internal hospital tool that will not be published to PyPI, the flat layout is friction-free.

```
WSLHD_WinstonLutz/
  app.py                      ← Streamlit entry (home page = mode + module selector)
  pages/
    1_Winston_Lutz.py         ← WL page (renders simple or advanced per sidebar toggle)
  core/
    config.py                 ← machines.yaml loader + validator (pydantic)
    wl_runner.py              ← thin wrapper around pylinac.WinstonLutz
    excel_writer.py           ← xltx copy + named-cell writer + per-image sheets
    result_types.py           ← typed result dataclass for session_state hand-off
  templates/
    winston_lutz.xltx         ← hand-crafted, bind-mounted
  assets/
    fry_money.png             ← placeholder; real image bind-mounted at /assets
  machines.yaml               ← bind-mounted
  pyproject.toml
  Dockerfile
  docker-compose.yml
  Caddyfile
  tests/
```

**Alternatives considered:**
- *Packaged `src/rt_qa_ui/`*: rejected — friction with Streamlit's `pages/` discovery, no PyPI publishing expected
- *Single-file app*: rejected — WL is complex enough to warrant separation; future modules will multiply complexity

### D2: `machines.yaml` schema (pydantic-validated)

```yaml
machines:
  LA2:
    display_name: "LA2 (TrueBeam)"
    dicom_roots:
      winston_lutz: /data/LA2/WinstonLutz
      # catphan: /data/LA2/CatPhan        (future)
      # field_profile: /data/LA2/FieldProfile   (future)

output:
  root: /out                              # container path, mounted rw

analysis_defaults:
  winston_lutz:
    bb_size_mm: 5.0
    machine_scale: VARIAN_IEC
    tolerance_mm: 1.0                     # UI-only pass/fail threshold

assets:
  fry_meme_path: /assets/fry_money.png
  logo_path: /assets/logo.png
```

Per-machine-per-module DICOM roots are explicit (no globbing, no guessing). The `dicom_roots` dict is keyed by module name (`winston_lutz`, `catphan`, etc.) so adding a future module is purely additive.

**Alternatives considered:**
- *Single `dicom_root` per machine with module subdirs*: rejected — requires the app to know the subdir convention; explicit paths surface misconfigurations at load time
- *Per-machine `analysis_defaults`*: rejected — defaults are centre-wide; per-machine overrides are YAGNI

### D3: Runfolder discovery — newest subdirectory by mtime

For a machine's WL `dicom_root`, list immediate subdirectories and pick the one with the newest mtime. No filename pattern matching in v1.

```python
def find_newest_runfolder(dicom_root: Path) -> Path | None:
    subdirs = [p for p in dicom_root.iterdir() if p.is_dir()]
    if not subdirs:
        return None
    return max(subdirs, key=lambda p: p.stat().st_mtime)
```

Empty runfolder detection: if the chosen subdirectory has zero `.dcm` files, surface a clear error ("runfolder appears empty — wait for DICOM export to complete?").

**Alternatives considered:**
- *Filename date pattern matching*: rejected — user confirmed mtime is sufficient; avoids imposing a naming convention on the treatment machine's export
- *Newest by ctime*: rejected — mtime is more meaningful (write completion) and more portable across SMB mounts

### D4: Paired xltx + xlsx per session, named cells as the contract

Output layout per session:

```
/out/<MACHINE>/WL/<MACHINE>_WL_<RUNFOLDER_NAME>/
  <MACHINE>_WL_<RUNFOLDER_NAME>.xltx    ← copied verbatim from templates/winston_lutz.xltx
  <MACHINE>_WL_<RUNFOLDER_NAME>.xlsx    ← filled from template, named cells set
```

The xltx is `shutil.copy`'d from `templates/winston_lutz.xltx` into the session folder before writing. The xlsx is produced by `openpyxl.load_workbook(template_path)` → set named cells → `save(output_path)`.

**Named cells contract** (24 cells, all defined in the xltx as Excel defined names):

| Group | Cells |
|---|---|
| Session metadata (3) | `machine_name`, `session_date`, `num_total_images` |
| Clinical metrics (9) | `max_2d_cax_to_bb`, `median_2d_cax_to_bb`, `mean_2d_cax_to_bb`, `gantry_3d_iso`, `coll_2d_iso`, `couch_2d_iso`, `bb_shift_x`, `bb_shift_y`, `bb_shift_z` |
| Secondary metrics (12) | `max_2d_cax_to_epid`, `median_2d_cax_to_epid`, `mean_2d_cax_to_epid`, `gantry_coll_3d_iso`, `max_gantry_rms`, `max_coll_rms`, `max_couch_rms`, `max_epid_rms`, `num_gantry_images`, `num_coll_images`, `num_couch_images`, `num_gantry_coll_images` |

**Writing pattern** — resolve defined name → target cell → set value:

```python
def set_named_cell(wb: Workbook, name: str, value):
    defined_name = wb.defined_names[name]
    cell_range = defined_name.destinations  # yields (worksheet, cell_range) tuples
    sheet_title, coord = next(cell_range)
    wb[sheet_title][coord] = value
```

**Per-image sheets** — one sheet per image, sourced from `wl.results_data().keyed_image_details`. Sheet title = the pylinac key (e.g. `G0B0P0`, `G90B45P0`). Within each per-image sheet, data is written as a **header-based table** (field name in column A, value in column B) — no per-image named cells, no namespace expansion. This keeps the MyQA contract at 24 named cells in the summary sheet; per-image sheets are for physicist browsing and any future positional reads. Sheet titles are sanitised for Excel's constraints (≤31 chars, no `\ / ? * [ ] :` chars); pylinac keys are typically safe (`G0B0P0`, `G180B270P315` are well within limits) but sanitisation runs defensively.

**Alternatives considered:**
- *Single shared xltx per directory*: rejected (user decision) — paired-per-session is robust to deletion of a master
- *One xlsx with all data in a single flat sheet*: rejected — summary + per-image separation matches MyQA's multi-sheet indifference and aids physicist browsing
- *Positional cell writes (`wb['Sheet']['B4'] = value`)*: rejected — fragile to template layout changes; named cells decouple app from template geometry

### D5: Streamlit page structure — mode toggle in sidebar

A single WL page (`pages/1_Winston_Lutz.py`) renders either Simple or Advanced based on a sidebar radio toggle. The toggle defaults to Simple.

```
Sidebar:
  Mode: ( Simple | Advanced )      ← st.radio, persisted in session_state
  Module: Winston-Lutz              ← static for v1; future: dropdown
  ---
  [mode-specific widgets]

Main area:
  [mode-specific content]
```

**Simple → Advanced hand-off** preserves the analysis result via `st.session_state["wl_result"]`. When the user clicks "View in Advanced mode", the toggle switches and Advanced reads the cached result instead of re-running.

**Alternatives considered:**
- *Two separate pages (`1_Simple_WL.py`, `2_Advanced_WL.py`)*: rejected — hand-off requires shared session_state anyway; one page with a toggle is simpler
- *Always-simple with "expand advanced" accordion*: rejected — advanced has too many controls to fit in an accordion; dedicated sidebar state is cleaner

### D6: Caching strategy — `@st.cache_data` for the serialisable result, `st.session_state` for the WL object

**Two-tier storage:**

```python
@st.cache_data(show_spinner="Running Winston-Lutz analysis...")
def run_wl_analysis(
    machine_id: str,                       # encoded into runfolder_path but explicit for clarity
    runfolder_path: str,
    bb_size_mm: float,
    machine_scale: str,
    low_density_bb: bool,
    open_field: bool,
    apply_virtual_shift: bool,
    snap_tolerance: float,
    gantry_reference: float,               # pylinac ≥3.45 takes 3 separate scalar refs
    collimator_reference: float,           #   (verified against pylinac docs)
    couch_reference: float,
    dicom_file_count: int,                 # stale-cache mitigation
    runfolder_mtime: float,                # stale-cache mitigation
) -> WLAnalysisResult:
    ...
```

Cache key includes `machine_id` explicitly (defends against two machines sharing a runfolder name) and `(dicom_file_count, runfolder_mtime)` to invalidate automatically when the treatment machine is still writing DICOMs to the same folder.

**`WLAnalysisResult` dataclass** (the cache return type + Simple→Advanced hand-off payload):

```python
@dataclass(frozen=True)
class WLAnalysisResult:
    # Identity
    machine_id: str
    runfolder_path: str
    session_date: str                      # ISO 8601, from DICOM AcquisitionDate
    # Summary (the 24 named-cell values, as a flat dict)
    summary: dict[str, float | int | str]
    # Per-image data (from pylinac's image_details)
    image_details: list[dict]
    image_keys: list[str]                  # e.g. ["G0B0P0", "G90B0P0", ...]
    # Plotly-ready arrays (precomputed, frozen)
    deviation_vs_gantry: dict              # {x: [...], y: [...], text: [...]}
    bb_xy_scatter: dict                    # {x: [...], y: [...], color: [...]}
    distance_histogram: dict               # {values: [...]}
    # Parameters used (for "you analyzed with..." display)
    params_used: dict
```

Frozen dataclass — hashable, picklable, safe for `st.cache_data`.

**WL object lifecycle (Advanced mode):**

The pylinac `WinstonLutz` object is **not** stored in `st.cache_data` (not reliably picklable). Instead:

| Key | Lifecycle | Purpose |
|---|---|---|
| `st.session_state["wl_result"]` | Set by Simple mode run; read by Advanced mode on entry | Simple→Advanced hand-off payload (the `WLAnalysisResult`) |
| `st.session_state["wl_obj"]` | Lazy-init on first Advanced-mode render; cleared on re-run | The live `pylinac.WinstonLutz` object for overlay plotting |
| `st.session_state["wl_params"]` | Set whenever Advanced sidebar changes | Parameters for the next re-run; compared against `wl_result.params_used` to decide if re-run is needed |

Flow:
1. Simple mode runs → `wl_result` set; `wl_obj` and `wl_params` not yet populated.
2. User clicks "View in Advanced mode" → toggle switches; Advanced mode reads `wl_result` for summary/plots without needing `wl_obj`.
3. User first visits the Detection overlay tab (or any tab needing `wl.images[i].plot()`) → `wl_obj` lazy-initialised from `wl_result.runfolder_path` + params. This is one 5-30s load — acceptable because it happens once per Advanced session, not per tab switch.
4. User adjusts a sidebar parameter and clicks "Re-run" → `wl_obj` and `wl_result` invalidated; new analysis runs; both are repopulated.

This resolves the latency tension: analysis runs at most once per parameter set, and the WL DICOM load happens at most once per Advanced session.

**Alternatives considered:**
- *Cache the pylinac WL object directly*: rejected — not reliably picklable
- *Re-instantiate from runfolder on every overlay render*: rejected — would cost 5-30s per tab switch; the `wl_obj` session_state pattern avoids this
- *No caching, accept 5-30s per interaction*: rejected — UX killer

### D7: Advanced mode — 4 tabs and per-image axis filter

```
Tab: Overview         → static table of all aggregate metrics + pass/fail vs tolerance_mm
Tab: Per-image        → plotly.express.data.extract → st.dataframe; axis filter
                        dropdown (gantry/coll/couch/any) + value field; selecting a row
                        via a per-row st.button opens the corresponding detection-overlay
                        image inline below the table
Tab: Plots            → plotly: (a) deviation vs gantry angle scatter,
                        (b) BB X-vs-Y scatter coloured by axis, (c) distance histogram
Tab: Detection overlay→ grid of st.pyplot(wl.images[i].plot()) for all images;
                        click → st.dialog (Streamlit ≥1.33) showing the same call
                        full-size with zoom
```

**Note**: `st.dataframe` does not have a native row-click callback. The per-image tab uses an explicit per-row `st.button` ("View image") instead of relying on dataframe selection events. `st.dialog` requires Streamlit ≥1.33 — pin in `pyproject.toml`.

**Per-image axis filter** — the user can set "gantry = 0" and see all images with gantry 0 regardless of collimator/couch. Implementation: filter `wl.results_data().image_details` on `variable_axis` or on parsed axis values from each image's key. Filter UI: a column-dropdown (`gantry | collimator | couch`) + a numeric input.

**Tolerance display (UI-only)** — sidebar widget, default `1.0` mm from config. Applied as `passing = max_2d_cax_to_bb <= tolerance_mm`. Never passed to pylinac's `analyze()`. Stored in session_state, not in the xlsx.

### D8: Error handling — two postures

| Mode | Failure | Display |
|---|---|---|
| Simple | No runfolders in machine's WL directory | "No runfolders found for LA2 at /data/LA2/WinstonLutz. Contact physics IT." |
| Simple | Newest runfolder has 0 DICOMs | "Runfolder <name> is empty. Wait for DICOM export to complete, then click the button again." |
| Simple | pylinac analysis raises | "Analysis failed: <single-line summary>. Switch to Advanced mode to debug." (full traceback logged server-side, NOT shown) |
| Simple | xltx template missing | "WL template missing at <path>. Contact physics IT." |
| Simple | Output directory not writable | "Cannot write to <path>. Contact physics IT." |
| Advanced | Any failure | Full error + traceback inline, with "Adjust parameters and re-run" prompt |

The simple-mode error wrapper catches `Exception`, logs the full traceback via `logging.exception`, and renders only a one-line user-safe summary. The summary is keyed off the exception type with a fallback.

### D9: Docker Compose layout

```yaml
services:
  streamlit:
    build: .
    expose:
      - "8501"              # container-internal only; not published
    volumes:
      - /mnt/hospital/RT_DICOM:/data:ro
      - /mnt/hospital/RT_Results:/out:rw
      - ./machines.yaml:/app/machines.yaml:ro
      - ./templates:/app/templates:ro
      - /mnt/hospital/RT_Assets:/assets:ro
    restart: unless-stopped

  caddy:
    image: caddy:2
    ports:
      - "80:80"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
    depends_on:
      - streamlit
    restart: unless-stopped
```

**Caddyfile (v1 baseline)** — HTTP + IP allowlist, structured for escalation:

```caddy
{
    auto_https off
}

:80 {
    @allowed remote_ip 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16
    handle @allowed {
        reverse_proxy streamlit:8501
    }
    respond "Forbidden" 403
}

# Escalation paths (commented; uncomment + adjust when ready):
#
# real_cert:
#   rt-qa.hospital.internal {
#       tls /certs/hospital.crt /certs/hospital.key
#       reverse_proxy streamlit:8501
#   }
#
# basic_auth:
#   :80 {
#       basic_auth { ethan <bcrypt-hash> }
#       reverse_proxy streamlit:8501
#   }
```

**Alternatives considered:**
- *Auth baked into Streamlit (e.g. streamlit-authenticator)*: rejected — auth concerns belong at the reverse proxy; avoids coupling app code to auth strategy
- *NGINX instead of Caddy*: rejected — Caddy's config is more readable; auto-HTTPS-ready when hospital certs become available
- *Single container (Streamlit + Caddy in one image)*: rejected — separating concerns aids independent updates

### D10: Asset handling — bind-mounted `/assets` with repo-baked default

The Fry meme (and future logo) live at `/assets/fry_money.png` inside the container, bind-mounted from the hospital network. The app loads via `st.image` with a graceful fallback:

```python
def render_fry_meme():
    path = Path(config.assets.fry_meme_path)
    if path.exists():
        st.image(str(path))
    else:
        st.info(f"Drop a meme image at: {path}")
```

This lets the user upload the Fry meme (or swap it later) by editing the network share, without rebuild.

**Default asset (committed to repo at `assets/fry_money.png`)**: the canonical Fry "shut up and take my money" meme, sourced from <https://imgflip.com/i/auf87m>. The image is downloaded once during project scaffolding and committed so the app works out-of-the-box without requiring the bind-mount to be populated. The bind-mount overrides the baked-in default when present, so physicists can swap memes without rebuilding the Docker image.

## Risks / Trade-offs

- **[Network share latency]** Hospital SMB shares can be slow; pylinac loads all DICOMs eagerly → 5-30s analysis runs.
  → Mitigation: caching (D6); "Running analysis..." spinner with explicit messaging; future option to copy-to-local-tmp before analysis if measured latency is pathological.

- **[Concurrent xlsx writes]** Two physicists writing the same `<machine>_WL_<runfolder>/` simultaneously could corrupt.
  → Mitigation: session-folder naming includes runfolder name, which is unique per session per machine; collisions require two physicists running the same runfolder simultaneously, which is unlikely and recoverable (re-click button). No file locking in v1.

- **[MyQA template drift]** If someone edits `templates/winston_lutz.xltx` and forgets to update MyQA's mapping, imports silently break.
  → Mitigation: the xltx is bind-mounted read-only from a host path controlled by physics IT; changes go through a documented update procedure (edit → test against MyQA staging → swap). Version stamp the template in a named cell (`template_version`).

- **[Streamlit caching invalidation]** If a physicist re-runs the same runfolder after DICOM export was incomplete, the cache returns stale results.
  → Mitigation: include the runfolder's DICOM file count + total mtime in the cache key, so new files invalidate automatically. Surface "analyzed N images" in the UI so incomplete runs are visually obvious.

- **[pylinac API drift]** pylinac v3.45 changed axis-data handling; future major versions could break the wrapper.
  → Mitigation: pin pylinac version in `pyproject.toml`; wrapper isolates pylinac API to one module (`core/wl_runner.py`).

- **[No auth in v1]** Anyone on the hospital subnet can access the app and trigger analysis.
  → Mitigation: IP allowlist at Caddy limits to hospital subnet; DICOM mount is read-only; the worst case is a wasted analysis run, not data corruption. Document the escalation path in Caddyfile comments.

## Open Questions

1. **Pass/fail tolerance granularity** — single `tolerance_mm` applied to `max_2d_cax_to_bb` (recommend), or per-metric tolerances? Captured as a single tolerance in v1; per-metric can be added to the xltx later without breaking MyQA.
2. **Session date source** — parse from runfolder name (only viable if the treatment machine's naming convention is stable) or read from the first DICOM's `AcquisitionDate` tag? Recommend DICOM tag (authoritative); fall back to runfolder mtime if missing.
3. **Test fixtures** — use pylinac's `generate_winstonlutz` to synthesise DICOMs in-test (deterministic, no committed binary fixtures) or commit a small anonymised real sample? Recommend synthetic — reproducible across CI environments.
4. **Per-image sheet name sanitisation** — pylinac keys like `G0B0P0` fit Excel's 31-char limit, but combos like `G180B270P315` are still short. Confirm no sanitisation needed in practice; truncation rule in place as a safety net.
