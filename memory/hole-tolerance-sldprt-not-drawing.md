---
name: hole-tolerance-sldprt-not-drawing
description: "Hole/feature tolerances live on the PART hole-wizard dimension (or the DRILLED HOLES title-block row), NEVER a drawing dimension or a note. Setting IDimensionTolerance on a DRAWING dim is inert-but-passing (SetValues returns True, GetMaxValue2 reads it back, callout still renders bare nominal). Drilled holes govern via a unilateral title-block row (TOL_HOLE_MINUS/PLUS, +0.10/0 UOS)."
metadata:
  type: project
---

How this project tolerances holes (settled 2026-07-17, PR #334). Pairs with the
policy: only a few CRITICAL features carry explicit callouts, the general block
governs everything else (`cad/docs/tolerance-policy.md` §Scope; ASME Y14.5 §1.4(a)).

- **The drawing hole callout DISPLAYS the part's tolerance; it does not own one.**
  Set the fit on the PART hole-wizard feature. `_holes._tolerance_hole_diameter`
  tolerances the wizard hole's `"Thru Hole Dia."` display dimension — found BY
  NAME (the feature also carries `"Thru Hole Depth"`; toleranceing whichever came
  first would be silently wrong) — via `IDimension.Tolerance` →
  `IDimensionTolerance` (`Type = swTolBILAT = 2`, `SetValues` in **METERS**).
- **TRAP — drawing-dim tolerance is INERT-BUT-PASSING** (render-verified, and the
  failure Pedro diagnosed: *"not rendering because it is not set in the sldprt as
  it should"*). Setting `IDimensionTolerance` on the DRAWING dimension: `SetValues`
  returns True, `GetMaxValue2` reads the value straight back — and the native
  callout still renders the bare nominal (`Ø3.05`). Every signal says success
  except the ink. A print that looks specified and is not is worse than no attempt.
  Verify hole tolerances on the RENDER, never the exit code.
- **DEFAULT PATH for drilled holes = the DRILLED HOLES title-block row, not
  per-feature callouts.** `title_block.yaml` `drilled_hole: {minus_mm, plus_mm,
  display_minus, display_plus}` → `_common.part_properties` stamps
  `TOL_HOLE_MINUS`/`TOL_HOLE_PLUS` on EVERY part (like `TOL_LIN_XX`) → the DRWDOT
  title-block row reads them via `$PRPSHEET`, composed PLUS then MINUS →
  **`+0.10 / 0`**. It is UNILATERAL (hard-zero minus): a twist drill cuts
  on-size-to-oversize and never under, and a clearance hole must never come out
  under its fastener. Required in
  `_drawing_common.TITLE_BLOCK_TOLERANCE_PROPERTIES`, so `finalize_drawing` fails
  loud on a stale part with a blank row (the invariant is "the row must not ship
  blank", not "every hole needs a callout").
- **Per-feature callout is the EXCEPTION HOOK only** — `_holes.wizard_holes(...,
  dia_tolerance_mm=(minus,plus))` — for a hole needing TIGHTER than the general
  row (a close-fit LOCATION hole where +0.10 slop is too much). Nothing needs it
  today; every clearance hole (close and normal) rides the row. The hard-fail
  guard that once forced callouts (`clearance_hole_needs_a_callout` /
  `_block_tolerance_mm`) was REMOVED when the row landed — its premise, that holes
  fall to the symmetric `±0.51` linear block, became false.
- **Standards.** ASME Y14.5 §1.4(a): a general note / supplementary block may
  carry a feature CLASS's tolerance, and it may be unilateral — so the DRILLED
  HOLES row is standard, not a workaround (eng-tips 113720 quotes it; real shops
  carry a drilled-hole block distinct from the .XX/.XXX rows). §2.3.2: a nil
  unilateral limit is a single **`0`**, no sign, no decimals (NOT `-0.00`, not
  `-0`). Upper deviation first, so the row reads `+0.10 / 0`.
- **SW-native hole tolerance vocabulary** (all on the PART or the callout, never a
  note): `swTolMIN`/`swTolMAX` (unilateral single-limit), `swTolFIT` +
  `IDimensionTolerance.GetHoleFitValue`/`FitType` (ISO H-class, inherently
  unilateral for a hole), `swTolBILAT`. Modern path is `IDimension.Tolerance` →
  `IDimensionTolerance`; the older `IDimension.SetToleranceType/SetToleranceValues`
  are marked Obsolete. `SetValues` is METERS.

Links: [[dimxpert-block-tolerance]] (the parallel TOL_LIN_* / DimXpert plumbing),
[[hole-wizard-com-recipe]], [[drawing-text-leader-style]].
