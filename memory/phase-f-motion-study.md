---
name: phase-f-motion-study
description: "Phase F operation Motion study — scope decision, sub-mate ground truth, suppression classifier"
metadata: 
  node_type: memory
  type: project
  originSessionId: ba03bcc4-d81e-4e71-bbc7-7926c9a87d29
---

Phase F = build_motion_study.py (artifact B): throwaway Basic Motion
(physical_simulation; MotionAnalysis UNLICENSED on this Makers seat) opening
the static fully-defined harmonic-analyzer.SLDASM, never re-saving it. See
[[motion-study-pipeline]] (gate PROVEN: top motor drives a flexible sub's gear
train) and [[amplification-wires]].

> **NOTE (later drift):** the spring-eye world coordinates quoted below (lever eye
> 1063.65, plate eye 989.5) are the 2026-06-13 Phase-F values; they were superseded by
> the OD-62.2 and ch14-ROM re-anchors — current `LEVER_EYE_Y` ≈ 1062.52, `PLATE_EYE_Y`
> ≈ 996.54, gooseneck tip ≈ 1370.6. The PR/branch labels (`#64`, `#63`, `demo_motion.py`)
> are historical and not all resolvable in git today. The METHOD (named-axis depth-2
> selection, cam Z-rank pairing, suppression classifier) is unchanged.

**Scope decision 2026-06-13: user chose "Incremental, push for full"** — validate
the per-sub suppression recipe in isolation first (fast), then assemble the full
crank-driven device with the 21 real springs + the two wires. (Options offered:
full / drive-train+cams / fallback-c drive-train-only.)

**Pipeline:** open asm → for the 3 MOVING subs (drive-train-1, channel-1,
output-1; frame-1 stays fixed) float + ground rigid pose at identity with 3
coincident plane mates + set_component_solving FLEXIBLE → suppress internal
driver dims via suppress_mate(component=<sub>) → 20 cam concentrics (rod ring ↔
cylinder-gear eccentric lobe Ø50.8) → crank rotary motor on crankshaft face →
21 springs (k=G·d⁴/8D³n, G=79.3 GPa; channel d1.0/D5.5/n28/free32; counter
d1.8/D10.7/n165/free315) → 2 wires (WIRE1 fixture→hub Ø20, WIRE2 rim Ø100→pen,
5×) → gravity → Calculate → mp4 + pen-tip-vs-harmonic-curve sample.

**SLOW iteration:** full asm ~5 min to open, mate-walk ~2.3 s/mate (~300 mates =
~12 min). DECOUPLE: dump each sub's mates once to JSON, design the classifier
offline. The mate value read uses DisplayDimension2(0)→GetDimension2(0)→.Value.

**Channel mate ground truth (per channel j, suffix = j+1):** the ASSEMBLY ROOT
plane shows up as a referenced "part" named after the sub ("channel"/"drive-train"
/"output") — filter it out; a real driver = ONE real part + the root. Structural
mates ref TWO real parts (e.g. Concentric pivot-shaft-1↔rocker-arm-N). Per part
the single-real-part DISTANCE mates split into:
- AXIAL-Z that VARIES by the 7.0565 mm channel pitch (38.07,31.02,… ) → KEEP
  (holds the part at its station);
- POSE drivers CONSTANT across all 20 channels → SUPPRESS: rocker-arm spin
  ≈249.11; connecting-rod ring-X≈47.37, ring-Y≈121.72, swing≈48.01.
Classifier rule: bucket single-real-part dist/angle values by family; a bucket
recurring across many instances = pose (suppress), per-instance-unique = axial
(keep). amplitude-bar stays FULLY pinned (coefficient) — exclude it. channel-lever
has a constant 1066.72 whose role (structural fulcrum-Y vs angle pin) is unverified
— test in isolation before suppressing.

