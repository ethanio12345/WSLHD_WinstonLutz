# Proposal: generalize-field-profile-browser

## Why

The Field Profile page shipped coupled to per-machine `dicom_roots.field_profile`
+ a runfolder dropdown, mirroring WL/CatPhan. In practice Field Profile is a
**general-purpose** flatness/symmetry tool — a physicist points it at *any* RT
image folder, not a pre-configured per-machine one. The per-machine coupling
forces a config edit + container restart every time a new folder needs
analysis, which defeats the "general purpose" use case.

## What changes

1. **Decouple from machines** — `field_profile` leaves per-machine `dicom_roots`
   entirely. FP becomes a standalone tool with no machine association. The page
   is always available; `analysis_defaults.field_profile` becomes optional
   (defaults to `protocol: VARIAN` + pylinac defaults if absent).

2. **Cascading folder browser** — replace the machine/runfolder dropdowns with a
   set of cascading selectboxes that drill down from a configurable
   `field_profile.browse_root` (default `/data`). No path typing; click to
   navigate. Sandboxed to `browse_root` (cannot escape above it).

3. **In-browser result + browser download (no server-side writes)** — remove
   the `output_root`/session-folder disk-write path and the paired `.xltx`
   copy. The analysis result is shown in-browser; a download button serves the
   populated xlsx straight to the user's Downloads via `st.download_button`
   with in-memory bytes. The 30 named cells (the MyQA contract) are preserved
   inside the downloaded xlsx.

## Scope

**In scope:** Field Profile page only (`pages/3_Field_Profile.py`), the FP excel
writer (`core/fp_excel_writer.py` — refactored to produce in-memory bytes),
FP-related config (`core/config.py`), FP tests, FP docs.

**Out of scope:** Winston-Lutz and CatPhan (keep their per-machine/runfolder
model — user confirmed FP-only). The 30 named cells / xltx template structure
itself is unchanged (still the MyQA contract). pylinac `FieldAnalysis` analysis
logic is unchanged (`core/fp_runner.py` untouched).

## Impact

- **Breaking config change**: any deployment using `dicom_roots.field_profile`
  must remove that key (now ignored/forward-compat). `analysis_defaults.field_profile`
  remains valid but is now optional.
- **Removed**: server-side FP output (`<output_root>/FP/...`), the paired
  `.xltx` disk copy, the FP session-folder builder usage.
- **Preserved**: the 30-cell xlsx (now delivered via browser download), all
  Advanced-mode tabs, FFF auto-detection, the runner.
