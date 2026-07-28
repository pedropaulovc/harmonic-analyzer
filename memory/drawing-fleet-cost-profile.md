---
name: drawing-fleet-cost-profile
description: Measured per-span cost breakdown of a drawing build — where the ~32 s median actually goes, and which of it is validation that must not be deleted for speed
metadata:
  type: project
---

First real per-span breakdown of the drawing fleet, from the `drawing.*` spans
added in #437. Source: the 34 drawings completed in #440's pass-1 console log on
2026-07-28 (`⟩ <span> <secs>s` lines; medians, so the assembly outliers do not
skew them).

| span | median | × 93 | what it is |
|---|---:|---:|---|
| `drawing.build` | 32.2 s | — | the whole recipe body |
| `drawing.finalize` | 12.5 s | — | save → PDF → reopen → validate (39% of build) |
| `drawing.new_from_template` | 5.4 s | 506 s | template instantiation |
| `drawing.reopen` | 4.7 s | 435 s | round-trip the saved artefact |
| `drawing.layout_audit` | 4.3 s | 400 s | `check_drawing_layout` on the reopened doc |
| `drawing.normalize_edge_break` | 2.2 s | 200 s | rewrite one template note, per drawing |
| `drawing.save_and_export_pdf` | 1.9 s | 177 s | |

`drawing.finalize` is ~87% accounted for by reopen + layout_audit +
save_and_export_pdf, so there is no hidden cost left in it to find.

**Why:** the reassessment of #382/#384/#389/#407 proposed deleting the reopen,
the layout audit and the edge-break normalizer together as "runtime normalizers"
— about 1035 s/pass, ~26% of the fleet. This profile says two of those three are
*validation*, not normalization: `drawing.reopen` is what makes the saved
artefact prove its own sheet scale and format (deliberately kept by #436, which
deleted only the repair half), and `drawing.layout_audit` runs on that reopened
doc. Deleting them buys 835 s/pass by removing the only proof the persisted file
is correct — a reliability-for-speed trade that is explicitly out of bounds here.
Only `drawing.normalize_edge_break` (200 s/pass) is pure normalization, and it is
removable only after the note is baked into `harmonic-analyzer.DRWDOT` — the fix
#382 attempted and botched by regressing the template binary.

**How to apply:** treat a proposed drawing-pipeline deletion as needing this
question answered first — *is this span normalizing, or proving?* Regenerate the
profile from any pass-1 log with the one-liner that parses `⟩ <name> <secs>s`
lines and reports median + count per span name; it costs nothing beyond a log
that already exists. Do not compare two runs' wall clock to judge a change —
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
