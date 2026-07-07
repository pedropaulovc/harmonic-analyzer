---
name: paper-drive-real-train
description: Final paper-drive topology (PR #196) — six-gear train, Appendix C #8 closed, small-pinion gap-floor rule
metadata:
  type: project
---

# Paper-drive real train (2026-07-07, PR #196)

The paper-drive was rebuilt against the primary references
(docs/paper-drive-rework.md is the evidence doc). Durable facts:

- **Topology (final):** crank T12 —chain→ knob T24 —lock→ 12T DP38 third gear
  —gear 12:120→ 120T DP38 reducer disc —lock→ 12T DP30 feed pinion
  —rack-pinion π·10.16/rev→ teeth-down rack —lock→ platen. Net 1.596
  mm/crank-rev (T12/T24 mounted). The disc NEVER meshes the rack (the old
  96T-DP30 `rack-pinion` role was refuted by the rack/disc pitch ratio ≈1.27
  on ch30 p002 and the 4/4 narration).
- **Appendix C #8 CLOSED:** the "one arm, two centre distances" riddle
  (66.05 rest vs 51.0 engaged) was an artefact of the wrong topology. The
  latch arm pivots ON the stud; its single c2c 44.766 IS the permanent
  12T:120T mesh. Unlatching tilts the WHOLE cluster away from the rack
  (v4_transgear 001 vs 011-013). Don't resurrect the 66.05 figure.
- **Small-pinion gap-floor rule (`_gear.build_fixed_gear`):** the recipe cuts
  tooth gaps only down to the BASE circle, so any pinion under ~63T (PA
  14.5°) has its gap floor ABOVE where the mate's tips reach at nominal
  centres → extend centres like the drive-train's checker-arbitrated slacks
  (12:120 mesh +0.65; feed-pinion/rack axis 0.8 below nominal). Also a 12T
  gear's base/root sits under a 3/8" bore's wall → both 12T gears bore Ø5 on
  turned-down seats (stud + knob shaft are stepped).
- **One support bar** (22×9×452, y-centre 338.5): the platen HANGS on it via
  back guide rails + lock plates; the bar is MACHINE-handed (asymmetric
  bracket holes) and placed `mirror=False`. Two-piece clamp arcs use
  `mirror_plane: z`.
- **Platen is CENTRED (x ±150)** between the columns — the clamp screw heads
  protrude in front of the bar, so the old x −258..+42 offset would collide.
- **All platen-riding fasteners must be lock-mated to the platen** (grounded
  screws float in space when the platen feeds — the original issue-5 bug).
- **Two interference-gate fixes are load-bearing geometry, not whitelists:**
  the platen counterbores its 10 guide-screw stations Ø6.5×2.4 (heads 0.2
  sub-flush so the 0.5-thick paper lies flat; shanks thread 2.4 into blind Ø3
  holes on the rails), and the transgear bracket carries a 1.5-deep full-width
  front groove at stud-local y 16..24 (the bottom guide rail slides 1.0 past
  the bar-back plane and would otherwise sweep the plate). Don't "simplify"
  either away.
- Chain z-stack straddles the 2.4-wide sprockets (inner plate inner faces
  ±1.45); knob centre (54.575, 284.1332) pre-mirror is duplicated as a
  literal in `_chain.KNOB_CENTRE` (leaf-safety) and pinned by
  `_assert_chain_layout` with 1e-3 tolerance.

**Why:** future sessions must not "fix" the model back toward the old
rest-gap/NET-coupling topology or reuse superseded anchors (stud (0, 253.5),
knob (65, 241.78), rails y 440/334, 96T disc).

**How to apply:** when touching paper-drive geometry, derive from
`build_paper_drive_assembly.py` constants (STUD_XY, KNOB_SHAFT_XY, DISC_Z0)
and keep `_chain.KNOB_CENTRE` in lockstep. Related: [[belt-chain-feature]],
[[paper-drive-kinematic-probe]], [[default-free-dof-park-drivers]].
