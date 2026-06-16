## proposal Round 1 — 2026-06-16

Batch: proposal.md (first artifact — nothing frozen)
Baseline: explore-brief.md

### 🔴 Fixed
(none — first review)

### 🟡 Addressed
(none — first review)

### 🔴 Outstanding
(none)

### 🟡 Notes

1. **Canonical `openspec/specs/` was empty** — `machine-config` baseline only existed in the archive. The OpenSpec tooling would reject `## MODIFIED Requirements` without a canonical baseline. FIXED before continuing: promoted archived WL specs to canonical (`openspec/specs/`) and converted from delta format (`## ADDED Requirements`) to flat format (`## Purpose` + `## Requirements`).
2. **Named-cells contract grouped, not enumerated** — `cbct-result-export` summarises ~19 cells by category; brief lists all 19 names. Pin the list in the proposal.
3. **Session-folder naming convention referenced but not pinned** — `/out/<MACHINE>/CatPhan/<MACHINE>_CP_<RUNFOLDER>/` is locked in the brief but only gestured at in the proposal.
4. **Advanced-mode error posture not stated** — proposal captures Simple side (no raw stack traces); add the Advanced side (full errors surfaced).
5. **Operator-facing config migration not in Impact** — note that operators must add `catphan:` under `dicom_roots` in `machines.yaml` for each machine that adopts CatPhan.
6. **Brief internal inconsistency (informational)** — brief line 25 says "WL is required (existing centres depend)" while line 31 says both optional. Proposal correctly adopted both-optional; no action needed.

### 💡 Optional

- What Changes names specific helper functions — borderline implementation-level. Acceptable as scope signaling.
- Impact section could note testing scope (unit tests for extracted core modules, page-level integration test).

---

**Verdict**: Ready to freeze (0 🔴 outstanding). All 6 🟡 notes applied as improvements.
- Note 1 (canonical specs) already FIXED via promotion.
- Notes 2-5 applied as declarative edits to proposal.md.
- Note 6 is informational; no action.

---

## design Round 1 — 2026-06-16

Batch: design.md only (proposal.md is frozen)
Baseline: proposal.md (frozen) + explore-brief.md (reference) + openspec/specs/ (canonical) + core/ implementation (cross-check)

### 🔴 Fixed
(none — first review of this batch)

### 🟡 Addressed
(none — first review of this batch)

### 🔴 Outstanding

1. **D6 `build_session_folder` is a path REDESIGN, not a refactor** — proposed
   `module_id.replace("_", "-").title()` produces `Winston-Lutz/` not `WL/`,
   violating frozen `wl-result-export` spec. Three-way conflict between code,
   prose, and existing `_session_folder` implementation. Required: pick ONE
   canonical path layout for both WL and CatPhan.
2. **D3 Module dropdown contradicts proposal's separate-page architecture** —
   proposal clearly names `pages/2_CatPhan.py` as a separate file. D3
   introduces a unified sidebar `Mode | Module | Machine` for a single-page
   model. Decision-level UX conflict.

### 🟡 Notes

1. D8 doesn't enumerate the 19 named cells.
2. D7 off-by-one: prose says "11 params" but signature has 10.
3. D3 references `button_label` config but D2 schema doesn't list it.
4. D8 omits the parallel "tolerance excluded from xlsx" rule.
5. D5 doesn't say where the dataclass lives.
6. D1's `caching.py` is a new abstraction, not pure extraction.
7. Design omits `core/ui_utils.py` (existing helpers).
8. Pre-existing spec/implementation divergence on WL path (informational).

---

**Round 1 Verdict**: NOT ready to freeze. 2 🔴 blockers.

Applying all fixes before Round 2:
- 🔴 #1: Updated canonical `wl-result-export` spec to match existing implementation path
  (`/out/Clinical QA/<display>/Pylinac/WL/...`). Rewrote D6 to faithfully extract
  the existing pattern, parameterised over module via a literal `module_dir`
  argument and a small dispatch dict. No WL behavior change.
- 🔴 #2: Rewrote D3 to match proposal's separate-page model. Dropped Module
  dropdown; CatPhan is `pages/2_CatPhan.py` with machine dropdown filtered to
  CatPhan-configured machines. Dropped `button_label` config (centre-wide
  consistency).