**CAM COUPLING SOLVED 2026-06-13 (the core unlock).** Artifact A has NO cam
mates (subs inserted rigid+fixed); the cam coupling lives ONLY in the motion
study. DO NOT use face-based concentric on the cylinder-gear — walking its
~thousands of tooth faces took 430 s/call AND the lobe face won't Select4
through a nested flexible sub (returns False → "concentric needs 2 entities",
mate never forms, nothing moves). FIX = named reference axes:
- Added **Axis3@cylinder-gear** = eccentric cam-lobe axis (part-local x0,
  y −ECCENTRICITY) in build_cylinder_gear.py (_name_lobe_axis, verified via
  IRefAxis.GetRefAxisParams so a flipped offset fails loudly). Axis1=pattern,
  Axis2=bore (rides arbor), Axis3=lobe.
- Per channel, TWO two-axis COINCIDENT mates (AddMate rejects concentric on two
  axes): Axis1@connecting-rod ↔ Axis3@cylinder-gear (cam→rod); Axis2@connecting-rod
  ↔ Axis2@rocker-arm (rod→rocker). Rocker pivot revolute is in artifact A (kept).
- Pair the 3 part families by **Z-RANK** (sort each by world Z, zip by index) —
  a rod's Z sits between its own gear and the next station's gear so nearest-Z
  mis-matches.

