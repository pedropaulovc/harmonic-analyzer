---
name: drawing-notes-no-title-block-boilerplate
description: "DRAWING_NOTES must not restate title-block content (units 'DIMENSIONS IN MM', UOS clauses, general tolerances) — redundant at best, contradicts the block tolerance at worst; tighter tolerances go ON the dimension"
metadata:
  type: feedback
---

Pedro, 2026-07-21 (during the full-fleet drawing fan-out): "some drawings are
adding redundant info in notes like uos unit mm".

**Why:** the title block already declares units and the general (block)
tolerances (`TOL_LIN_XX`/`TOL_LIN_XXX`/`TOL_ANG` rows — see
[[dimxpert-block-tolerance]]). A per-sheet note like
`"UOS, DIMENSIONS IN MM; ..."` duplicates that, and the worse flavor —
`"UOS, DIMENSIONS IN MM: LENGTH +/-0.25; HOLE CENTRES +/-0.10."`
(crankshaft's first draft) — silently SHADOWS the block tolerances, exactly the
"dims that read as contradictions" defect the blind machinist reviews exist to
catch.

**How to apply:**
- DRAWING_NOTES carry ONLY part-specific facts (process steps, functional fits,
  gear/spring/wire data tables, commercial-equivalent designations).
- Never restate units, UOS clauses, or general tolerances in a note.
- A dimension needing a TIGHTER tolerance than the block gets it ON that
  dimension (`IDimensionTolerance` on the PART model dim — see
  [[hole-tolerance-sldprt-not-drawing]]), never as a blanket note.
- Grep sweep for offenders: `rg -i "UOS|UNLESS OTHERWISE|DIMENSIONS IN MM"
  cad/scripts/*_spec.py`.
