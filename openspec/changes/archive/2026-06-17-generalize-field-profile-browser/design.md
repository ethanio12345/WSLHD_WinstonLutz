# Design: generalize-field-profile-browser

## D1: Cascading folder browser (selectboxes, sandboxed)

The machine + runfolder dropdowns are replaced by a **cascading selectbox**
browser rooted at `field_profile.browse_root` (config, default `/data`).

**Render model** — selectboxes are rendered level-by-level, persisted in
`st.session_state["fp_browser_path"]` (a list of path components):

```
browse_root/
  └─ selectbox L1: immediate subdirs of browse_root
       └─ selectbox L2: immediate subdirs of selected L1
            └─ ... (a new selectbox renders whenever the current folder has
                  subdirs; "📁 Use this folder" button + image dropdown render
                  at the current level regardless)
                 └─ selectbox: DICOM images in the selected folder
```

**Rules:**
- Each selectbox lists immediate subdirectories only (sorted alphabetically).
  Files are never listed in the folder selectboxes.
- Changing a higher-level selectbox truncates the deeper levels (re-branches).
- **Sandbox**: the browser CANNOT navigate above `browse_root`. No `..`, no
  absolute-path escape. Defense in depth (the page must not enumerate arbitrary
  host paths in a browser).
- A "📁 Use this folder" button is always available at the current level; it
  populates the image dropdown from the current folder. (Equivalently, the
  image dropdown auto-populates from the deepest selected folder.)
- **Empty/non-existent folder**: inline info message, no crash (mirrors the
  existing `_render_image_dropdown` empty-state).

**Why selectboxes over a text input**: user explicitly chose "selectable boxes"
(cascading), no path typing. Selectboxes are also safer (can't typo a path) and
discoverable (the physicist sees what folders exist).

## D2: In-browser result + browser download (no server writes)

The `output_root`/session-folder disk-write path is **removed**. The excel
writer is refactored:

- **Before**: `write_fp_session_output(result, output_root, template_path) -> Path`
  (copies `.xltx`, loads it, populates 30 named cells + 4 data sheets, saves
  `.xlsx` to `<output_root>/FP/<MACHINE>_FP_<IMAGE_STEM>/`).
- **After**: `build_fp_xlsx_bytes(result, template_path) -> bytes` — loads the
  `.xltx` template from disk, populates the same 30 named cells + 4 data sheets,
  saves to an in-memory `io.BytesIO`, returns the bytes. **No `output_root`,
  no session folder, no machine key, no `.xltx` disk copy.**

The page renders the result in-browser (success card / Advanced tabs, unchanged)
and offers `st.download_button(label="Download xlsx", data=<bytes>,
file_name="<IMAGE_STEM>.xlsx", mime=...)`. The browser writes it to the user's
Downloads. The 30 named cells (MyQA contract) are intact inside the downloaded
xlsx — MyQA import still works, just delivered via browser instead of a server
share.

`core/session_io.py` (`build_session_folder`, `copy_template_to_session`) is no
longer called by the FP path. The helpers stay (WL/CatPhan still use them).

## D3: Config decoupling

| Config element | Before | After |
|---|---|---|
| `machines.<key>.dicom_roots.field_profile` | optional, validated, enabled the page | **removed** (becomes a forward-compat/ignored key like `trajectory_log`) |
| `analysis_defaults.field_profile` | required iff a machine had field_profile | **optional** — centre-wide defaults; if absent, page uses `protocol: VARIAN` + pylinac defaults |
| `field_profile.browse_root` (new, top-level) | n/a | optional, default `/data`; the browser root |
| `has_field_profile()` | checked machines' dicom_roots | **repurposed**: returns `True` always (page always available); kept for app.py home-page display logic |
| FP template validation (`app.py`) | conditional on `has_field_profile()` (machines) | conditional on the FP page being shipped (always, since the template is committed) — validated at startup unconditionally now |

`FieldProfileDefaults` model stays (used to parse `analysis_defaults.field_profile`
when present). `_KNOWN_MODULE_KEYS` no longer includes `field_profile` (it's not
a dicom_root key anymore); `field_profile` joins `trajectory_log` as a
forward-compat/ignored dicom_root key.

## D4: Page always available

The FP page is always shown in the sidebar (it's a general tool). The home page
lists it as available unconditionally (no "not configured" caveat). The only
config that affects it is the optional `analysis_defaults.field_profile`
(defaults) and optional `field_profile.browse_root` (browser root).

## D5: Risks

- **Large directory trees** — a `browse_root` with thousands of subdirs would
  make a selectbox unwieldy. Mitigation: this is a hospital RT data share with
  machine/date-organised folders; trees are shallow. If it becomes a problem,
  add a search/pagination later (out of scope).
- **Browser download ≠ server audit trail** — previously the xlsx landed on a
  shared output share (audit trail). Now it goes to the user's Downloads.
  Acceptable: the user explicitly chose this; MyQA import is the system of
  record. The runner result still logs to stdout.
