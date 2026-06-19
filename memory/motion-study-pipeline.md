---
name: motion-study-pipeline
description: Phase F motion-study recipe — Basic Motion (NOT MotionAnalysis), driver suppression, motor, sampling; all proven on drive-train
metadata:
  node_type: memory
  type: reference
  originSessionId: ba03bcc4-d81e-4e71-bbc7-7926c9a87d29
---

Phase F motion pipeline PROVEN end-to-end 2026-06-13 on drive-train.SLDASM
alone (`cad/scripts/probe_motion.py`): a crank motor drove the gear train and
cylinder-gear-1 (a cam) swept 270° across a 2 s run, sampled by transform.

CRITICAL licensing fact: **MotionAnalysis (study_type "motion_analysis",
type 4) is NOT licensed on this 3DEXPERIENCE Makers seat** — create_motion_study
fails with "StudyType did not take (read back 1)". Use **Basic Motion
(`study_type="physical_simulation"`, type 2)** — it is a REAL dynamics solver
that resolves spring/damper/force/gravity, so requirement #5 (true springs) is
met. Confirmed by the PR-M1 demo (`SolidworksMCP-python/scripts/demo_motion.py`)
which deliberately uses physical_simulation for this reason. There is NO
GetResults API; sample by `set_motion_time(t)` then read `component_transform`
(works for Basic Motion despite a docstring caveat — poses update per frame).

Proven recipe:
1. `create_motion_study(name="", study_type="physical_simulation", duration, activate=True)`
   — pass name="" to CREATE (a non-empty name LOOKS UP an existing study and
   errors). Capture returned `name`; later calls use study_name="" (active).
2. Free the DOF Motion must drive by SUPPRESSING its driver mate. Find the
   driver by walking the MateGroup (FirstFeature→GetTypeName2=="MateGroup"→
   GetFirstSubFeature; each sub.GetSpecificFeature2()→IMate2; .Type
   (distance=5,angle=6); .MateEntity(i).ReferenceComponent.Name2) and matching
   the referenced component. Crank driver = the Distance mate touching
   "crank-handle". `suppress_mate(name, suppress=True)` then ForceRebuild3 →
   crankshaft goes FULLY(3)→UNDER(2).
3. `add_motor(motor_type="rotary", entity=MateEntityRef(entity_type="AXIS",
   name="Axis1@crankshaft-1@drive-train"), speed=RPM, component="crankshaft-1")`.
4. `calculate_motion(name="")`; then `set_motion_time(t)` + `component_transform`
   to sample any part's pose over the run.
5. Video: `export_motion_video` (.mp4) — see [[motion-avi-export]].

FULL top-level study — RESOLVED 2026-06-13 (the driver mates to suppress live
INSIDE the subs; how to reach them):

- **DO NOT DissolveSubAssembly.** It is DESTRUCTIVE: the API auto-"deletes any
  features that need to be deleted", and the per-part driving-dim mates (spin /
  axial / snapshot drivers) reference each SUB's ORIGIN PLANES, which vanish on
  dissolve → SolidWorks deletes them. Probe (`probe_dissolve_motion.py`, since
  removed): dissolving all 3 moving subs left 329 comps but only **142 mates**
  (subs hold far more) and the crank driver was GONE. Dissolve shreds the very
  drivers you need to manage and breaks the fully-defined state.
- **Canonical path = FLEXIBLE subassemblies** (official help
  help.solidworks.com .../c_Flexible_Sub-Assemblies.htm: "the mates in a
  flexible subassembly are solved simultaneously with the mates of the parent
  assembly … a component moves only within its DOF" — the documented use case is
  literally "move the components of a PISTON subassembly in a MOTOR assembly").
  Basic Motion uses that same assembly solver, so a flexible sub's internal parts
  DO animate. [[flexible-subassemblies]] already proved the subs CAN go flexible
  on this seat.
