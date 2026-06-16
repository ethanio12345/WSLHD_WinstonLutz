## 1. Project scaffolding

- [x] 1.1 Create `pyproject.toml` (hatchling build, pinned deps: `pylinac>=3.45`, `streamlit>=1.33`, `plotly`, `openpyxl`, `pyyaml`, `pydantic`; dev deps: `pytest`, `pytest-cov`, `ruff`, `mypy`, `requests` for integration tests)
- [x] 1.2 Create directory structure (`app.py`, `pages/`, `core/`, `templates/`, `assets/`, `tests/`, plus empty `__init__.py` where appropriate)
- [x] 1.3 Download the Fry meme from `https://imgflip.com/i/auf87m` to `assets/fry_money.png` (or fetch the underlying image URL via `curl`; commit the binary to the repo as the baked-in default per design D10)
- [x] 1.4 Create `machines.yaml.example` showing one machine (`LA2`), `output.root`, `analysis_defaults.winston_lutz` (required + optional keys per `machine-config` spec), `assets` paths
- [x] 1.5 Create `.gitignore` (Python, `__pycache__/`, `.mypy_cache/`, `.venv/`, `machines.yaml` — only the `.example` is committed)
- [x] 1.6 Create `ruff.toml` and `mypy.ini` (target Python 3.10+, line length 100, strict mypy for `core/`)
- [x] 1.7 Implement `app.py` Streamlit entry point — at first script run, call `load_config()` (2.2), template validation (2.3), and `output.root` writability probe; configure logging to stdout (9.4); render home page (mode toggle, module selector, Fry meme via 6.0); refuse to render any page if any startup check fails (display the specific failure message instead)

## 2. Config layer (machine-config spec)