**DEPTH-2 SELECTION CORRECTED 2026-06-13 (PR-M5 #64, MERGED to personal).** The
hand-built `Axis@part@sub@asm` string FAILS for a part nested two levels deep
(part-in-sub-in-top). Verified live: SelectByID2 resolves ONE level
(`X@sub@asm` selects the sub's own ref geom) but returns False at depth two
(`X@part@sub@asm`) — planes AND axes. The 1-channel rig "passed" only because it
placed parts DIRECTLY (single nesting). GetCorrespondingEntity is entity-only
(face/edge/vertex) and rejects an IRefAxis. FIX (user-researched: CADBooster /
CodeStack): `IComponent2.GetCorresponding` maps ANY persistent-ID object incl.
an `IFeature` reference axis — keep the BASE IFeature (FeatureByName, NOT
GetSpecificFeature2's IRefAxis), `comp.GetCorresponding(feat).Select2(append,
mark)`. Depth-agnostic (the IComponent2 encodes its full path) and ~600x faster
than the cylindrical-face walk (gear Axis3: 1.02 s vs 612 s measured). Adapter:
`MateEntityRef(entity_type="AXIS", component="sub-1/part-1", name="Axis3")` ->
new `_component_named_feature`, honored by `_select_mate_entity` (mates) AND
`_resolve_motor_entity` (motor). So the cam coupling = component+name AXIS refs,
NOT named-string refs. See [[verify-sw-api-with-research]].

**SPRING + WIRE GROUND TRUTH (verified 2026-06-13, for build_motion_study_springs.py).**
- Channel spring (build_channel_spring_installed.py): linear Motion spring per
  channel between the lever tab eye (world Y 1063.65) and the summing-lever plate
  eye (world Y 989.5, under the plate); plate holes at z_j-1.95. k via
  _k_helical(d1.0,D5.5,n28); cosmetics OD6.5/wire1.0/coils28, free 32.
- Counter spring (build_counter_spring.py + build_output_assembly.py): ONE linear
  spring between boss-hook ring (95,1012,0) [rod along X at (95,1015)] and the
  gooseneck tip X-pin (95,1373,0). k via _k_helical(d1.8,D10.7,n165); free 315.
- Adapter API (base.py): MotionSpringParameters(spring_type="linear",
  endpoints=[MateEntityRef,MateEntityRef], spring_constant=<N/m>, free_length=mm
  or None, damping_constant, coil_diameter/wire_diameter/number_of_coils cosmetic,
  reverse, study_name). add_gravity(MotionGravityParameters(axis="y",
  strength=9.80665, reverse=True)). add_motion_damper/add_motion_force exist.
- Wires (MOTION couplings, NOT artifact A) via _common.rack_pinion_mate(rack_ref,
  pinion_ref, pinion_pitch_diameter=mm OR rack_travel_per_revolution=mm). Axes:
  Axis1@magnifying-wheel ("wheel axis", local Z, hub Ø20 + rim Ø100, 5x);
  Axis1@pen-rod ("slide axis", local Y long axis). WIRE1 fixture/vertical-rod ->
  hub Ø20; WIRE2 rim Ø100 -> pen-rod. Endpoints: named_ref / bore_axis_ref(point).
  Eye world points read live via _common.world_point(adapter,name,local_mm).
- build_motion_study_springs.py NOT yet written; imported only at level>=2
  (springs/full); kinematic stage (level 1) does not touch it.
- SPRING ENDPOINT = NAMED DATUM POINT (proven by demo_motion.py PR-M2):
  endpoints=[MateEntityRef(entity_type="DATUMPOINT", name="Point1@<instance>"),
  ...]; _select_two_endpoints -> _select_mate_entity selects each by name via
  SelectByID2 (the name path that survives nesting, like the cam Axis3; a
  point/face pick returns Select4=false through a flexible sub). => the springs
  stage must add NAMED eye reference points (create_reference_point) to the
  connected PART scripts: channel-lever tab eye + summing-lever plate eye (x20),
  summing-lever boss-hook + gooseneck tip for the counter spring. Datum points
  add no DOF so artifact A stays fully-defined; needs a parts rebuild + reassembly.
  Do this only AFTER the kinematic gate confirms the cam chain moves.
  NOTE: cad/scripts has NO create_reference_point usage yet (only name_bore_axis
  for axes) -> springs stage must add a _common helper (name_eye_point wrapping
  create_reference_point, mirror name_bore_axis) + eye points on build_channel_lever,
  build_summing_lever (per-channel plate holes), build_boss_hook, build_gooseneck.

**SUPPRESS BUG FIXED 2026-06-13:** _do_suppress must keep adapter.currentModel =
TOP assembly; suppress_mate(component=sub) resolves the component vs currentModel
then GetModelDoc2-retargets itself. Switching currentModel to the sub doc made it
fail "Component not found: 'drive-train-1'". Also: reading mate metadata on a
FLEXIBLE sub is ~1.7-2.3s/mate (parts walk + DisplayDimension2) -> ~25min/run;
_iter_mates(read_values=False) for the crank driver, lazy value read for channel
candidates only. Still slow (parts walk unavoidable); a name cache would help.

**DRIVE-TRAIN CORRUPTION + FAIL-FAST GATE 2026-06-13.** drive-train.SLDASM was
CORRUPT ON DISK: 40 broken mates (GearMate2-21 + Coincident3-22, the per-channel
cone<->cylinder gear meshes + cylinder-gear radial coincidents), all swFeatureError
code **48 = swFeatureErrorMateBroken = "one or more mate entities were
suppressed"**. Shared entity across all 40 = `Axis2@cylinder-gear` (bore axis) —
the assembly went stale when cylinder-gear was rebuilt (Axis3 lobe added +
revolve-pi fix) while the gate was blind to mate errors. The build gates MISSED
it: `assert_components_fully_defined` passes broken mates (a grounded comp reports
FIXED regardless of mate health) and `check_no_interference` does not see mate
state. FIX = new `_common.assert_model_healthy(deep=True)`: ForceRebuild3 +
`IModelDocExtension.GetWhatsWrong` (byref VT_BYREF|VT_VARIANT out-params — a bare
pywin32 call RAISES; mirror com_variant.byref_long via `_byref_variant`), raises
on any non-warning entry. **deep=True walks each top-level component's OWN doc**
(GetModelDoc2) — a flexible sub's internal mate errors show ONLY there, the
parent's What's Wrong shows just a component-level WARNING (code 1, warning=True),
hiding them. Wired into `save_assembly_and_images` so no broken assembly is ever
saved. Also `whats_wrong()` (raw reader) + `body_faults()` (IBody2.Check3 ->
IFaultEntity, degenerate-geometry / sliver detection for PART corruption — the
0.7.0 skill learning detecting-faulty-geometry.md; complementary, NOT the mate
tool). Rebuilding drive-train regenerates the mates fresh against current parts.

**ADAPTER FIX (SolidworksMCP #63, MERGED to personal).** create_plane(mode=
"offset") silently collapsed NEGATIVE offsets onto the base plane: InsertRefPlane
Distance needs a +magnitude with OptionFlip for the side; a negative distance is
clamped to 0. Fixed via _offset_plane_distance (abs + toggle flip). Was blocking
the lobe axis (landed at origin). [[fix-relations-last-resort]] pattern: named
refs over geometry-walks.
