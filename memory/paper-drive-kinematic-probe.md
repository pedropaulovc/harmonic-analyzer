---
name: paper-drive-kinematic-probe
description: Paper-drive crank→feed kinematic probe — coupling is the Belt/Chain feature at ENFORCED pitch diameters (0.500, same-sense); knob-shaft spin axis ⊥ sprockets (magnitude-compare only)
metadata:
  type: project
---

`cad/scripts/build_kinematic_probe.py` (PR #189) drives the crank +30° on the built
`paper-drive.SLDASM` and reads the whole feed train back; `verify:kinematics` runs
its `_drive_and_measure` as the `paper-drive:crank-feed` gate. Findings that will
trip up anyone reasoning about this model:

1. **The crank→T24 coupling is the SW Belt/Chain feature with PulleyDiameters
   ENFORCED to the pitch values (24/48 → ratio 12:24 = 0.500), same-sense.** Round-5
   briefly replaced it with a gear mate after concluding "EngageBelt ignores
   pulley_diameters" — that conclusion was WRONG (the getters read [] until
   `AccessSelections`, and only the PRE-create set no-ops; post-create
   `ModifyDefinition` re-solves the coupling — see
   [[belt-chain-feature-com-binding]]). The gear mate also had a real fidelity bug
   the magnitude-only probe couldn't see: an external gear mesh REVERSES rotation,
   a chain turns both sprockets the SAME way. The probe now asserts BOTH: ratio
   0.500 ± 0.03 (tip-face 0.538 fails it) AND same sign of the two sprockets'
   SIGNED Z rotations.

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

The probe never saves (drives + reads, then discards via
`preflight_release._discard_open_documents` in a `finally`). NON_PART_SCRIPT,
run by hand or via `verify:kinematics` (skipped for a `locked` build — no free
crank DOF to drive). See [[default-free-dof-park-drivers]] and
[[chain-component-pattern]].
