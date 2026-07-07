---
name: paper-drive-kinematic-probe
description: Paper-drive crank→feed kinematic probe — coupling is the Belt/Chain feature with AXIS pulley members (0.500, same-sense; face members bake the tip ratio 0.538); knob-shaft spin axis ⊥ sprockets (magnitude-compare only)
metadata:
  type: project
---

`cad/scripts/build_kinematic_probe.py` (PR #189) drives the crank +30° on the built
`paper-drive.SLDASM` and reads the whole feed train back; `verify:kinematics` runs
its `_drive_and_measure` as the `paper-drive:crank-feed` gate. Findings that will
trip up anyone reasoning about this model:

1. **The crank→T24 coupling is the SW Belt/Chain feature with DATUM-AXIS pulley
   members and typed pitch diameters (24/48 → ratio 12:24 = 0.500), same-sense.**
   Two wrong turns are baked into this: round-5 replaced the belt with a gear
   mate after concluding "EngageBelt ignores pulley_diameters" (wrong — the
   getters read [] until `AccessSelections`; and a gear mate REVERSES rotation
   while a chain turns both sprockets the SAME way — a fidelity bug the
   magnitude-only probe couldn't see). The follow-up "enforce PulleyDiameters
   post-create via ModifyDefinition" ALSO turned out wrong: the definition read
   back green while the coupling mate kept the picked faces' tip diameters
   (0.538) — with FACE members no definition-level route touches the mate. AXIS
   members give the mate no face to steal from, so the typed diameters drive it
   exactly (measured +0.5000 live; see [[belt-chain-feature-com-binding]]). The
   probe asserts BOTH: ratio 0.500 ± 0.03 (tip-face 0.538 fails it) AND same
   sign of the two sprockets' SIGNED Z rotations.

2. **The knob shaft's modeled spin axis is PERPENDICULAR to the sprockets'.** T24
   and the fine pinion spin about global Z; the `transgear-knob-shaft` (placed
   `ROT_X_POS90`, Lock-mated to T24) turns about global **Y** — same magnitude,
   different axis. Any readback that projects rotation onto a shared axis reads a
   FALSE ZERO for the shaft (bit the first probe). Compare cluster rotations by
   MAGNITUDE (axis-angle via `acos((trace−1)/2)`); the signed-Z compare is valid
   ONLY for the two sprockets (both on global Z).

3. **Scratch-assembly angle drivers are unreliable** — in the minimal two-sprocket
   probe (`probe_belt_diameter.py`) the same temp angle driver fails IN PLACE
   (hard error 1, both flips) from parallel AND 15°-off-apex rest poses, while it
   drives the FULL paper-drive model fine. Root cause unisolated
   ([[park-driver-singularities]]); measure coupling ratios on the real model.

4. **`FEED_SIGN` is PINNED physics (+1), not a calibration knob** (2026-07-07,
   PR #196). The original rack-pinion mate passed every magnitude check while
   feeding the paper BACKWARD (user drag test). Since then: the mate rides the
   RACK's own pitch-line `Axis1` (not the platen's slide axis) with
   `flip=True` — calibrated live (flip=False measured platen +0.133 mm for feed
   Z −1.50°; physics demands −0.133). If the `paper-drive:crank-feed` gate ever
   fails on sign, flip the MATE in `build_paper_drive_assembly.py`; never
   re-sign the probe constants. The end-to-end NET assert is signed through the
   whole train, so a reversal can't hide behind a retuned pairwise constant.

The probe never saves (drives + reads, then discards via
`preflight_release._discard_open_documents` in a `finally`). NON_PART_SCRIPT,
run by hand or via `verify:kinematics` (skipped for a `locked` build — no free
crank DOF to drive). See [[default-free-dof-park-drivers]] and
[[chain-component-pattern]].