- [x] 2.1 Define pydantic models in `core/config.py`: `MachineConfig`, `OutputConfig`, `WLDefaults`, `AssetsConfig`, `AppConfig` (with `MachineScale` enum pulled from pylinac)
- [x] 2.2 Implement `load_config(path: Path) -> AppConfig` in `core/config.py` — reads YAML, validates with pydantic, then performs filesystem validation (each machine's `dicom_roots.winston_lutz` exists; `output.root` exists and is writable via probe-write)
- [x] 2.3 Implement template validation in `core/config.py`: load `templates/winston_lutz.xltx`, enumerate defined names, verify all 25 required names (24 metrics + `template_version`) are present
- [x] 2.4 Write `tests/test_config.py` — happy path (valid config + template), missing required key (pydantic error), nonexistent DICOM root, read-only `output.root`, template missing named cells, optional pylinac parameter absent (succeeds). Note: happy-path template test depends on 2.5 having generated the template — run 2.5 first.
- [x] 2.5 Generate `templates/winston_lutz.xltx` programmatically via a one-time setup script `scripts/build_xltx_template.py` using openpyxl — creates summary sheet, defines 25 named cells with sensible layout (session metadata row, then metric table), applies basic formatting (column widths, header bold), sets `template_version` to `2026-06`. Output the `.xltx` to `templates/`. Run the template validator (2.3) against it to verify all 25 names present.

## 3. WL runner (core/wl_runner.py)

- [x] 3.1 Define `WLAnalysisResult` frozen dataclass in `core/result_types.py` with identity fields (`machine_id`, `runfolder_path`, `session_date`) per design D6, `summary` dict, `image_details` list, `image_keys` list, plotly-ready arrays (`deviation_vs_gantry`, `bb_xy_scatter`, `distance_histogram`), `params_used` dict
- [x] 3.2 Implement `find_newest_runfolder(dicom_root: Path) -> Path | None` (mtime-based, returns `None` if no subdirs)
- [x] 3.3 Implement `count_dicoms(runfolder: Path) -> int` and `runfolder_mtime(runfolder: Path) -> float` (for cache key)
- [x] 3.4a Implement `run_wl_analysis(...)` core in `core/wl_runner.py` — wraps `pylinac.WinstonLutz(dicom_root).analyze(...)`, extracts `results_data(as_dict=True)` and maps the 24 metrics + identity fields into `WLAnalysisResult.summary`, extracts `keyed_image_details` into `image_details`/`image_keys` parallel arrays, stashes `params_used`
- [x] 3.4b Implement Plotly-ready array precomputation — iterate `image_details` to build `deviation_vs_gantry` ({x: gantry angles, y: cax2bb_distance, text: image keys}), `bb_xy_scatter` ({x: bb X deviation, y: Y deviation, color: variable axis}), `distance_histogram` ({values: all cax2bb distances}); attach to `WLAnalysisResult`
- [x] 3.5 Write `tests/test_wl_runner.py` — use `pylinac.core.image_generator.generate_winstonlutz` to synthesise DICOMs in a tmp_path; test happy path (offset BB → predicted `max_2d_cax_to_bb`), empty runfolder (`None` return), per-image parallel arrays alignment, Plotly arrays shape/values

## 4. Excel writer (core/excel_writer.py, wl-result-export spec)

- [x] 4.1 Implement `set_named_cell(wb: Workbook, name: str, value) -> None` — resolve defined name → target cell → set value; raise `KeyError` with clear message if name not defined
- [x] 4.2 Implement `sanitise_sheet_name(name: str) -> str` — replace `\ / ? * [ ] :` with `_`, truncate to 30 chars + `…` if length > 31
- [x] 4.3 Implement `write_session_output(result: WLAnalysisResult, output_root: Path, template_path: Path) -> Path` — create `/out/<MACHINE>/WL/<MACHINE>_WL_<RUNFOLDER>/`, `shutil.copy` template as `.xltx`, load via openpyxl, populate 24 metric named cells + `template_version`, write per-image sheets (title from `image_keys[i]`, contents from `image_details[i]` as header-based table), save as `.xlsx`, return xlsx path
- [x] 4.4 Write `tests/test_excel_writer.py` — verify all 25 named cells populated with expected values, sheet count = N+1 (summary + per-image), sanitisation edge cases, title/content parallel alignment, tolerance NOT written

## 5. (Template generation moved to task 2.5 so it precedes the validator tests in Group 2)

## 6. Simple mode UI (pages/1_Winston_Lutz.py, wl-simple-mode spec)

- [x] 6.0 Implement `render_asset(path: Path, placeholder_msg: str)` UI utility — uses `st.image(str(path))` if file exists, else `st.info(placeholder_msg)`. Called for the Fry meme on the WL page per machine-config R5. Used by `app.py` (1.7) for the home page.
- [x] 6.1 Implement sidebar machine dropdown — `st.selectbox` populated from `AppConfig.machines` (alphabetically sorted by machine key), showing `display_name`, returning machine key. Includes the empty-state branch: if no machines configured, display "No machines configured. Edit machines.yaml and reload." banner and disable downstream widgets.
- [x] 6.2 Implement runfolder preview — calls `find_newest_runfolder` + `count_dicoms`, displays "Will analyze: `<name>` (N DICOMs)" or appropriate error/disabled-button state (no runfolders, empty runfolder)
- [x] 6.3 Implement the "Shut Up and Give Me My MyQA Results" button — `st.button` calls `run_wl_analysis` with `analysis_defaults` from config, wrapped in `st.spinner("Running Winston-Lutz analysis...")`
- [x] 6.4 Implement success card — `st.success` block showing output xlsx path, `max_2d_cax_to_bb` with `[PASS]`/`[FAIL]` against `tolerance_mm`, `median_2d_cax_to_bb` and `gantry_3d_iso` as plain values, "View in Advanced mode" `st.button`
- [x] 6.5 Implement error wrapper — `try/except Exception` around `run_wl_analysis` and `write_session_output`; `logging.exception(...)` to stdout; render one-line user-safe message keyed off exception type with fallback ("Analysis failed: <summary>. Switch to Advanced mode to debug.")
- [x] 6.6 Implement Simple→Advanced hand-off — on "View in Advanced mode" click, set `st.session_state["wl_result"] = result`, `st.session_state["mode"] = "advanced"`, `st.rerun()`

## 7. Advanced mode UI (pages/1_Winston_Lutz.py continued, wl-advanced-mode spec)

- [x] 7.1 Implement Advanced sidebar — `st.number_input`/`st.checkbox`/`st.selectbox` for all 9 pylinac params + `tolerance_mm` widget + "Re-run analysis" + "Download xlsx" buttons. Defaults from config OR from `session_state["wl_result"].params_used` on hand-off
- [x] 7.2 Implement Overview tab — `st.dataframe` of `WLAnalysisResult.summary`, with `[PASS]`/`[FAIL]` column populated only for `max_2d_cax_to_bb`; "Analysed with: ..." summary line from `params_used`
- [x] 7.3 Implement Per-image tab — `st.dataframe` of `image_details`; axis filter (`st.selectbox` for axis + `st.number_input` for value); per-row `st.button("View image")` that renders `wl_obj.images[i].plot()` inline below
- [x] 7.4 Implement Plots tab — three `st.plotly_chart` calls sourced from `deviation_vs_gantry`, `bb_xy_scatter`, `distance_histogram` (no recomputation at render time)
- [x] 7.5 Implement Detection overlay tab — grid of `st.pyplot(wl.images[i].plot())` (4 columns, each annotated with image key); `st.dialog` (Streamlit ≥1.33) opens on click with full-size figure. **Depends on 7.6** — implement lazy `wl_obj` init first.
- [x] 7.6 Implement lazy `wl_obj` init — on first Advanced render needing `wl.images`, populate `st.session_state["wl_obj"]` from `WLAnalysisResult.runfolder_path` + params (one-time load per Advanced session). **Should be implemented before 7.5** (Detection overlay tab depends on `wl_obj`).
- [x] 7.7 Implement hand-off reception — on Advanced entry, if `st.session_state["wl_result"]` is set, render Overview immediately without re-running; populate sidebar widgets from `params_used`
- [x] 7.8 Implement "Re-run analysis" handler — invalidate `session_state["wl_obj"]`, call cached `run_wl_analysis` with new sidebar values, update `session_state["wl_result"]`; on cache short-circuit, show "Result loaded from cache (parameters unchanged)"
- [x] 7.9 Implement "Download xlsx" handler — call `write_session_output` with current `wl_result`, then `st.download_link` (or `st.download_button`) for the produced xlsx

## 8. Caching (wiring into existing modules)

- [x] 8.1 Decorate `run_wl_analysis` with `@st.cache_data(show_spinner="Running Winston-Lutz analysis...")` — verify cache key tuple includes `machine_id`, `runfolder_path`, all 9 analyze params, and `dicom_file_count` + `runfolder_mtime`
- [x] 8.2 Verify `WLAnalysisResult` is picklable (frozen dataclass with primitives + dicts/lists of primitives) — write a smoke test that pickles and unpickles a result
- [x] 8.3 Write `tests/test_caching.py` — call `run_wl_analysis` twice with identical inputs (mock pylinac), assert the underlying `WinstonLutz.analyze` is called once; call with different `bb_size_mm`, assert called twice

## 9. Docker deployment (container-deployment spec)

- [x] 9.1 Write `Dockerfile` — `FROM python:3.13-slim`, install `uv`, `uv sync`, create `appuser` UID 1000, `COPY` app code, `USER appuser`, `EXPOSE 8501`, `CMD ["uv", "run", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]`
- [x] 9.2 Write `docker-compose.yml` — `streamlit` service (build `.`, `expose: ["8501"]`, 5 volumes per design D9, `restart: unless-stopped`); `caddy` service (`image: caddy:2`, `ports: ["80:80"]`, `volumes: ["./Caddyfile:/etc/caddy/Caddyfile:ro"]`, `depends_on: [streamlit]`, `restart: unless-stopped`)
- [x] 9.3 Write `Caddyfile` — `auto_https off`; `:80` block with `@allowed remote_ip` (RFC1918 ranges), reverse-proxy to `streamlit:8501`, `respond "Forbidden" 403` fallback; commented escalation blocks for `real_cert`, `basic_auth`, OIDC via `forward_auth`
- [x] 9.4 Configure stdout logging — in `core/logging_config.py` (or top of `app.py`), `logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")`
- [x] 9.5 Write `tests/test_docker.py` (marked `@pytest.mark.integration`) — `subprocess.run(["docker", "compose", "up", "-d"])`, wait for healthy, `requests.get("http://localhost:80/")` returns 200, `requests.get` from outside allowlist returns 403. Also assert: `docker exec <container> ps -o user= -p 1` returns `appuser` (non-root, R9); writing to `/data` fails (read-only mount, R2); root-owned `machines.yaml` bind-mount produces clear startup permission error (R3). Skip gracefully if Docker daemon unavailable.

## 10. End-to-end tests

- [x] 10.1 Write `tests/integration/test_simple_mode_e2e.py` — synthesize DICOMs in tmp_path, write a temporary `machines.yaml` pointing to them, run `run_wl_analysis` + `write_session_output`, verify the produced xlsx exists, has 25 named cells populated, sheet count = N+1
- [x] 10.2 Write `tests/integration/test_advanced_mode_e2e.py` — synthesize DICOMs, simulate Simple→Advanced hand-off by directly populating `st.session_state` (or test the underlying functions), call re-run with new `bb_size_mm`, verify `wl_result` updated and xlsx overwritten
- [x] 10.3 Write `tests/test_error_handling.py` — feed corrupt DICOMs, missing template, read-only output dir; verify one-line user-safe message + full traceback in caplog

## 11. Documentation

- [x] 11.1 Write `README.md` — what the project is, quickstart (`docker compose up -d`), how to populate `machines.yaml`, host file ownership requirement (chown to UID 1000), how to update the Fry meme, escalation path for auth/HTTPS
- [x] 11.2 Document the `machines.yaml` schema in `docs/CONFIGURATION.md` (all fields, required vs optional, examples for one machine and multiple machines)
- [x] 11.3 Document the xltx template update procedure in `docs/TEMPLATE_UPDATES.md` (edit template → run validation → test against MyQA staging → bump `template_version` → deploy)
- [x] 11.4 Document deployment ops runbook in `docs/DEPLOYMENT.md` — volume mount paths, IP allowlist CIDR adjustment, log access via `docker logs`, common failure modes (permission denied, mount missing, MyQA import failure)

## 12. Verification

- [x] 12.1 Run full Python verification pipeline: `uv run ruff format`, `uv run ruff check --fix`, `rm -rf .mypy_cache && uv run mypy core/`, `uv run pytest tests/ -v` — all must pass
- [x] 12.2 Verify all spec scenarios have at least one corresponding test (cross-reference `specs/*/spec.md` scenarios with `tests/**`)
- [x] 12.3 Manual smoke test with synthetic DICOMs in Docker: container starts, simple mode writes xlsx, advanced mode tabs render, re-run works, dialog opens
