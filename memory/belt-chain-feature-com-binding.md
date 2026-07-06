---
name: belt-chain-feature-com-binding
description: SW Belt/Chain feature via pywin32 — for a correct EngageBelt coupling ratio on toothed wheels the pulley members MUST be datum AXES, not faces; with FACE members the MateBeltDim bakes the picked faces' TIP diameters and NO definition-level route (PulleyDiameters+ModifyDefinition, ModifyMemberParameters, EngageBelt re-author, direct mate-dim writes) changes the coupling — all verified inert live
metadata:
  type: reference
---

## Belt/Chain assembly feature — the full pywin32 recipe (2026-07-05/06)

For the paper-drive operational-DOF rework (couple the T12 crank sprocket ↔ T24
knob sprocket so the crank drives the paper feed). Working probes:
`cad/scripts/diagnostics/probe_belt_feature.py` (creation),
`probe_belt_mate_dims.py` (found where the ratio lives),
`probe_belt_ratio_fix.py` + `probe_belt_mate_dim_write.py` (proved every
definition-level route inert), `probe_belt_axis_members.py` (the fix, measured
ratio +0.5000). Extends [[chain-component-pattern]].

> **Lesson, FOUR times now: do NOT conclude "the API can't do this" from a
> null/empty/False return — and do NOT conclude "it worked" from a green
> read-back.** (1) Wrong pulley member TYPE made CreateFeature null →
> "infeasible in pywin32" (wrong). (2) Reading `PulleyDiameters` without
> `AccessSelections` returns EMPTY → "EngageBelt ignores PulleyDiameters, use a
> gear mate" (codex #189 round-5 — wrong, and a gear mate also REVERSES the
> rotation sense a chain preserves). (3) Late-bound `ModifyDefinition` returns
> False → looks like "unsupported" (wrong — early-bind the IFeature). (4) The
> post-create PulleyDiameters enforcement read back GREEN while the measured
> coupling stayed at the face-derived 0.538 — the definition and the mate are
> DISJOINT stores. Verify the behaviour (drive it and measure), not the
> property. Per [[verify-assumptions-live-sw]].

**Enum:** `swFeatureNameID_e.swFmBeltAndChain = 119` (verified via .NET reflection;
NOT 92 — a wrong value → CreateDefinition null).

**Creation (proven):**
1. **Pulley members: datum AXES for a correct coupling** (see below). The
   face route (each pulley's largest cylinder about the rotation axis) also
   creates fine but poisons the coupling ratio on toothed wheels. Passing
   IComponent2 objects → CreateFeature silently null.
2. `data = fm.CreateDefinition(119)` → `typed = sw_type_info.early_bound(data,
   "IBeltChainFeatureData")` → set `PulleyComponents` (dispatch_array of the
   member entities), `PulleyDiameters` (double_array, METRES), `FlipSides`,
   `BeltLocationPlane` (IRefPlane normal to the axes), `EngageBelt=True` (the
   coupling mates — a `BeltMates1` folder holding a `BeltMate1` of type
   `MateBeltDim`), `CreateBeltPart=False` (the roller-chain pattern stays the
   visual) → `feat = fm.CreateFeature(data)` (raw data, late-bound fm).

**The coupling ratio lives in the MATE, not the definition.** `BeltMate1`
(`MateBeltDim`) carries plain dimensions `D1`/`D2` — the per-pulley diameters
whose quotient IS the coupling. With FACE members SW bakes the picked faces'
diameters into them at creation (tooth-TIP ring 28:52 = 0.538 on the m2
sprockets, a ~7.7% feed error) and **never re-derives them**. Measured live,
ALL of these commit green and leave the coupling at 0.5385:

- `PulleyDiameters` post-create + early-bound `ModifyDefinition` (the official
  C# example's route — the definition reads back the new values; the belt PATH
  sketch even honours them, radii at pitch 0.012/0.024 m; the mate does not).
- `ModifyMemberParameters` (returns True, inert).
- Deleting + re-authoring with `EngageBelt` toggled (re-bakes from faces).
- Writing the mate's own `D1`/`D2` `IDimension.SystemValue` directly (write
  verified by read-back, rebuild forced — coupling unchanged; the mate solves
  from cached internals, not its display dims).

**The fix: DATUM-AXIS pulley members.** Select each sprocket's `Axis1` via
`SelectByID2("Axis1@<comp>@<asm>", "AXIS", …)` → `GetSelectedObject6(1, -1)` →
pass those entities as `PulleyComponents`. An axis has no diameter to steal, so
the typed `PulleyDiameters` drive the mate exactly. Measured on the real
paper-drive: T12 +30.00° → T24 +15.00°, **ratio +0.5000, same sense**
(`probe_belt_axis_members.py`). Productised in the adapter as
`BeltChainParameters.pulley_member_axes` (submodule #79); post-create the
adapter walks the MateGroup for the `MateBeltDim` and fails loud unless its
D1/D2 multiset equals the request — the only meaningful verification.

**COM traps (still real):** `PulleyDiameters` getters return **[]** until
`typed.AccessSelections(model, None)`; `ModifyDefinition` must be called on an
EARLY-bound IFeature (late-bound mismarshals → False).

**Driving a coupled sprocket in a SCRATCH probe fails (unresolved):** a temp
plane-plane ANGLE driver in the minimal two-sprocket assembly is created in
hard error 1 IN PLACE, both flip sides — from parallel AND 15°-off-apex rest
poses. The same `angle_driver` drives the FULL paper-drive model fine, so
measure coupling ratios on the real model ([[park-driver-singularities]]).

**comtypes NOT needed** (its nulls were the same input bugs; it also can't
unmarshal `GetComponents`' SAFEARRAY — see `probe_belt_comtypes.py`).

**Rack-pinion gotcha (shipped with this work):** the rack-pinion mate needs
DISTINCT entity marks (rack=64, pinion=128); the adapter's `_MATE_DEFAULT_MARKS`
had no `rack_pinion` entry so both got mark 1 and `CreateMate` returned null.
Fixed in the adapter (submodule #78).

**blank_sketch:** `IModelDoc2::BlankSketch` exposed as an adapter method to hide
construction sketches (the chain-path spline + the belt's own generated sketch).

See [[paper-drive-kinematic-probe]] for the ratio/sense verification wired into
`verify:kinematics`, and [[default-free-dof-park-drivers]] for the freed crank
spin.