- **The ONLY real obstacle is a TOOLING gap, not a SolidWorks limit**: the
  adapter's `suppress_mate` resolves a mate via `FeatureByName` + a TOP-LEVEL
  MateGroup walk, neither of which descends into a sub — so a driver nested in a
  flexible sub is unreachable by name from the parent. FIX: retarget suppression
  at the sub's already-loaded model doc — `comp = GetComponentByName("drive-
  train-1"); sub_model = comp.GetModelDoc2()`, set `adapter.currentModel =
  sub_model` (it is a plain settable attribute), call `suppress_mate(name)`
  (the mate keeps its standalone name, e.g. crank driver = "Distance34"), then
  restore currentModel. NEVER save the sub → artifact A on disk stays fully
  defined. (`_SUPPRESS_FEATURE=0/_UNSUPPRESS=1`, `_ALL_CONFIGURATIONS=2`.)
- Entity refs for parts in a flexible sub need the FULL instance path, e.g.
  `Axis1@crankshaft-1@drive-train-1@harmonic-analyzer` (build from the
  component's path, not just `@drive-train`).

The cam ring↔lobe couplings + the two wires ([[amplification-wires]]) + 21
springs + crank motor are added on the (flexible, NOT flattened) top level —
top-level mates can reference parts inside a flexible sub. See
[[flexible-subassemblies]], [[harmonic-analyzer-project]].

GATE PROVEN 2026-06-13 (`probe_flex_motion.py`): a top-level rotary motor DOES
drive a FLEXIBLE sub's internal gear train. Built fresh (frame fixed +
drive-train grounded by 3 coincident plane mates + made flexible), suppressed the
crank driver IN the sub doc via currentModel retarget, added the motor, ran Basic
Motion -> cylinder-gear-1 (cam) swept a full rev over 2 s @ 30 RPM. The whole
non-destructive flexible-sub architecture is validated. Critical empirical facts:
- **`GetConstrainedStatus` is a LIE for flexible-sub children**: the crankshaft
  read FULLY(3) before AND after suppressing its driver AND after ForceRebuild3 +
  EditRebuild3 -- yet the cam moved. Status reflects the sub's own internally-rigid
  solve, NOT the parent flexible solve. NEVER gate on it; trust calculate + a
  Transform2 sample over the run.
- **Motor entity for a nested part = `IComponent2.GetCorrespondingEntity(face)`**,
  NOT a hand-built `Axis1@a@b@title` string (malformed for multi-level nesting;
  SelectByID2 silently falls back to top level). Take a CYLINDRICAL FACE from the
  part doc (`comp.GetModelDoc2()` -> GetBodies2(0,False) -> faces -> ISurface.
  IsCylinder + CylinderParams), map with GetCorrespondingEntity, and **assign the
  returned dispatch DIRECTLY to data.Location/DirectionReference** (its Select4
  returns False but direct assignment works). Crank axis = r4.76mm (0.375") face,
  local -Y.
- Re-fetch the IComponent2 AFTER each rebuild / each SetTime frame (a pre-rebuild
  pointer reports stale pose); read Transform2 off the dispatch (nested
  GetComponentByName('sub/part') returns None).
- Measure rotation about ANY axis via R_rel=R1·R0^T, angle=acos((trace-1)/2) --
  atan2(y,x) only sees rotation about Z and the cam spins about Y.

PR-M4 formalizes: set_component_solving(name, "rigid"|"flexible"); suppress_mate
+component (retarget to the sub's GetModelDoc2); motor entity by component-face
(GetCorrespondingEntity, direct dispatch assign).

**SAME-FLEXIBLE-SUB AddMate RESTRICTION (proven 2026-06-13).** A top-level mate
CANNOT join two components that are BOTH nested in the same flexible sub —
AddMate5 returns status 0 "unknown error" on every alignment, for coincident AND
concentric. This was the real cause of the 20/20 `rod pin <-> rocker bore`
failures (NOT the 0.39mm rigid-loop / over-constraint theory, which was wrong —
the four-bar IS closeable: circle-intersection |127−120.92| ≤ 178.6 ≤ 127+120.92,
slack absorbed by ~0.2° rocker rotation). Decisive isolation (`probe_axis_isolate.py`):
the SAME rod.Axis2 mates fine CROSS-sub to gear.Axis3 (channel↔drive-train, OK)
but same-sub to rocker.Axis2 FAILS; rod.Axis1↔rocker.Axis2 (also same-sub) fails
too. So cross-sub couplings (cam ring↔lobe) are fine at top level, but an
intra-sub joint must be authored INSIDE that sub's own doc. FIX pattern (same
currentModel-retarget as suppress): `_, ch_doc = _sub_model(adapter,"channel-1");
adapter.currentModel = ch_doc;` add coincident(rod-i.Axis2, rocker-i.Axis2) where
rod/rocker are now SIBLINGS of the sub (Name2 has no slash, pair by Z-rank);
restore currentModel; NEVER save the sub. Proven end-to-end (`probe_sub_mate.py`):
in-sub pin↔bore OK + top-level cam-after OK = the four-bar closes. In
build_motion_study.py = `_add_rod_rocker_revolutes` (runs after rod ring drivers
suppressed, before `_add_cam_couplings`). Also: **concentric on two named
reference AXES is rejected even cross-sub** — use coincident for axis-to-axis.

**FULL-DEVICE KINEMATIC GATE — diagnosis 2026-06-14 (in-process probes, doc
left open by the build).** Sequence of decisive findings:
- **Motion-study CALCULATED results do NOT survive disconnect/reconnect.** Two
  cross-process probes contradicted (crank=180 vs crank=0); a study calculated in
  one process reads all-zeros (assembled pose) after a fresh attach. RULE: always
  `calculate_motion(name=STUDY)` IN THE SAME PROCESS right before sampling. The
  named study re-activates on attach via set_motion_time(study_name=...).
- **Cached IComponent2 dispatches DO reflect motion across SetTime frames** —
  memory's earlier "must re-fetch every frame" caveat was OVERCAUTIOUS. Walk the
  tree ONCE, cache (comp, name), read Transform2 off the cached dispatch each
  frame: crank span=180 came off a cached dispatch. The full-tree Name2 walk is
  ~270-300s for 345 comps (the cost is `sw_type_info.flag_methods` per comp in
  `_read_member`/`_flag`); a TOP-LEVEL walk (toplevel=True) is ~3s. So pay ONE
  full walk, then frames are <1s each. (`probe_live.py`, `probe_chain_live.py`.)
- **All 3 moving subs ARE flexible** (Solving=1) in the built doc — not the bug.
- **The drive chain breaks at the cam coupling, by OVER-CONSTRAINT.** With all 20
  cam couplings active the cone-shaft + everything downstream of the crank is
  FROZEN (motor just overpowers the crank↔16T-pinion lock → crankshaft spins 180
  while the locked pinion reads 0 — the signature of a jammed mechanism the motor
  fights). Suppress all 20 cams → gear train spins free (cylgear span 170°,
  `probe_suppress_cam.py`). Unsuppress just ONE cam → mechanism MOBILE again
  (crank 146°, cylgear 168°, rockers rock up to 23°, `probe_one_cam.py`). So the
  four-bar SCHEME is sound; the lock appears only with many loops active = classic
  redundant-constraint accumulation in 20 parallel closed loops. Each cam coupling
  (COINCIDENT on two axes = collinear, 4 constraints) RE-fixes the rod's
  out-of-plane orientation that the rod↔rocker pin (also coincident-axes, 4)
  already fixes → ~1 redundant constraint/loop × 20 → Basic Motion locks. FIX
  DIRECTION: make each cam coupling POSITION-ONLY (ring-centre point ON lobe axis
  = 2 constraints) so cam(2)+rodrocker(4)+pivot(5)=11 on rod+rocker's 12 DOF = a
  clean 1-DOF loop, no redundancy. Connecting-rod ring centre = the rod's ORIGIN
  (ring centred at origin; Axis1=ring bore @origin, Axis2=pin bore @(0,127)).

**WORKING RECIPE for the full-device kinematic gate (proven 2026-06-14).** TWO
changes together make it reliably move:
1. **Point-on-axis cams.** The rod ORIGIN feature is NOT mateable (AddMate5
   "unknown error"). Create a real ring-centre RefPoint at RUNTIME on the SHARED
   `connecting-rod.SLDPRT` part doc (all 20 instances inherit it via
   GetCorresponding), NEVER saved → artifact A untouched. Recipe: resolve a rod
   comp's part doc (`comp.GetModelDoc2()`), **ActivateDoc3(part_title,…,
   _byref_i4())** (selection in a component's part doc REQUIRES it be the ACTIVE
   doc — else `create_reference_point` edge-select fails), then
   `create_reference_point(mode="arc_center", edge_point=[25.5,0,1.5])` (a point
   on the Ø51 bore circular edge → centre = ring centre; returns e.g. "Point2"),
   ActivateDoc3 back to the assembly. Cam mate = `coincident_mate(
   component_named_ref(rod,"Point2","POINT"), component_named_ref(gear,"Axis3",
   "AXIS"))`. 20/20 add OK. (`probe_mkpoint.py`, `probe_refpoint_fix.py`.)
2. **Reset-before-calc.** `calculate_motion` is POSE-DEPENDENT: 3 identical
   recalcs of the UNCHANGED model gave 11.9/0/0 (run1 from a fresh rebuild moved,
   run2/3 from the prior calc's t=1.5 pose LOCKED). Before EVERY calc do
   `set_motion_time(0)` → `ForceRebuild3(False)` → `EditRebuild3()`. With reset,
   3 trials all MOVED (crank 102-170°, coneshaft 25-68°, rockers 1-7°) — never
   locks. (`probe_reset_calc.py`.) So the deliverable must calc ONCE from a clean
   assembled pose.
CAVEAT: motion is WEAK + variable + DEGRADES across repeated trials (maxrock
7.4→3.2→1.2 — the flexible-sub pose still leaks past reset). A single calc after a
fresh build gets the best (trial1) quality. Gate "rockers rock >0" PASSES; pen-
trace QUALITY tuning (frames/accuracy/mate stiffness, maybe coincident-axes which
is a stiffer revolute) is a follow-up if the trace is too faint.

**F3 KINEMATIC GATE PASSES END-TO-END 2026-06-14.** The last blocker: the
point-on-axis cam ADDED 20/20 in `probe_refpoint_fix` (displaced post-motion doc)
but FAILED 0/20 in a fresh build ("AddMate5: mate over-defines the assembly").
Root cause = **DEGENERACY at the exact design pose**, NOT the rod↔rocker revolute
(disproven: collinear-axes cams over-define too once the revolutes exist; the
distinguishing variable is pose). At the design pose the rod ring point lies
EXACTLY ON the eccentric lobe Axis3 (zero-distance) → AddMate5 rejects the
point-on-axis. FIX (proven decisively `probe_perturb_cam.py`: control FAIL vs
perturbed 3/3, then full build 20/20): **before adding each cam, spin its gear
~20° about its own axis** so the eccentric lobe orbits OFF the stationary rod ring
point → non-degenerate → mate adds. Read the spin axis from the gear's world
transform (`Transform2.ArrayData`: local Z→cols 6..8, origin→cols 9..11 in m);
`rotate_component(mode="exact", axis_vector=cols6..8, axis_point=cols9..11*1000,
angle=20)`. The closing `ForceRebuild3` snaps every gear back to its
concentric+axial mate pose (dragging the ring back onto the lobe); the added mate
then just holds. Baked into `_add_cam_couplings`. Full `build_motion_study.py
kinematic` (526s): 20/20 in-sub revolutes + 20/20 cams + crank motor + reset +
calc → **rocker rock spans 18.7°/16.7°/13.6°**, oscillating over 2 crank revs.
NOTE: results were GOOD on this single fresh-build calc (no degradation seen) —
consistent with "calc ONCE from a fresh build". Next: F4 springs.

**F4 SPRINGS PASS 2026-06-14** (`build_motion_study_springs.add_springs`, stage
`springs`/level 2). 20 channel + 1 counter `add_motion_spring` (linear). Endpoints
= eye-centre RefPoints created at runtime via `create_reference_point(mode=
"arc_center", edge_point=<local pt on the eye hole's circular edge>)` on each
SHARED part doc (ActivateDoc3 round-trip, inherited by all instances, NEVER
saved) — VALIDATED edge points: channel-lever `[179.8,0,0]`, summing-lever
`[39.35,8.0,-69.05]`, gooseneck `[-109,165,0]`, boss-hook `[6.5,16.5,0]` (the
boss-hook eye is the swept-rod END-FACE circle at X=6.5, NOT the side). The 20
channel-spring BOTTOM eyes all share ONE summing-lever point (every plate hole has
the same X off the Z knife axis → identical torque arm → faithful summing torque
from one point). k = G·d⁴/(8·D³·n): channel 2127.8 N/m (d1.0/D5.5/n28), counter
514.8 (d1.8/D10.7/n165). `free_length=None` = zero force at assembled pose (motion
from cam-chain length changes; no pretension to calibrate). MUST suppress the
summing-lever ANGLE snapshot driver first (`_suppress_named(output-1,
("summing-lever",), (ANGLE,))`) so springs can rock it. RESULT: rockers still
17/16.6/13.8°, **summing-lever rock span 45.13°** (large — F6 amplitude tuning via
k / free_length, but gate "springs move it" PASSES). The 4 output compliant-chain
families: summing-lever (ANGLE snapshot=suppress, DISTANCE axial+COINCIDENT
pivot=keep), magnifying-lever (ANGLE=suppress), magnifying-wheel (ANGLE=suppress),
pen-rod (DISTANCE travel=suppress, other slide DISTANCE+spin ANGLE=keep); platen
families STAY pinned (crank-coupled coefficient). mag-lever/wheel/pen-rod
suppression belongs with F5 wires that drive them.

**F6 SPRINGS-FEASIBILITY RE-VERIFIED 2026-06-14 (a research agent's "Basic
Motion fundamentally can't force-balance" verdict was an OVERSTATEMENT).** User
asked to double-check before abandoning springs. Findings, decisive:
- **The `ISimulationSpringFeatureData` "motors supersede springs" Remark is
  NARROW**: verbatim it governs ONE part that has BOTH a motor AND a spring ("a
  motor moving a component to the left and a spring pulling [that] component to
  the right → moves left"). The **summing-lever has NO motor** (only the crank
  does) → springs act on it with full authority. F4 already proved this: springs
  rocked it 45.13°. Basic Motion IS a real dynamics solver (integrates
  spring/damper/force/gravity on free bodies — that's why the PR-M2 pendulum demo
  works); it is NOT animation-only.
- **The real F4/F5 blocker was the FROZEN channel-levers, not the springs.**
  `channel-lever=0.00` every timestep = a KINEMATIC transmission gap: the
  rocker→amplitude-bar→channel-lever link is a physical CONTACT (bar foot rests on
  the rocker R800 arc) and **Basic Motion IGNORES contact unless explicit 3D
  solid-body contact is added** (SW help, Basic Motion overview); PLUS the bar/
  lever artifact-A spin drivers were KEPT. Dead spring inputs → springs correctly
  settle to a static equilibrium and hold ("jump to 45° + freeze"). Fix the inputs
  and the springs get a time-varying signal. So springs are FEASIBLE; decision =
  attempt spring path first (user, 2026-06-14), interpolated-motor fallback.
- **Remaining spring-path RISKS (feasible ≠ guaranteed clean trace):** (1) must
  author a real mate for the bar-foot-on-rocker-arc (tangent/coincident in-sub,
  since contact is ignored) + suppress the bar/lever snapshot drivers; (2) the
  solve is DYNAMIC not quasi-static — for the pen to trace a clean ΣA_k·sin the
  summing-lever's natural freq must exceed the harmonic freqs, else ringing/lag/
  attenuation → needs stiffness/inertia/damping tuning; (3) heavy solve (20
  springs + gears + 3 flexible subs) locked/degraded before, ~hour runtimes.
- **Adapter add_motor is CONSTANT-SPEED ONLY** today; the interpolated fallback
  needs an extension — SW DOES support it (`ISimulationMotorFeatureData.
  InterpolatedMotor` + `LoadSplineData(file)` reads a `time,value` table;
  `Expression` and `OscillatingMotor` also exist).

**LICENSING — Motion Analysis CANNOT be bought for the Makers seat (researched
2026-06-14).** "SOLIDWORKS for Makers" $48/yr lists "Motion Studies" = Animation
+ Basic Motion ONLY. **Motion Analysis** = the separate "SOLIDWORKS Motion"
add-in, bundled in SOLIDWORKS Premium (~$3,300–7,100) or attachable to SOLIDWORKS
Connected only as a separately-purchased COMMERCIAL Simulation/Motion licence
(Simulation Standard list ~$4,195). Makers has a FIXED feature set (no purchasable
roles) and the official FAQ states "there is no direct upgrade path from a
SOLIDWORKS for Makers licence to a commercial one." So force-spring quasi-statics
via MotionAnalysis is off the table at any reasonable cost — Basic Motion is the
only solver, and the spring force-balance must work within it.

**F6 ISOLATED POC — Basic Motion DOES sum moving-anchor springs (PROVEN
2026-06-14).** `cad/scripts/poc_spring_adder.py` (reuses pivot-shaft fixed
guides + pivot-bushing vertical sliders; 2 oscillating linear motors as moving
anchors at distinct freqs/amps + 1 free output node held by 2 channel springs +
1 counter spring). Result: out = **0.4002·in1 + 0.4001·in2 + c, R²=0.992** —
matching the closed-form weighted average (k_ch=2, k_ch=2, k_ct=1 →
out=(2·in1+2·in2+1·datum)/5 = 0.4/0.4/0.2) to THREE decimals. The spring path is
VIABLE. Three keys (carry into the full model):
- **Spring k must be ~N/m scale.** k=2000 N/m ABORTS the solve (ω≈177 Hz, too
  stiff for the fixed-step integrator → inputs freeze ~1.2 s); k=0.1 N/m too soft
  (forces ~0.003 N drown in numerical noise → 50 mm wander, R²≈0); **k≈2 N/m
  (ω≈5.6 Hz) settles clean.** Tune full-model spring constants into this regime,
  NOT the geometric G·d⁴/(8D³n) steel values (those are ~10⁴–10⁵ N/m → far too
  stiff for Basic Motion).
- **Drop the startup transient before sampling.** The free node needs ~1–3 s to
  settle from the assembled pose onto the moving spring equilibrium; those frames
  are not quasi-static. POC fit on t≥3 s of a 20 s run.
- **No explicit damper needed — Basic Motion has STRONG inherent numerical
  damping.** `cad/scripts/poc_damper_check.py` (textbook 1-DOF mass-spring under
  gravity, released from rest): oscillation decayed early-pk-pk 329 mm → late
  ~5 mm with damper OFF *and* ON, IDENTICAL (ratio 0.015). So the inline spring
  damper / separate `add_motion_damper` element have ~no effect in
  physical_simulation (50 N·s/m on a 1.6 g node barely moved the span) — but it
  does not matter, the solver dissipates transients on its own. Earlier "dampers
  ignored → springs dead" was a WRONG diagnosis; real cause was over-soft springs.

**F6b CHANNEL-LEVER TRANSMISSION — gear coupling PROVEN (2026-06-14).** The
springs diagnostic showed crank 31 deg + rockers ~17 deg move but channel-lever
= 0.00 every frame: the rocker->amplitude-bar->channel-lever link is the bar-
foot-on-rocker-arc CONTACT, which Basic Motion ignores. Fix = an in-sub GEAR
mate rocker(Axis1) <-> channel-lever(Axis1) (parallel Z), authored inside
channel.SLDASM (both parts share the one flexible sub, so top-level AddMate5 is
rejected -- same as the rod<->rocker revolute). probe_channel_gear.py proved it
kinematically: rocker rotated 160.7 deg -> channel-lever 159.0 deg (ratio 0.990
for a [1,1] gear). CRITICAL gotcha: the channel-lever has its OWN J4 bar-pin
spin driver (build_channel_assembly _revolute adds concentric+axial+spin per
revolute) -- suppress rocker-arm AND amplitude-bar AND channel-lever recurring
drivers, else the lever stays pinned to ground and the gear drives nothing (1st
probe: rocker moved, lever 0.00). The gear RATIO encodes the integration
coefficient (user: each of the 20 bars may be moved to set the analyzer's
coefficient); modelled default state is UNIFORM (solve_default_state takes no
channel arg) so one ratio serves all 20, derive per-channel from bar geometry
when non-uniform. The bar goes cosmetic (dangles from J3, no force -> stays put).
Two probe-infra gotchas: standalone probes MUST CloseAllDocuments(True) first
(a prior run's in-memory motion study triggers the blocking "Update Initial
Animation State" modal on suppress/rotate, and no-ops rotate_component);
artifact A .SLDASM on disk stays clean (never saved -- mtime unchanged).
