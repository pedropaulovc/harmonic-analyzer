---
name: channel-bar-station-driven
description: PR #458 — amplitude-bar station is DRIVEN via a foot-pin (J5 arc radius + J6 station chord), NOT freed and NOT a rocker↔bar angle; the angle form transmitted rocker rotation 1:1 into the bar at neutral; drag solver provably slides any free station; cam-follower mate not COM-authorable; IDragOperator drag ≠ mate re-solve
metadata:
  type: project
---

**Decision (2026-08-01, PR #458, two iterations):** the channel amplitude-bar
STATION (Fourier coefficient a_j) is **driven, not freed** — but the driven
coordinate must be the **material contact point**, not the rocker↔bar angle.
Each channel pins the bar's FOOT AXIS with two distance mates: **J5
foot-on-arc** (`Axis2@bar` ↔ arc-centre `Axis3@rocker` = `BAR_TANGENT_DISTANCE`)
+ **`J6-station-chNN` station chord** (`Axis2@bar` ↔ rod-pin `Axis2@rocker`,
value = the solve's foot↔rod-pin chord). The rod pin sits at +132.76, BEYOND
the +88 mm arc end, so the unsigned chord is monotone across the whole ±88 span
— measuring from the mid Right Plane would fold ± stations (the v0
bidirectional bug). Channel freed DOF stay **2 per channel** (rocker + rod, 40
specs at 20 channels); bar + lever are coupled through the foot pin.
Repositioning = edit `D1@J6-station-chNN` (in mm; gates ramp it) or suppress
J6 (the physical "lift against friction"; J5 stays, so the freed bar slides
ALONG the arc like the real shove). Copies inherit J5+J6 verbatim
(same-amplitude seeds); their mates keep AUTO names, so classifiers pick a
bar's station as the SMALLER of its two rocker↔bar distance values
(unit-independent; J5 ≈ 802 mm, J6 ≤ ~221 mm).

**Why the angle mate was wrong (user repro #2):** a hard rocker↔bar ANGLE mate
holds the RELATIVE orientation, so a rocker stroke θ forces the bar to tilt θ
at EVERY station — at the a_j=0 neutral the bar visibly tilted and walked
(~6 mm + full θ per 5° stroke) when physically zero amplitude transmits ZERO
output (the neutral contact point sits ~16 mm above the rocker pivot and
barely moves; the bar's orientation belongs to its HANG from the lever).
Friction pins WHERE the notch grips (the material point), never the bar's
tilt. Gate: `chain:channel:bar-neutral-isolation` (bar tilt ≤ 0.5°, foot walk
≤ 2.5 mm, lever-end ≤ 1.5 mm over a ±5° stroke). The tandem gates are
expressed as **foot-in-rocker-frame pinned** (edge slide ≤ 0.5 mm), NOT
angle-constancy — the relative angle legitimately changes by ~θ during a
stroke. Contact checks are RADIAL distances to the arc centre, not
projections onto the bar axis (a projection reads a spurious cos(tilt) error
the moment the rocker tilts under the hanging bar).

**Why driven at all (user repro #1):** live evidence (probe_drag_station /
probe_cam_station, diagnostics/):
- The **Move Components drag solver (IDragOperator) is a DIFFERENT solver from
  the mate re-solve**: a transient-drive rocker stroke held a free station to
  0.06° while the same stroke via drag slid it 1:1 (mode 0/2) or worse (mode
  1). A kinematic gate about MANUAL behaviour must use the drag path
  (`_assembly.drag_rotate_component`; gate `chain:channel:bar-station-drag`).
- Every free-station contact representation slides: plane-tangent,
  foot-on-circle, face-tangent. No mate expresses friction.
- **Cam-follower mate (swMateCAMFOLLOWER=9) was not COM-authorable** through
  the stock adapter: the 2026 typelib mistypes `SetEntitiesToMate` as bare
  `(9,1)` VT_DISPATCH on exactly {ICamFollowerMateFeatureData,
  IRackPinionMateFeatureData} (hinge uses `(12,1)` VT_VARIANT — the working
  convention). Fixed by typelib fixup in SolidworksMCP-python PR #96; even
  authorable, the cam family constrains tangency, not arc position, so it
  cannot hold a station (pending live drag measurement).

**Drag-solver calibration:** mode 0 (rigid) carries the coupled chain full
stroke; mode 2 (relaxation) converges only ~0.1°/step regardless of step size
— per-mode min-motion floors {0: 2.0, 1: 0.1, 2: 0.1} deg, don't read slow
convergence as "frozen DOF".

**Consequences wired in:** `verify._expected_free_dof` channel =
2×active_count; bar+lever stay in `_REQUIRED_FREE_STEMS`/`_ALLOWED_FREE_STEMS`;
gates drive the production `D1@J6-station-ch00` in mm (no transient rocker↔bar
drive — it would over-define); the COPY path records only rocker/rod specs;
`build_motion_setup_drives._drive_p0` and `build_mobility_probe` suppress the
smaller-value rocker↔bar distance (the chord). AGENTS.md "Default-free DOF"
updated.

Related: [[default-free-dof-park-drivers]], [[mate-flip-determinism]],
[[cwm-free-dof-by-design]], [[verify-assumptions-live-sw]],
[[negative-result-needs-positive-control]].
