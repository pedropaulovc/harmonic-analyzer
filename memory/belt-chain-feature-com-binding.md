---
name: belt-chain-feature-com-binding
description: SW Belt/Chain feature via pywin32 — pulley members are cylindrical FACES; PulleyDiameters getters return [] until AccessSelections; pre-create diameter sets no-op (SW re-derives from faces) — enforce post-create via early-bound ModifyDefinition + read-back
metadata:
  type: reference
---

## Belt/Chain assembly feature — the full pywin32 recipe (2026-07-05/06)

For the paper-drive operational-DOF rework (couple the T12 crank sprocket ↔ T24
knob sprocket so the crank drives the paper feed). Working probes:
`cad/scripts/diagnostics/probe_belt_feature.py` (creation),
`probe_belt_diameter.py` (diameter enforcement + measured coupling ratio/sense).
Extends [[chain-component-pattern]].

> **Lesson, three times now: do NOT conclude "the API can't do this" from a
> null/empty/False return.** (1) Passing the wrong pulley member TYPE made
> CreateFeature null → "infeasible in pywin32" (wrong). (2) Reading
> `PulleyDiameters` without `AccessSelections` returns EMPTY and the pre-create
> setter no-ops → "EngageBelt silently ignores PulleyDiameters, use a gear mate"
> (codex #189 round-5 — wrong, and the gear mate also REVERSES the rotation
> sense a chain preserves). (3) Late-bound `ModifyDefinition` returns False →
> looks like "modification unsupported" (wrong — early-bind the IFeature).
> Per [[verify-assumptions-live-sw]]: everything the C# examples do, pywin32 does.

**Enum:** `swFeatureNameID_e.swFmBeltAndChain = 119` (verified via .NET reflection;
NOT 92 — a wrong value → CreateDefinition null).

**Creation (unchanged, proven):**
1. **Pulley members = cylindrical FACES** (each pulley's largest cylinder about
   the rotation axis — on a gear/sprocket that is the tooth-TIP face ring), NOT
   the IComponent2 objects (components → CreateFeature silently null, and the
   pre-commit setters still report success).
2. `data = fm.CreateDefinition(119)` → `typed = sw_type_info.early_bound(data,
   "IBeltChainFeatureData")` → set `PulleyComponents` (dispatch_array of faces),
   `FlipSides`, `BeltLocationPlane` (IRefPlane normal to the axes),
   `EngageBelt=True` (the coupling mates — a `BeltMates1` folder holding a
   `BeltMate1` of type `MateBeltDim`), `CreateBeltPart=False` (the roller-chain
   pattern stays the visual) → `feat = fm.CreateFeature(data)` (raw data,
   late-bound fm). ~2–5 min solve on the real assembly.

**Diameters — the part round-5 got wrong.** SW derives each pulley's belt
diameter from the picked FACE when the definition commits (tip ring 28:52 =
0.538 on the m2 sprockets), and the `PulleyDiameters` you set pre-create does
NOT survive the commit. Enforce POST-create (the official
`Create_Belt_Chain_Feature_Example` route), with two COM traps:

- **Getters are AccessSelections-gated**: `GetDefinition()` →
  `typed.PulleyDiameters` reads **[]** until `typed.AccessSelections(model,
  None)` — an un-accessed read looks exactly like "the property doesn't work".
- **`ModifyDefinition` must be called on an EARLY-bound IFeature**
  (`sw_type_info.early_bound(feat, "IFeature")`) — the late-bound flagged call
  mismarshals and returns False. (Same family as the chain-pattern
  CreateFeature null.)

Recipe (now inside the adapter's `insert_belt_chain`, fail-loud):
`GetDefinition` → `AccessSelections` → read (skip if already right, then
`ReleaseSelectionAccess`) → set `PulleyDiameters = double_array(metres)` →
`feat_eb.ModifyDefinition(data, model, None)` → fresh `GetDefinition` +
`AccessSelections` → read-back must equal the request (raise otherwise) →
`ReleaseSelectionAccess`. ModifyDefinition re-solves the belt from the new
diameters; the enforcement read-back is PROVEN live (scratch probe, 2026-07-06:
requested [0.024, 0.048] m confirmed post-ModifyDefinition, feature solved
green). The resulting coupling ratio + same-sense rotation are asserted on the
REAL paper-drive by `verify:kinematics` (`paper-drive:crank-feed`).

**Driving a coupled sprocket in a SCRATCH probe fails (unresolved):** a temp
plane-plane ANGLE driver in the minimal two-sprocket assembly is created in
hard error 1 IN PLACE, both flip sides — from parallel AND 15°-off-apex rest
poses. The same `angle_driver` drives the FULL paper-drive model fine (twice),
so measure coupling ratios on the real model via `verify:kinematics`
([[park-driver-singularities]]). The scratch probe's durable result is the
diameter enforcement itself: `insert_belt_chain` completed with the fail-loud
read-back green (requested [0.024, 0.048] m confirmed post-ModifyDefinition).

**comtypes NOT needed** (its nulls were the same input bugs; it also can't
unmarshal `GetComponents`' SAFEARRAY — see `probe_belt_comtypes.py`).

**Rack-pinion gotcha (shipped with this work):** the rack-pinion mate needs
DISTINCT entity marks (rack=64, pinion=128); the adapter's `_MATE_DEFAULT_MARKS`
had no `rack_pinion` entry so both got mark 1 and `CreateMate` returned null.
Fixed in the adapter (submodule #78); diameters enforce is submodule #79.

**blank_sketch:** `IModelDoc2::BlankSketch` exposed as an adapter method to hide
construction sketches (the chain-path spline + the belt's own generated sketch).

See [[paper-drive-kinematic-probe]] for the ratio/sense verification wired into
`verify:kinematics`, and [[default-free-dof-park-drivers]] for the freed crank
spin.
