---
name: motion-study-full-device-rework
description: 2026-07-09 full-device operation study rework — the default-free architecture needs ZERO suppression; COM traps (unflagged IComponent2, currentModel overwrite, lightweight docs) and Basic Motion margin lessons (fresh-solve-only attribution, coaxial gear degeneracy)
metadata:
  type: project
---

The operation motion study was rewritten 2026-07-08/09 (branch
motion-study-full-device, PR #217) for the default-free 7-sub architecture.
The old study targeted the retired `output-1` sub and a ~500 s
suppression-classifier walk over driver mates a `free` build no longer
authors. See [[motion-study-pipeline]] for the June recipe this supersedes.

**Why:** prove full functionality beyond the per-sub kinematic gates — one
crank motor operating the whole machine with real spring force elements, plus
video + pen-vs-truth assets.

**How to apply (the new shape):**
- ZERO suppression: deferred park drivers are ABSENT = free. Replay ENGAGED
  only the setup poses (drive-train cone_swing/pinion_swing/pinion_cam) + the
  20 bar_amplitude clamps — on each sub opened STANDALONE (the preflight
  ground) BEFORE the top opens; the top binds to the dirtied in-memory docs.
  A non-config amplitude preset patches spec params.distance = PIVOT.x + a_j
  (J5 is radius-invariant along the R800 arc, so re-stationing is consistent);
  drop the recorded verify point when patching.
- Study-only couplings, all cross-sub top-level (the output split lifted the
  same-flexible-sub AddMate restriction): 20 cam ring-point↔Axis3 (perturb
  20° first), crank↔T12 chain 1:1 gear (pick the T12 by
  ReferencedConfiguration — XY probing found nothing near the crank),
  summing↔magnifying lever 1:1 gear on the OFFSET pair (Axis1@summing-lever,
  5.134 mm off the knife line — a COAXIAL gear pair is degenerate: the
  coupling sense comes from the centre line), WIRE2 rim-point↔pen-rod Top
  Plane yoke.
- Suppress each channel's J2 rod-AXIAL mate (Front@rod↔Front@rocker) on the
  standalone channel doc: artifact A's axial + the cam point-on-axis = 7
  constraints on 6 DOF ⇒ 20 redundant loops (June's recipe had no axial).
- ALL real mates BEFORE create_motion_study; motion elements (motor, springs,
  gravity) after. A mate authored under an existing study risks the
  initial-animation-state corruption class.

**COM traps that each cost a ~40 min live run:**
- `open_model` FLAGS the doc and sets `adapter.currentModel` itself — never
  overwrite currentModel with a raw `swApp.ActiveDoc`: the unflagged dispatch
  breaks `GetTitle()` inside `_qualify_entity_name`, so every named
  mate-entity selection silently misses.
- Post-#87, component dispatches from `GetComponents` are UNFLAGGED and
  `GetModelDoc2()` is a METHOD: the unflagged call raises and `_attempt`
  reads None. `_flag(comp, "IComponent2")` at the point of use
  (`_comp_model_doc`).
- A union can eat part of a circular edge: the gooseneck lug consumes the
  pin end-face's top arc, so arc_center at (x, y+r, 0) fails while side/
  bottom points on the same circle select. Eye points are candidate LISTS.
- `SuppressMateParameters(component=None)` is a pydantic error — omit the
  kwarg.

**Basic Motion margin lessons (full machine = 6 flexible subs, 20 loops,
21 springs):**
- With everything coupled the machine moves CORRECTLY (rockers on the cam
  math, platen feeding) but the solve can die ~1/3 rev in, and identical
  fresh runs are NON-deterministic (dead vs partial). The system sits at the
  integrator's stability edge — de-marginalize (soft springs ~5 N/m, slower
  crank) rather than debug kinematics.
- In-session strip-and-recalc attribution is CONFOUNDED: repeated recalcs
  degrade toward lockup regardless of what was stripped (June's degradation
  caveat, rediscovered). Only each run's FIRST solve is evidence.
- The `kinematic` stage (cams + chain tie + motor, no springs/output) is the
  robust class: 2 crank revs tracked, rockers 5.5–7.7° (cam math ~7.8° max),
  platen 19 mm — the first healthy full-machine video came from it.
