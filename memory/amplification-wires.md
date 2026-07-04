---
name: amplification-wires
description: The two magnifying-wheel wires — now modeled as straight rest-pose rods (hub-wire/pen-wire) — and how the Motion study (Phase F) models their couplings
metadata: 
  node_type: memory
  type: project
  originSessionId: ba03bcc4-d81e-4e71-bbc7-7926c9a87d29
---

The harmonic analyzer's output amplification runs through TWO inextensible
steel WIRES at the magnifying wheel — both crucial for the Motion study, both
kinematic couplings (NOT springs). User flagged this explicitly 2026-06-13.

Topology (DIMENSIONS.md ch20 pp.46-49, ch21 pp.50-53, strongest-sourced):
`20 channels → summing-lever → magnifying-lever (rotates; adjustable ≤4× set by
the CLAMP position on the Ø-rod) → clamp+vertical-rod+OUTPUT-FIXTURE ride the
lever → WIRE 1 hooks the output-fixture (its mostly-vertical travel) and wraps
wheel hub Ø20 → magnifying-wheel → WIRE 2 leaves wheel rim Ø100 → pen-rod
(vertical travel)`. Wheel ratio Ø100/Ø20 = 5× (annotated). WIRE 1 attaches to
the output-fixture/vertical-rod (ch20 p.48: "the output fixture rides on it and
the wire to the magnifying wheel hooks below"), NOT the lever body directly. In
Phase D these 4 input-linkage parts are LOCKED to the magnifying-lever (clamped
at the set radius) so they rotate with it.

**REVISED 2026-07-04 (user request): the wires ARE now modeled as geometry** —
straight rest-pose Ø0.8 Plain-Carbon-Steel rods, book-checked. **FINAL
GEOMETRY after the same-day DEPTH RE-ANCHOR (ch30 p.4: the whole output line
reads as ONE PLUMB vertical at the machine front — the first cut's z −85
lever hung the hook 50 behind the wheel plane, ~8° lean, user-flagged as a
bug):** LEVER_ROD_Z −128.3 — the ONLY depth window (thumb-screw head vs
top-frame ring rail z −101..−123 needs ≤ −128.25; lever rod vs front column
surface −124.7 needs ≤ −127.95; the wire's rim-duck feasibility caps the hook
at ~−137.96 → ≥ −128.31); VROD_Z −134.8; bracket arm lengthened to machine
−124.3..−70 (plate flange band unchanged). `hub-wire` (MHA-099) runs from the
hook (−150, 925.35, −137.95 — tied under the fixture collar bottom, beside
the rod's front face at rod r + wire r + 0.25) to the hub-pitch tangency at
z −142.77, a 0.74° lean: a PERFECTLY planar wire is IMPOSSIBLE (the rim ring
z −142.9..−150.9 blocks every straight in-band approach; the hub pokes only
1.0 past the rim per side), so the run ducks behind the rim's back face into
the hub's back groove band. TRAP (historical, still valid): check the axle
flange's back-face EDGE CIRCLE in 3D, not just its face planes — an early
diagonal route grazed it by 0.024 (a 0.00 mm³ interference hit).
`pen-wire` (MHA-100, in pen.SLDASM, LOCKED to the pen-rod so it rides the pen
travel) is the vertical drop off the rim's 3-o'clock tangent (x −2.35 = wheel
−53 + 50 + wire r + 0.25) from y 565 to the rod's wire hole at 513, passing 1.7
in FRONT of the rod face (z −146.9 vs −149). Hub/rim WRAPS, hooks/tie-offs and
compliance are still NOT modeled; every run stands ≥0.25 off its neighbours
(offline clearance probe covers hub/flange/stud/rim/spokes/collar/rod/bar).
Endpoint math lives in the part scripts (build_hub_wire/build_pen_wire); the
assemblies import + assert it against their layout anchors (fail loud on
drift). No MIRROR_PLANE entry needed — a straight Y-cylinder rides the
default "x" bbox path (avoids re-keying all 8 assemblies via _transforms).

**WIRE 1 IS NOW A LIVE, BOOK-TRUE COUPLING in the saved magnifier (2026-07-04).**
magnifier joined build_lock `free` with THREE freed DOF (necessity gate stems
magnifying-lever + magnifying-wheel + hub-wire; 7 chain components read free;
closure in preflight — `FREE_ASSEMBLIES` includes magnifier):

1. **Lever knife-rock** (deferred `free_dof_key="lever_rock"`): the lever does
   NOT spin in the bracket collar — engineerguy video 2/4+4/4: it "extends
   from the pivoted summing bar" and pivots WITH it about the knife-edge
   ridge (pre-mirror (15, 995.134), along Z; ~6 mm tip arc ≈ 1.6°; the clamp
   position along the rod = the radius from THAT pivot = the real ≤4×
   adjustment). Mated via the part's `KnifeAxis` (Axis2, name_bore_axis from
   offset planes — local (215, 5.134)) held by two axis-to-plane distances +
   a Front-plane depth; the bracket collar is a loose Ø6.2/Ø6 guide.
2. **Hub-wire swing + spin** (deferred `wire_swing`/`wire_spin` angle parks):
   the wire ARTICULATES like the real one — a BALL JOINT at the hook
   (`HookPoint` arc_center ref point on the wire ↔ `HookAnchorPoint` hidden-
   sketch ref point on the fixture, both selected via component_named_ref —
   POINTs do NOT resolve through name@comp strings) + an AXIS-AXIS distance
   `wire Axis1 ↔ wheel Axis1 = 10.65` (the offset tangency; skew lines have
   ONE minimal distance → no far-side flip, and named refs survive solver
   motion — a point-picked FACE self-destructed when flip-recovery moved the
   wire). A LOCKED wire was the original sin: its hub tip swept laterally off
   the hub (user screenshot).

The wheel is COUPLED (no DOF of its own) by the **WIRE-1 yoke**: `WireYokePoint`
(hub pitch r10.4 at the tangency azimuth, from a hidden sketch point via
raw-COM `InsertReferencePoint(swRefPointSketchPoint=7)`, drift-asserted)
COINCIDENT to the hub-wire's `YokePlane` (offset ref plane ⊥ wire axis; part
origin at the HUB end). VALIDATED by the new `verify:kinematics` live-chain
gates (chain:magnifier:{wire-rides-hub, hook-ball-holds, coupling-alive,
restores-to-rest} — replay ONLY lever_rock, sweep 0..1°, close unsaved):
transmission is now LINEAR ≈ 17.2 rad/rad opposite-signed (lever +1° → wheel
−17.2°; ×5 hub→rim → the book's chain: 1.6° tip arc → ~24 mm pen swing), the
wire axis holds 10.6500 at every pose, hook residual 0.0000. KEY SW FINDINGS:
(1) GEAR mates need coplanar axes — lever(X)↔wheel(Z) REJECTED
(probe_couple_types.py, why the motion study lumped summing→wheel 5×);
(2) any rigid primitive linearizes a cable; with the hook-pivot articulation
the yoke transmits the HOOK's true motion (the pre-articulation lock gave a
wrong, strongly-asymmetric curve — measure rest ratios by CENTRAL difference).

