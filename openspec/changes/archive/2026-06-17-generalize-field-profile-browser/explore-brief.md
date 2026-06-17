# Explore Brief — generalize-field-profile-browser

## Context

The Field Profile page shipped (`add-field-profile-page`, archived 2026-06-17)
coupled FP to the per-machine `dicom_roots.field_profile` config + runfolder
dropdown, mirroring WL/CatPhan. In practice FP is a **general-purpose**
flatness/symmetry tool — a physicist points it at *any* RT image folder, not a
pre-configured per-machine one. This change makes FP standalone.

## User decisions (from explore conversation)

1. **Fully decoupled** — `field_profile` leaves per-machine `dicom_roots`
   entirely. FP is a standalone tool with no machine association.
2. **Cascading selectboxes** for the folder browser (click to drill down; no
   path typing).
3. **No server-side file writes** — result shown in-browser; a download button
   serves the xlsx straight to the user's Downloads via the browser
   (`st.download_button` with in-memory bytes). The `output_root`/session-folder
   path and the paired `.xltx` disk write are **removed**. The 30 named cells
   (MyQA contract) are preserved inside the downloaded xlsx.
4. **Field Profile only** — WL and CatPhan keep their per-machine/runfolder model.

## Design decisions made during explore (flag if wrong)

- **Browse root**: new optional top-level config `field_profile.browse_root`
  (defaults to `/data`, the DICOM mount). Cascading browser starts there.
- **Page enablement**: FP page is **always available**. `analysis_defaults.field_profile`
  becomes **optional** — if absent, defaults to `protocol: VARIAN` + pylinac
  defaults. No machine-coupled enablement flag.

## Rejected alternatives

- **(A) Keep `dicom_roots.field_profile` as an optional default browse root** —
  rejected: contradicts "fully decoupled" + "general purpose, not only for
  specific folders." Adds machine coupling the user explicitly removed.
- **(B) Text input for absolute path** — rejected: user chose "selectable boxes"
  (cascading selectboxes), no path typing.
- **(C) Keep server-side output + add download** — rejected: user said "no
  written output, just in-browser and a click to download to downloads." Server
  writes removed entirely.
- **(D) Apply browser model to WL/CatPhan too** — rejected: user confirmed
  "field profile only." WL/CatPhan are inherently per-machine/per-runfolder.

## Cascading folder-browser data flow

```
browse_root (config, default /data)
  └─ selectbox: subdirs of browse_root  (level 1)
       └─ selectbox: subdirs of selected L1  (level 2)
            └─ ... (dynamic depth: a new selectbox appears whenever the
                  current folder has subdirs; a "Use this folder" action +
                  the image dropdown appear when the user stops drilling)
                 └─ selectbox: DICOM images in the selected folder
                      └─ (Simple: FFF detect → analyze → in-browser card + download)
```

Implementation: render selectboxes level-by-level in `st.session_state`. Each
selectbox lists immediate subdirectories (sorted). When the selected folder
has no further subdirs (or the user clicks "Analyse this folder"), the image
dropdown is populated from that folder. A "go up" affordance isn't needed
because each level is an independent selectbox (change any level to re-branch).

## Open questions

- **Browse-root security**: should the browser be sandboxed to `browse_root`
  (no escaping above it), or allow navigating to any path? **Decision: sandbox
  to `browse_root`** — prevents the page from listing arbitrary host paths in a
  browser (defense in depth). Documented in design.
- **Empty folder**: if the selected folder has no DICOMs, show an inline info
  message (no crash). Already the existing `_render_image_dropdown` behaviour.