- 🟡 #1: Enumerated all 19 cells in D8.
- 🟡 #2: Corrected D7 prose to "10 parameters".
- 🟡 #3: Dropped `button_label` (covered by 🔴 #2 fix).
- 🟡 #4: Added tolerance-exclusion clause to D8.
- 🟡 #5: Pinned `CatPhanAnalysisResult` to `core/result_types.py` in D5.
- 🟡 #6: Called out `caching.py` as new abstraction in D1 with test boundary note.
- 🟡 #7: Mentioned `core/ui_utils.py` in D1 (not touched, remains shared).
- 🟡 #8: Resolved via canonical spec fix (covered by 🔴 #1).

---

## design Round 2 — 2026-06-16

Batch: design.md (proposal.md was frozen; canonical wl-result-export spec updated)
Baseline: proposal.md (frozen, then soft-unfrozen for 2-line declarative path correction) + explore-brief.md (reference) + openspec/specs/ (canonical)

### 🔴 Fixed

1. **D6 path layout redesign (Round 1 🔴 #1)** — RESOLVED. D6 now faithfully
   extracts existing `_session_folder` pattern. Canonical `wl-result-export`
   spec updated to match implementation.
2. **D3 Module dropdown contradicts proposal (Round 1 🔴 #2)** — RESOLVED.
   D3 rewritten to separate-page model per proposal.

### 🟡 Addressed

1-8: All Round 1 🟡 fixes verified individually (19-cell enumeration, 10-param
prose, button_label drop, tolerance exclusion, result file location pinned,
caching.py flagged as new abstraction, ui_utils.py mentioned, WL spec divergence
resolved via canonical spec update).

### 🔴 Outstanding

1. **Frozen proposal had stale flat CatPhan path** — caught in Round 2. RESOLVED
   via soft-unfreeze: patched proposal.md lines 21 and 32 to use the deep path
   `/out/<CATEGORY>/<MACHINE_DISPLAY>/<PYLINAC_SUBFOLDER>/CatPhan/<MACHINE>_CP_<RUNFOLDER>/`
   matching D6 and the canonical WL pattern. Proposal re-frozen.

### 🟡 Notes

1. **Risks section reworded** — removed stale "module dropdown" / "defaults to
   Winston-Lutz" language from two risks; replaced with separate-page phrasing.

---

**Round 2 Verdict**: Ready to freeze (0 🔴 outstanding). Proposal soft-unfrozen
for declarative 2-line path correction then re-frozen. Design is internally
consistent and aligned with the (corrected) proposal + canonical specs.

---

## specs Round 1 — 2026-06-16

Batch: specs/ (4 files; proposal.md + design.md are frozen)
Baseline: proposal.md (frozen) + design.md (frozen) + explore-brief.md (reference) + openspec/specs/ (canonical)

### 🔴 Fixed
(none — first review)

### 🟡 Addressed
(none — first review)

### 🔴 Outstanding

1. **`tolerance_mm` semantics contradiction for CatPhan** — Advanced mode
   said "tolerance updates pass/fail" but Overview said "pass/fail is only
   on the four pylinac flags" (which don't depend on tolerance_mm). No
   metric ever gated by tolerance_mm. RESOLVED: dropped tolerance_mm entirely
   from CatPhan. Soft-unfroze proposal + design D4 + D8.
2. **Missing MODIFIED wl-simple-mode spec** — machine-config change filters
   WL dropdown to WL-configured machines but canonical wl-simple-mode said
   "all machines". RESOLVED: added MODIFIED wl-simple-mode spec capturing
   the dropdown filtering behavior.

### 🟡 Notes

1. `cp_obj` vs `cbct_obj` typo — UNIFIED to `cp_obj` per design D4.
2. CTP486 columns contradict within spec — ALIGNED (added stdev to
   requirement text to match scenario).
3. "Every parameter" silently excludes `expected_hu_values` — CLARIFIED
   as "every scalar parameter" with note about dict-typed
   `expected_hu_values` being config-only.
4. "Page hidden" vs "empty dropdown + banner" — RESOLVED (changed
   "hidden" to "reachable with empty dropdown + banner" per Streamlit's
   pages/ auto-discovery).
5. Forward-compat validation phrasing — FIXED ("at least one module
   root" instead of enumerating WL+CatPhan).
6. Column drift from design D8 — informational; specs internally
   consistent and richer than directional design.

### 💡 Optional

- CTP515 tab didn't specify pylinac call for sub-image; left as-is
  (implementer can derive from `plot_analyzed_subimage('low_contrast')`).

---

**Round 1 Verdict**: NOT ready to freeze (2 🔴). All fixes applied before
Round 2: dropped tolerance_mm entirely from CatPhan (proposal/design/specs),
added MODIFIED wl-simple-mode spec for dropdown filtering, unified cp_obj,
aligned CTP486 columns, clarified expected_hu_values config-only status,
fixed page-hidden wording, generalized validation phrasing.

---

## specs Round 2 — 2026-06-16

Batch: specs/ (5 files; proposal.md + design.md are frozen; canonical wl-result-export spec updated)
Baseline: all previously frozen artifacts + explore-brief.md (reference) + openspec/specs/ (canonical)

### 🔴 Fixed

1. **tolerance_mm semantics contradiction (Round 1 🔴 #1)** — RESOLVED. Dropped
   tolerance_mm entirely from CatPhan across proposal, design D4+D8, all 5 specs.
2. **Missing MODIFIED wl-simple-mode (Round 1 🔴 #2)** — RESOLVED. Added
   well-formed MODIFIED wl-simple-mode spec for dropdown filtering.

### 🟡 Addressed

1-6: All Round 1 🟡 fixes verified (cp_obj unified, CTP486 columns aligned,
scalar-only sidebar clarified, page-hidden wording fixed, validation phrasing
generalized, column drift noted).

### 🔴 Outstanding

1. **design.md soft-unfreeze was incomplete** — D2 line 90 still had
   `tolerance_mm: 1.0` under catphan, and D4 line 142 still said
   "pass/fail flags against tolerance_mm". RESOLVED: soft-unfroze design,
   removed both stale references, refrozen.

### 🟡 Notes (all applied as declarative fixes)

1. cbct-result-export "No tolerance field" requirement overstated per-module
   sheet contents (claimed tolerances ARE written; specs don't list them).
   FIXED: removed "ARE written" claim.
2. cbct-advanced-mode missing "Full errors surfaced in Advanced mode"
   requirement. FIXED: added explicit requirement mirroring Simple mode's
   hide-traceback requirement.

---

**Round 2 Verdict**: Ready to freeze (0 🔴 outstanding). All Round 1 + Round 2
issues resolved. Specs internally consistent with corrected proposal + design +
canonical baselines.

---

## tasks Round 1 — 2026-06-16

Batch: tasks.md (all previously frozen artifacts: proposal.md, design.md, specs/×5)
Baseline: proposal.md (frozen) + design.md (frozen) + specs/ (frozen) + core/ implementation (cross-check)

### 🔴 Fixed
(none — first review)

### 🟡 Addressed
(none — first review)

### 🔴 Outstanding
(none)

### 🟡 Notes

1. **Session-state key naming inconsistency** — task 1.4 helpers use
   `f"{module_id}_*"` formula; if passed semantic name ("catphan"), produces
   `catphan_result` not `cp_result` per design D4. Hand-off would KeyError.
2. **No test task for MODIFIED wl-simple-mode dropdown filtering.**
3. **No test task for `core/caching.py` helper boundary** (design D1 requires).
4. **Forward-compat `field_profile` key handling ambiguous** — pydantic model
   might reject unknown keys; need explicit `extra="allow"` or free-form dict.
5. **Task 6.2 doesn't distinguish "No runfolders" from "Empty runfolder".**
6. **Tasks 4.2a and 5.1 may exceed 2-hour granularity.**

### 💡 Optional

- Task 6.0 marked "(already done)" with unchecked box.
- Task 2.4 sequencing note (template validation before template exists).
- `core/result_types.py` `__all__` should include `CatPhanAnalysisResult`.

---

**Round 1 Verdict**: Ready to freeze (0 🔴 outstanding). All 6 🟡 applied as
clarifications/splits before freezing.
