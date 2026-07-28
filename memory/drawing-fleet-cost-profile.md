---
name: drawing-fleet-cost-profile
description: Measured per-span cost breakdown of a drawing build — where the ~32 s median actually goes, and which of it is validation that must not be deleted for speed
metadata:
  type: project
---

Per-span breakdown of the drawing fleet, from the `drawing.*` spans added in
#437. Source: **826 drawing builds across nine 93-drawing passes** (2026-07-27/28
console logs, `⟩ <span> <secs>s` lines). Figures are the MEDIAN ACROSS PASSES of
each span's per-pass total — not one pass extrapolated, and not a per-drawing
median, which understates the skewed spans badly (`drawing.reopen` reads 2.1 s
median but 4.0 s mean).

| span | s/pass | passes | what it is |
|---|---:|---:|---|
| `drawing.build` | 3579 | 9 | the whole fleet's recipe bodies |
| `drawing.finalize` | 1095 | 3 | save → PDF → reopen → validate |
| `drawing.new_from_template` | 444 | 3 | template instantiation |
| `drawing.layout_audit` | 411 | 9 | `check_drawing_layout` on the reopened doc |
| `drawing.reopen` | 372 | 3 | round-trip the saved artefact |
| `drawing.save_and_export_pdf` | 323 | 3 | |
| `drawing.curate_dimensions` | 236 | 3 | |
| `drawing.normalize_edge_break` | 192 | 9 | rewrite one template note, per drawing |

`drawing.finalize` = reopen + layout_audit + save_and_export_pdf (372 + 411 +
323 = 1106 ≈ 1095), so it is fully accounted and has no hidden cost left in it.
Only the spans with `passes: 9` predate #437; the rest exist only in logs from
#437 onward, which is why their sample is 3 passes.

**Why:** the reassessment of #382/#384/#389/#407 proposed deleting the reopen,
the layout audit and the edge-break normalizer together as "runtime normalizers"
— ~975 s/pass, 27% of the fleet. This profile says two of those three are
*validation*, not normalization: `drawing.reopen` is what makes the saved
artefact prove its own sheet scale and format (deliberately kept by #436, which
deleted only the repair half), and `drawing.layout_audit` runs on that reopened
doc. Deleting them buys 783 s/pass by removing the only proof the persisted file
is correct — a reliability-for-speed trade that is explicitly out of bounds here.
Only `drawing.normalize_edge_break` (192 s/pass) is pure normalization, and it is
removable only after the note is baked into `harmonic-analyzer.DRWDOT` — the fix
#382 attempted and botched by regressing the template binary.

**How to apply:** treat a proposed drawing-pipeline deletion as needing this
question answered first — *is this span normalizing, or proving?* Regenerate the
profile by parsing `⟩ <name> <secs>s` out of every pass log, summing per span
PER PASS, then taking the median across passes; it costs nothing beyond logs that
already exist. Pool across passes rather than extrapolating one — a single pass
carries ~4 hung-window stalls worth ~3 min (see [[drawing-fleet-crash-rate]]),
and extrapolating one pass mis-sized `drawing.save_and_export_pdf` by 1.8×. Do
not compare two runs' wall clock to judge a change —
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
