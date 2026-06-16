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

1. **Missing Non-goals — 2 of 7 brief-rejected alternatives not captured**
   Brief lines 21-22 reject CBCT-WL (`from_cbct`) and multi-machine batch run.
   Proposal has no Non-goals section; these 2 items appear nowhere. The other
   5 rejected alternatives are implicitly covered by positive statements
   (Streamlit, paired xltx, hierarchical output, HTTP-first, deferred page
   abstraction). Risk: implementer adds CBCT-WL or batch mode → scope creep.
   Fix: add a Non-goals section explicitly excluding: CBCT-WL (`from_cbct`),
   multi-machine batch, HTTPS/basic-auth/OIDC (v1), shared page abstraction.

2. **Error-handling behavior not surfaced in `wl-simple-mode`**
   Brief line 35: "Never show pylinac stack traces in simple mode." Proposal
   `wl-simple-mode` (line 20) describes only the happy path (success card).
   This is a testable, user-facing requirement with clinical-UX implications.
   Risk: spec author writes happy-path-only scenarios → stack traces leak to
   clinical users. Fix: add error-state behavior to the capability description
   (physicist-friendly messages; no raw pylinac traces in simple mode).

3. **Pass/fail tolerance UI missing from `wl-advanced-mode`**
   Brief line 32 lists "pass/fail tolerance (UI-only)" as a distinct sidebar
   element. Proposal `wl-advanced-mode` (line 21) mentions only "pylinac
   analyze() parameters" — the tolerance display is omitted. It is UI-only
   (display), so it is a separate feature from pylinac parameters. Risk:
   tolerance display missed → physicists can't see pass/fail at a glance.
   Fix: add "pass/fail tolerance display (UI-only)" to the capability.

4. **Simple→Advanced hand-off semantics vague**
   Brief Q4 (line 49) recommends "preserve via session_state." Proposal
   `wl-simple-mode` (line 20) says "hand-off to Advanced mode" without
   specifying preserve vs re-run. Risk: implementer re-runs → wasted analysis,
   added latency, potentially different results. Fix: clarify to "hand-off
   to Advanced mode preserving the analysis result."

### 💡 Optional

1. **Named-cell count "~22" vs actual 24** — The brief's own list totals 24
   (3 metadata + 9 clinical + 12 secondary) but says "~22" (lines 30, 41).
   Proposal carries "~22" forward. The "~" covers the discrepancy; reconciling
   would improve precision. Non-blocking.

---

**Verdict**: Ready to freeze (0 🔴 outstanding). All 4 🟡 notes applied as
improvements before freezing. 💡 reconciled to "~24".

---

## design Round 1 — 2026-06-16

Batch: design.md only (proposal.md is frozen)
Baseline: proposal.md (frozen) + explore-brief.md (reference)

### 🔴 Fixed
(none — first review of this batch)

### 🟡 Addressed
(none — first review of this batch)

### 🔴 Outstanding
(none)

### 🟡 Notes

1. **D4 — per-image named cells introduce an undeclared contract surface**
   Design added `img_*` prefixed named cells per image without basis in
   proposal/brief. Either remove (use positional header-based tables in
   per-image sheets) or enumerate the per-image schema and flag for MyQA.
2. **D6 — "cheap re-instantiation" contradicts Risk [Network share latency]**
   If first-load is 5-30s, re-instantiation on cache miss is also 5-30s.
   Fix: hold WL object in `st.session_state["wl_obj"]` for Advanced session.
3. **D6 cache key vs Risks — internal inconsistency**
   D6 signature omits (dicom_file_count, runfolder_mtime) that Risks section
   requires for stale-cache mitigation.
4. **D6 cache key drops `machine`**
   Diverges from brief; collision risk if two machines share a runfolder name.
   Either add `machine_id`, or note runfolder_path encodes machine via
   dicom_root prefix (latter is cleaner).
5. **D6 `references` decomposition unverified against pylinac API**
   Verify pylinac ≥3.45 `WinstonLutz.analyze()` signature — design assumes
   3 separate scalars (`gantry_reference`, `collimator_reference`,
   `couch_reference`).
6. **WL object lifecycle in Advanced mode unspecified**
   Need D6 addendum: session_state schema (`wl_obj`, `wl_params`, `wl_result`),
   lifecycle (lazy init on first Advanced render, invalidated on re-run).
7. **`WLAnalysisResult` dataclass fields not enumerated**
   Implementer doesn't know which fields feed which Advanced tab.

### 💡 Optional

