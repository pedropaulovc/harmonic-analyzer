---
name: drawing-fleet-cost-profile
description: Measured per-span cost breakdown of a drawing build — where the ~32 s median actually goes, and which of it is validation that must not be deleted for speed
metadata:
  type: project
---

Per-span breakdown of the drawing fleet, from the `drawing.*` spans added in
#437. Source: nine COMPLETE 93-drawing passes, 2026-07-27/28 (`⟩ <span> <secs>s`
console lines), median across passes of each span's per-pass total.

**Spans that predate #437 — nine passes, trustworthy:**

| span | s/pass | what it is |
|---|---:|---|
| `drawing.build` | 3579–3730 | the whole fleet's recipe bodies |
| `drawing.layout_audit` | 411–414 | `check_drawing_layout`, BEFORE the save |
| `drawing.isolate_balloon_components` | ~350 | drive-train only; deleted by #442 |
| `drawing.normalize_edge_break` | ~190 | rewrite one template note, per drawing |

**Spans added by #437 — only THREE passes, and NOT well determined:**

| span | range across the 3 passes |
|---|---|
| `drawing.finalize` | 1054 – 1418 |
| `drawing.new_from_template` | 373 – 523 |
| `drawing.save_and_export_pdf` | 323 – 391 |
| `drawing.reopen` | **198 – 400** |
| `drawing.curate_dimensions` | 183 – 264 |
| `drawing.render_png` | 26 – 31 |

Quote these as RANGES, never as a median. `drawing.reopen` spans a 2× spread
across three passes — that is the fleet drift in
[[drawing-fleet-timings-drift]] (−30% to +21% with no code change), not a
measurement. Two of the three passes also contain a crash-retried drawing,
whose pre-crash spans are emitted once by the failed attempt and again by the
retry; measured against the nine-pass spans that double-count is ≤4%, but with
n=3 it cannot be separated from the drift.

`drawing.finalize` is NOT fully accounted by its traced children: subtracting
them **within each pass** leaves 100–128 s/pass in `sanitize_pdf_metadata`, the
post-reopen `assert_asme_b_sheet`, and the property-link validation.

**The two validations prove DIFFERENT things — do not conflate them.**
`check_drawing_layout` runs *before* `save_drawing`, so it proves the authored
in-memory layout (overlaps, border crossings, leader crossings). The reopen and
its `assert_asme_b_sheet` run *after*, so they prove the PERSISTED file kept its
sheet scale and format. Neither substitutes for the other.

**Why:** the reassessment of #382/#384/#389/#407 proposed deleting the reopen,
the layout audit and the edge-break normalizer together as "runtime normalizers"
— on the order of 600–1000 s/pass. This profile says two of those three are
*validation*, not normalization, and as the section above shows they prove
different things: the audit proves the authored layout, the reopen proves the
persisted file (#436 deliberately kept the reopen and deleted only its repair
half). Deleting both removes the only proof a drawing is correct, for a saving
whose own measurement spans 2× — a reliability-for-speed trade that is
explicitly out of bounds here, at any of those numbers.
Only `drawing.normalize_edge_break` (~190 s/pass) is pure normalization, and it is
removable only after the note is baked into `harmonic-analyzer.DRWDOT` — the fix
#382 attempted and botched by regressing the template binary.

**How to apply:** treat a proposed drawing-pipeline deletion as needing this
question answered first — *is this span normalizing, or proving?* Regenerate the
profile by parsing `⟩ <name> <secs>s` out of every pass log, summing per span
PER PASS, then taking the median across passes; it costs nothing beyond logs that
already exist. Three traps, all hit once: EXCLUDE incomplete passes (an
in-flight run silently dragged every per-pass total down); do not extrapolate
one pass (that mis-sized `drawing.save_and_export_pdf` by 1.8×); and never
compare a parent to the SUM OF ITS CHILDREN'S MEDIANS — medians do not add, so
subtract within each pass, which is what exposed finalize's 100–128 s residual.
A single pass also carries ~4 hung-window stalls worth ~3 min
(see [[drawing-fleet-crash-rate]]). Do not compare two runs' wall clock to judge
a change —
see [[drawing-fleet-timings-drift]]. Related: [[checks-perf-value-audit]],
[[release-perf-incremental]].

**Open, unmeasured:** each recipe's `open_model(SOURCE)` costs ~3 s (`open
<part> source`) and exists *only* to feed
`read_required_properties(adapter.currentModel, …)` before any view exists —
views are placed by path, and `finalize_drawing` already reads the same kind of
property off `first_view.ReferencedDocument`. Whether deferring the read
actually saves that ~3 s, or merely moves the load into the first
`CreateDrawViewFromModelView3`, is unknown; #388 claimed ~1.5 s/drawing without
a control. Measure one part both ways before touching 88 call sites —
[[load-bearing-claims-need-repro]].
