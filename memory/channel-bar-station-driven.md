---
name: channel-bar-station-driven
description: PR #458 — amplitude-bar station is DRIVEN (J6 rocker↔bar angle mate), not a freed DOF; drag solver provably slides any free station; cam-follower mate not COM-authorable; IDragOperator drag ≠ mate re-solve
metadata:
  type: project
---

**Decision (2026-08-01, PR #458):** the channel amplitude-bar STATION (the Fourier
coefficient a_j) is a **driven dimension**, not a freed operational DOF. Each channel
carries a hard rocker↔bar plane angle mate, ch00's renamed **`J6-station-ch00`**
(`rename_assembly_feature`; copies inherit the seed's mate with auto names). Channel
freed DOF: **2 per channel** (rocker swing + rod follow), manifest = 40 specs at 20
channels. Repositioning = edit the mate dimension (verify gates ramp
`D1@J6-station-ch00`) or suppress it — the physical "lift against friction" act
(book ch.15: the bar's foot notch rides a SMOOTH rocker edge, friction-held,
"satisfying metallic squeak").

**Why:** the user repro — bar at arc end, lower the rocker → bar must lower in
tandem — fails with ANY free-station scheme. Live evidence (probe_drag_station /
probe_cam_station, diagnostics/):
- The **Move Components drag solver (IDragOperator) is a DIFFERENT solver from the
  mate re-solve**: a transient-drive rocker stroke held station to 0.06°, while the
  same stroke via drag slid it 1:1 (mode 0/2) or worse (mode 1: −7.7° on −3°).
  A kinematic gate about MANUAL behaviour must use the drag path
  (`_assembly.drag_rotate_component`; gate `chain:channel:bar-station-drag`).
- Every contact representation slides: shipped plane-tangent (J5), main's
  foot-on-circle (11.3° roll in the PR regression), face-tangent (−3.6/−7.2/−3.0 by
  mode). They differ only in how contact is written; all leave station free and the
  drag solver spends free DOF by its own move-minimisation. No mate expresses friction.
- **Cam-follower mate (swMateCAMFOLLOWER=9) is not COM-authorable here**: the typelib
  puts `ICamFollowerMateFeatureData::SetEntitiesToMate` value as bare `(9,1)`
  VT_DISPATCH — wrapper + raw-Invoke VT_ARRAY|VT_VARIANT / VT_ARRAY|VT_DISPATCH all
  "Type mismatch", single dispatch "succeeds" but stores nothing (readback 0); the
  documented Mark=1/Mark=8 preselect + `CreateMate` throws server-side on a single
  arc face and returns None on the rocker's 6-face outer loop (not
  tangent-continuous, so likely never a valid cam profile). Positive control: a
  TANGENT mate (type 4) authors fine via the identical recipe. Even if authorable,
  it is the same tangency family that measurably slides.

**Drag-solver calibration:** with the chain coupled, IDragOperator mode 0
(maximum/rigid move) carries the whole channel in coarse 0.5° steps with 0.000°
station drift, but mode 2 (relaxation) converges only ~0.1° of each step's
rotation (measured −0.29° from six 0.5° steps) — give relaxation FINE steps
(60×0.05°, like the UI's stream of small updates), don't read slow convergence
as "the DOF is frozen".

**Consequences wired in:** `verify._expected_free_dof` channel = 2×active_count;
bar+lever stay in `_REQUIRED_FREE_STEMS`/`_ALLOWED_FREE_STEMS` (coupled →
under-constrained WITH the free rocker); the contact sweep + drag gate drive the
production `D1@J6-station-ch00` (no transient rocker↔bar angle mate — it would
over-define against J6); the COPY path records only rocker/rod specs (a copied
bar_amplitude spec would replay a second driver onto the driven coordinate);
`build_motion_setup_drives._drive_p0` and `build_mobility_probe` suppress the
two-real J6 (their single-real driver classifiers do NOT see it). AGENTS.md
"Default-free DOF" updated.

Related: [[default-free-dof-park-drivers]], [[mate-flip-determinism]],
[[cwm-free-dof-by-design]], [[verify-assumptions-live-sw]],
[[negative-result-needs-positive-control]].
