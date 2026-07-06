---
name: paper-drive-kinematic-probe
description: Paper-drive crank→feed kinematic probe — chain coupling is a GEAR MATE (12:24=0.5), NOT the belt feature (0.538 tip-dia bug); knob-shaft spin axis ⊥ sprockets
metadata:
  type: project
---

`cad/scripts/build_kinematic_probe.py` (added for codex #189, PR chain-component-pattern)
drives the crank +30° on the built `paper-drive.SLDASM` and reads the whole feed train
back. Two non-obvious findings that will trip up anyone reasoning about this model:

1. **The crank→T24 coupling is a GEAR MATE at the exact 12:24 tooth ratio — NOT the SW
   Belt/Chain feature.** The belt feature was tried first and REJECTED (codex #189 round-5,
   commit 35efcffa): `EngageBelt` derives its coupling-mate ratio from the wrapped
   OUTSIDE-cylinder faces it selects — for these module-2 gears that is the tip cylinder
   (dia 28:52 = **0.538**), and it SILENTLY IGNORES the `pulley_diameters=[24,48]` we set
   to the pitch diameters. A roller chain enforces the tooth/pitch ratio (one link per
   tooth → 12:24 = **0.500**), so 0.538 was a ~7.7% feed error baked into the shipped
   model. Fix: a plain `gear_mate(Axis1@t12, Axis1@t24, ratio=[PITCH_R_T12, PITCH_R_T24])`
   on the two sprocket spin axes (the conventional way to model a chain tie). The
   roller-chain COMPONENT PATTERN (the visual) is untouched — only the kinematic coupling
   changed. Validated: crank 30.0° → T24 **15.00°** (ratio **0.500**), shaft/pinion follow,
   platen +2.66 mm. The probe now asserts 0.500 ± 0.03 TIGHTLY. Everything downstream of
   T24 was always exact (rack-pinion faithful). NOTE the probe is MAGNITUDE-only, so it
   validates the 0.5 ratio but NOT the rotation SENSE (same-vs-opposite) — gear mate sense
   is `alignment`-dependent and unasserted, same parity as the old belt state. See
   [[belt-chain-feature-com-binding]] (the feature still WORKS, we just don't use it here).

2. **The knob shaft's modeled spin axis is PERPENDICULAR to the sprockets'.** T24 and the
   fine pinion spin about global Z; the `transgear-knob-shaft` (placed `ROT_X_POS90`,
   `ground=False`, Lock-mated to T24) turns about global **Y** — same magnitude, different
   axis. So any readback that projects rotation onto a shared/crank axis reads a FALSE ZERO
   for the shaft (this bit the first probe). Compare rotation by MAGNITUDE (axis-angle
   angle via `acos((trace−1)/2)`), never by axis projection. The Lock mates still couple
   all three (:592) — the cluster follows the crank; the perpendicular axis is a
   modeling-frame artifact, not a broken mate.

The probe never saves (drives + reads, then discards via `preflight_release._discard_open_documents`
in a `finally`). It is a NON_PART_SCRIPT (diagnostic, like `build_mobility_probe.py`), run
by hand; its assertions are ALSO wired into `verify:kinematics` via
`verify._verify_paper_feed_one` (skipped for a `locked` build — no free crank DOF to drive).
See [[default-free-dof-park-drivers]] and [[chain-component-pattern]].
