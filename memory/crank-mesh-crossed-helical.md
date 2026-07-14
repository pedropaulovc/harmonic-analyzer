---
name: crank-mesh-crossed-helical
description: 16T:64T crank mesh is a crossed-axis pair — engaged via linearized-helix 64T + backlash + root relief at the south-edge photo placement; crossed_mesh_study.py is the repro/gate
metadata:
  type: project
---

The crank-pinion (16T) : crank-drive-gear (64T) mesh crosses axes: the 64T
rides the cone shaft (inclined 12.5182° in plan, SIN_I 0.21675010133293013)
while the crankshaft is machine-Z (ch30 GT triangulation pins the axle at the
pedestal x at both z-stations; a cone-parallel crankshaft is 20+σ off).
Straight uniform teeth CANNOT engage across that crossing at any radial
depth — the crossing manifests as lateral flank misregistration (±1.08 mm
across the face vs ≤0.70 mm clearance), so the pre-2026-07-14 "fix" (PEN16
radial backoff) just parked the tip circles 0.29 mm apart: a literal air gap.

**Shipped solution (2026-07-14, PR #292):** the 64T is cut as a linearized
12.5182° helix (gear helix = shaft angle → crossed-helical pair with a
straight 16T), K=12 stacked rotated slice cuts, 0.40 mm circumferential
backlash, root-relieved gap floors (stock base-chord floor starves a 16T
pinion by 0.71 mm). Engaged C2C = R64+R16+0.60 slack = 38.839 (tips 1.31 mm
in, 69% working depth), Y_CRANK 143.34 (GT 0.85σ). Axially the pinion
(face 11) stands PROUD of the green post's casting face — ch12
page002_img06: NO relief pocket (the img02 "pocket" ring is the bearing
boss; a pocket-nested edge placement adopted from a concurrent branch was
reverted 2026-07-14 on the user's read) — centred in the static
casting-to-T120 span (PINION_TOOTH_Z −68.57, ~0.55 clearance each side,
~96% of the 64T row; span-fit + engagement-floor asserts in the assembly).
The pocket was an artifact of the straight-tooth era: a narrow engaged band
was the only way straight teeth stayed collision-free, while the helix
engages the full row. Helix HAND matters: +INCLINE zeroes the collision,
the mirrored hand collides ~9 mm³.

**Why:** the mesh geometry is the harder constraint than raw GT residuals —
the old Y_CRANK 144.96 matched GT at 0.13σ only by not meshing.

**How to apply:** never re-tune this pair with radial moves. Re-arbitrate any
change (slack, backlash, seed, placement) with
`cad/scripts/diagnostics/crossed_mesh_study.py` — SolidWorks-free, imports
the LIVE assembly constants (never mirrored), pins PINION_TOOTH_Z /
PINION_SEED_DEG / Y_CRANK against build_drive_train_assembly, and PASS/FAILs
on a full crank-pitch phase sweep. The tooth-in-gap seed window shifts ~−1.5°
at tighter slacks (helix twist at the engaged band), so the seed formula must
be re-checked with the study whenever the slack changes. Helix/backlash knobs:
gear_train.crank_drive_backlash_mm / crank_drive_helix_slices; fit class
tolerances.crank_mesh.c2c_slack_mm. See [[ch30-gt-re-anchor]],
[[load-bearing-claims-need-a-repro]].
