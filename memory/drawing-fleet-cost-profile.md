---
name: drawing-fleet-cost-profile
description: Measured per-span cost breakdown of a drawing build — where the ~32 s median actually goes, and which of it is validation that must not be deleted for speed
metadata:
  type: project
---

Per-span breakdown of the drawing fleet, from the `drawing.*` spans added in
#437. Source: **837 drawing builds across nine COMPLETE 93-drawing passes**
(2026-07-27/28 console logs, `⟩ <span> <secs>s` lines). Figures are the MEDIAN
ACROSS PASSES of each span's per-pass total.

| span | s/pass | passes | what it is |
|---|---:|---:|---|
| `drawing.build` | 3730 | 9 | the whole fleet's recipe bodies |
| `drawing.finalize` | 1311 | 3 | audit → save → PDF → reopen → validate |
| `drawing.new_from_template` | 444 | 3 | template instantiation |
| `drawing.layout_audit` | 414 | 9 | `check_drawing_layout`, BEFORE the save |
| `drawing.reopen` | 394 | 3 | round-trip the saved artefact |
| `drawing.save_and_export_pdf` | 337 | 3 | |
| `drawing.curate_dimensions` | 236 | 3 | |
| `drawing.normalize_edge_break` | 192 | 9 | rewrite one template note, per drawing |
| `drawing.render_png` | 28 | 3 | |

`drawing.finalize` is NOT fully accounted: subtracting its four traced children
**within each pass** leaves 100–128 s/pass in `sanitize_pdf_metadata`, the
post-reopen `assert_asme_b_sheet`, and the property-link validation — none of
them spanned. (Only the `passes: 9` spans predate #437; the rest exist only in
logs from #437 on.)

**The two validations prove DIFFERENT things — do not conflate them.**
`check_drawing_layout` runs *before* `save_drawing`, so it proves the authored
in-memory layout (overlaps, border crossings, leader crossings). The reopen and
its `assert_asme_b_sheet` run *after*, so they prove the PERSISTED file kept its
sheet scale and format. Neither substitutes for the other.

**Why:** the reassessment of #382/#384/#389/#407 proposed deleting the reopen,
the layout audit and the edge-break normalizer together as "runtime normalizers"
— ~1000 s/pass, 27% of the fleet. This profile says two of those three are
*validation*, not normalization, and as the section above shows they prove
different things: the audit proves the authored layout, the reopen proves the
persisted file (#436 deliberately kept the reopen and deleted only its repair
half). Deleting both buys 808 s/pass by removing the only proof a drawing is
correct — a reliability-for-speed trade that is explicitly out of bounds here.
Only `drawing.normalize_edge_break` (192 s/pass) is pure normalization, and it is
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