1. **Proposal internal inconsistency** — line 10 says "~24", line 22 says "~22".
   Frozen. Design picked 24 (matches brief's enumerated list). ✅
2. **`st.dialog` (D7) requires Streamlit ≥1.33** — pin in `pyproject.toml`.
   Also `st.dataframe` row-click is not a native primitive; may need
   `st.button` per row.
3. **Excel sheet name sanitisation** — also forbid `\ / ? * [ ] :` chars;
   pylinac keys are safe but defensive sanitisation is cheap.
4. **Caddyfile `respond 403`** — consider `respond "Forbidden" 403`.
5. **D7 typo** — same `st.pyplot(wl.images[i].plot())` shown twice; second
   should be the dialog/scoped version.

---

**Verdict**: Ready to freeze (0 🔴 outstanding). All 7 🟡 notes applied as
improvements before freezing. Relevant 💡 notes (1.33 pin, sheet sanitisation,
Caddyfile body, D7 typo) also applied.

---

## specs Round 1 — 2026-06-16

Batch: specs/ (5 files; proposal.md + design.md are frozen)
Baseline: proposal.md (frozen) + design.md (frozen) + explore-brief.md (reference)

### 🔴 Fixed
(none — first review of this batch)

### 🟡 Addressed
(none — first review of this batch)

### 🔴 Outstanding

1. **`couch_3d_iso` in `wl-advanced-mode` does not exist in the named-cells contract**
   Every other source (brief, design D4, wl-result-export) uses `couch_2d_iso`.
   Single-line typo in wl-advanced-mode/spec.md line 33.

### 🟡 Notes

1. Re-run button + `@st.cache_data` interaction self-contradictory (cache
   short-circuits vs analysis "runs anyway").
2. Per-image sheet source ambiguous: spec says `image_details`, design/proposal
   say `keyed_image_details`; sheet names vs contents source unclear.
3. `analysis_defaults.winston_lutz` required keys: machine-config lists 3,
   advanced sidebar uses 9, simple-mode implies all 9 required.
4. Non-root `appuser` + root-owned bind mounts = startup permission failure.
5. `output.root` existence/writability not validated at startup.
6. Pass/fail extended to 5 metrics beyond design D7's single `max_2d_cax_to_bb`.

### 💡 Optional

1. Success card scenario only asserts one metric (suggest all three).
2. Caddy `depends_on: streamlit` (design has it; spec doesn't mention).
3. OIDC escalation block in spec but not in design's Caddyfile example.
4. `streamlit>=1.33` is a lower bound, not a "pin" (wording imprecision).
5. Logging destination unspecified (suggest stdout for `docker logs`).
6. `machine_scale` enum "etc." is unbounded — consult pylinac's enum.

---

**Verdict**: NOT ready to freeze. 1 🔴 (`couch_3d_iso` typo). Applying 🔴 + all
6 🟡 before Round 2.

---

## specs Round 2 — 2026-06-16

Batch: specs/ (5 files; proposal.md + design.md are frozen)
Baseline: proposal.md (frozen) + design.md (frozen) + explore-brief.md (reference)

### 🔴 Fixed

1. **`couch_3d_iso` → `couch_2d_iso`** (wl-advanced-mode) — verified grep-clean
   across all spec files; matches named-cells contract in wl-result-export and
   design D4.

### 🟡 Addressed

1. Re-run cache semantics clarified (cache short-circuits on identical inputs).
2. Per-image sheet source: parallel-array semantics (`image_keys[i]` → title,
   `image_details[i]` → contents).
3. Config required/optional split: `bb_size_mm`, `machine_scale`,
   `tolerance_mm` required; 6 other pylinac params optional with fallback.
4. Bind-mount UID 1000 ownership requirement + scenario added.
5. `output.root` startup writability probe added.
6. Pass/fail scoped to `max_2d_cax_to_bb` only (matches design D7).

### 🔴 Outstanding
(none)

### 🟡 Notes (all applied as declarative fixes)

1. wl-simple-mode success-card prose scoped pass/fail to `max_2d_cax_to_bb`;
   scenarios renamed "Primary metric passes/fails".
2. wl-advanced-mode re-run requirement qualified with `@st.cache_data` gating.
3. wl-result-export truncation example fixed (was 33 chars, now 31).

---

**Verdict**: Ready to freeze (0 🔴 outstanding). All Round 1 🔴 + 🟡 resolved.
Three Round 2 prose-level 🟡 applied as declarative fixes. Specs are now
internally consistent and form a coherent test contract.

---

## tasks Round 1 — 2026-06-16

Batch: tasks.md (proposal.md, design.md, all 5 specs are frozen)
Baseline: all previously frozen artifacts + explore-brief.md (reference)

### 🔴 Fixed
(none — first review)

### 🟡 Addressed
(none — first review)

### 🔴 Outstanding
(none)

### 🟡 Notes (all applied as declarative amendments)

1. **No task wires startup validation into `app.py`** — add a task to call
   `load_config` + template validation + output probe at startup, guarded
   to run once per script invocation. Highest-impact gap: 4 "refuses to
   start" spec scenarios across 3 specs would silently not fire.
2. **No task implements Fry meme rendering with graceful fallback** — add
   `render_asset(path, placeholder_msg)` UI utility for machine-config R5.
3. **Task 3.4 likely exceeds 2-hour granularity** — split into 3.4a (pylinac
   wrapper + summary dict) and 3.4b (Plotly-ready array precomputation).
4. **Empty-machines banner scenario untested** — add to 6.1 scope.
5. **Docker integration test omits non-root/readonly/permission scenarios**
   — fold into 9.5 or defer to 12.2 cross-reference.
6. **Cross-group dependency: 2.3/2.4 ↔ 5.1** — reorder 5.1 into Group 2
   since the validator's happy-path test depends on the template existing.
7. **7.5 (overlay) should come after 7.6 (lazy wl_obj init)** — note ordering.
8. **3.1 "identity fields" underspecified** — enumerate per design D6.
9. **9.5 uses `requests` (undeclared)** — add to dev deps in 1.1 OR use
   `urllib.request`.

---

**Verdict**: Ready to freeze (0 🔴 outstanding). All 9 🟡 notes applied as
declarative amendments: reordered 5.1 into Group 2, added 1.7 (app.py
startup wiring), split 3.4 into 3.4a/3.4b, added 6.0 (Fry meme render),
added empty-machines case to 6.1, folded Docker scenarios into 9.5,
specified identity fields in 3.1, noted 7.6→7.5 ordering, added `requests`
to dev deps in 1.1.

All four OpenSpec artifacts (proposal, design, specs, tasks) are now frozen.
Change `add-winston-lutz-gui` is ready for `/opsx-apply`.
