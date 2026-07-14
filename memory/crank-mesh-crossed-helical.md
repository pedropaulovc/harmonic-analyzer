---
name: crank-mesh-crossed-helical
description: 16T:64T crank mesh is a crossed-axis pair — engaged via a TRUE-helix 64T (swept teeth) + 0.15 backlash + root relief, proud-of-casting placement; crossed_mesh_study.py is the repro/gate
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

**Shipped solution (2026-07-14, PR #292):** the 64T's teeth are a TRUE
12.5182° helix (gear helix = shaft angle → crossed-helical pair with a
straight 16T): ONE involute tooth boss-swept along the axis with constant
twist (`_gear.boss_tooth_swept`, root-cylinder blank, tooth root embedded
0.3 into it) and circular-patterned — smooth helicoid flanks. 0.15 mm
circumferential backlash, root-relieved floors (stock base-chord floor
starves a 16T pinion by 0.71 mm). Engaged C2C = R64+R16+0.25 slack = 38.489
(tips 1.66 mm in, 87% working depth), Y_CRANK 142.985 (GT 1.06σ). This
supersedes the same-day interim K=12 slice-cut stack at 0.40 backlash/0.60
slack: the user flagged visible slop + faceted teeth; the smooth flanks
freed the ~0.2 mm the facets consumed, and the study re-arbitrated the
tighter fit (zero window [−1.90, −1.10]° seed, ±0.4° margins clean — 4× the
0.10° authoring-correction bound). Axially the pinion (face 11) stands
PROUD of the green post's casting face — ch12 page002_img06: NO relief
pocket (the img02 "pocket" ring is the bearing boss; a pocket-nested edge
placement adopted from a concurrent branch was reverted 2026-07-14 on the
user's read) — centred in the TRUE casting-to-T120 span (PINION_TOOTH_Z
−68.90, face 10.8, 0.32 wall / 0.30 T120-rim clearance, ~94% of the 64T
row; span-fit + engagement-floor asserts in the assembly). NB the T120
bound is the inclined rim's ARC MINIMUM over the whole radial-overlap
region, not the line-of-centres point — at the tight fit the overlap arc
crosses 90° azimuth and the rim dips SOUTH of that estimate (0.67 model
error → a 0.00 mm³ pinion↔T120 graze the interference gate caught
2026-07-14; the assert now scans the arc). The pocket was an artifact of
the straight-tooth era: a narrow engaged band was the only way straight
teeth stayed collision-free, while the helix engages the full row. Helix
HAND matters: +INCLINE zeroes the collision, the mirrored hand collides
~19 mm³ at the tight fit.

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

Two live-caught build traps on this pair (both fixed in PR #292, both
gate-guarded now): (1) [retired-path lesson, kept for any future offset-plane
cut] the K-slice era's k>0 slice cuts sat on offset planes whose blind cut
defaults BACK toward Front; the pre-pattern seeded-tooth/gap volume gate
(±1 mm³) makes a mis-built seed fail loud (see
[[solidworks-modeling-pitfalls]]). (2) CopyWithMates2
cone-keying can wander the free train's spin before the 16T:64T gear mate
freezes the phase — the assembly measures the equivalent seed error, rotates
the cone family back (Rodrigues about the cone axis), and re-anchors the
pose ledger (reledger_to_solved) after the correction. Fast live repro for
any future mesh doubt: `diagnostics/probe_live_crank_mesh.py` (~17 s of
seat, prints patch locations + saves the SW interference picture).