WIRE 2 in the saved model is still snapshot-convention: the pen-rod's travel is
the F5 equation driver ([[pen-equation-driver]]) — a rim→pen yoke mate would
OVER-DEFINE against it (and needs flexible subs at top, it is cross-sub).
Phase 2 (making it live) = an architectural decision on where the crank→pen
math lives; NOT done. In **artifact B** (Motion study, Phase F) the two
snapshots are SUPPRESSED and replaced by:
- WIRE 1 = output-fixture VERTICAL travel → wheel hub rotation. Either a
  rack_pinion (fixture/vertical-rod linear ↔ wheel pitch dia = hub Ø20) or a
  gear `Axis1@magnifying-lever` ↔ `Axis1@magnifying-wheel` at ratio
  r_clamp : R_hub (the lever's adjustable part). Fixture rides the lever.
- WIRE 2 = rack_pinion mate, `Axis1@magnifying-wheel` (pitch dia = rim Ø100)
  ↔ `Axis1@pen-rod` slide axis (pen travel = 50·θ_wheel).

AS-BUILT (`build_motion_study_springs.add_wires_gravity`, stage `full`): WIRE1 =
the gear option (lumped 5×, summing-lever(Z) ↔ magnifying-wheel(Z)); WIRE2 is NOT
a rack-pinion mate — Basic Motion does NOT enforce rack-pinion in-sub (proven), so
it's a SCOTCH-YOKE: a RefPoint on the Ø100 rim (radius 50) held COINCIDENT to the
pen-rod's Top plane → `pen_Y ≈ 50·sin(θ_wheel)`, linear in the small operating
angles. Both wires use Motion-enforced primitives (gears + coincident
point-on-plane).

The named part axes added in Phase D (magnifying-lever, magnifying-wheel,
pen-rod slide axis) are exactly the refs these couplings select — Phase D is
the groundwork. `rack_pinion_mate` helper already in _common.py. See
[[harmonic-analyzer-project]].
