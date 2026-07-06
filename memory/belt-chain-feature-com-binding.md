---
name: belt-chain-feature-com-binding
description: SW Belt/Chain assembly feature IS creatable in pywin32 (swFmBeltAndChain=119) — the pulley members must be cylindrical FACES, not component objects; passing components makes CreateFeature silently null
metadata:
  type: reference
---

## Belt/Chain assembly feature — WORKS in pywin32 (2026-07-05)

For the paper-drive operational-DOF rework (couple the T12 crank sprocket ↔ T24
knob sprocket so the crank drives the paper feed). Probe:
`cad/scripts/diagnostics/probe_belt_feature.py` (WORKING). Extends
[[chain-component-pattern]].

> **Lesson repeated from the chain pattern (same morning mistake): do NOT conclude
> "the API can't do this from Python."** I first passed the wrong INPUT and wrongly
> declared it infeasible in both pywin32 and comtypes. The fix was the pulley member
> TYPE, per [[verify-assumptions-live-sw]] / the C#/VB.NET examples. Everything C#
> can do here, pywin32 does.

**Enum:** `swFeatureNameID_e.swFmBeltAndChain = 119` (verified via .NET reflection on
`SolidWorks.Interop.swconst.dll`; `swFmLocalChainPattern=112` cross-checked). The
offline docs list names but no ints. **NOT 92** (a wrong value → CreateDefinition null).

**The one thing that mattered — PulleyComponents must be cylindrical FACES, not the
component objects.** The C#/VB.NET help examples select pulley faces (`SelectByRay`
→ `GetSelectedObject6`). Passing the `IComponent2` objects makes the definition
INVALID, so `CreateFeature` returns null **silently** — and the property setters
still return "success" (the getters/setters lie pre-commit, so "all 7 props set =
True" proves nothing). Switching to a Z-axis cylindrical face per sprocket made
`CreateFeature` return the feature (`Belt1`) on the very first (simplest) strategy.

**Working pywin32 recipe (verified — `created=True name='Belt1'`):**
1. **Get each pulley's cylindrical FACE** (its rotation axis). Per component:
   `comp.GetBody()` → `body.GetFaces()`; for each face `face.GetSurface()`, keep the
   ones where `surf.IsCylinder()` and `surf.CylinderParams` axis ≈ Z (`abs(az)>0.9`);
   pick the largest radius. (Flag each dispatch: IComponent2 / IBody2 / IFace2 /
   ISurface — `GetBody`/`GetFaces`/`GetSurface`/`IsCylinder` are methods;
   `CylinderParams` is a property = 7 doubles `[ox,oy,oz, ax,ay,az, r]`, metres.)
   The tip-cylinder is fine (T12 r=0.014, T24 r=0.026); `PulleyDiameters` sets the
   effective belt diameter separately.
2. `data = fm.CreateDefinition(119)` → non-null.
3. `typed = sw_type_info.early_bound(data, "IBeltChainFeatureData")`; set on `typed`:
   `PulleyComponents = com_variant.dispatch_array([face_a, face_b])`,
   `PulleyDiameters = double_array([d_a, d_b])` (metres, pitch dia),
   `FlipSides = VARIANT(VT_ARRAY|VT_BOOL, [False, False])`,
   `BeltLocationPlane = <IRefPlane>` (from `model.FeatureByName("Front Plane")` →
   `.GetSpecificFeature2()`; plane is normal to the pulley axes = Z here),
   `UseBeltThickness=False`, `CreateBeltPart=False` (we keep the
   [[chain-component-pattern]] link chain for the visual), `EngageBelt=True`
   (creates the belt MATES that couple pulley rotation — the operational point).
4. `feat = fm.CreateFeature(data)` — pass the RAW `data` (typed shares its oleobj),
   late-bound `fm`. Returns the belt feature. (early_bound `fm` / passing `typed`
   also fine; the raw/late combo is simplest.)

**comtypes NOT needed** (it also nulled — but that was still the component-input bug;
it has its own friction anyway: object-typed returns come back as generic `_Dispatch`
needing per-call `QueryInterface`, and it can't unmarshal `GetComponents`'
`SAFEARRAY(VT_DISPATCH)` return, `KeyError 9`). See `probe_belt_comtypes.py` for that
dead end.

**SHIPPED in the real build (2026-07-05).** Wrapped as an adapter method
`insert_belt_chain` (submodule `SolidworksMCP-python`, branch `pedro/belt-chain-feature`)
+ used in `build_paper_drive_assembly.py`: T12/T24 sprockets freed (`ground=False` +
axis-to-plane revolute via `_sprocket_revolute`, spin free), then the belt feature
couples them (EngageBelt, CreateBeltPart=False — the roller-chain pattern is the
visual). The crank T12 spin is the freed operational DOF (deferred park driver,
`build_lock.yaml` `paper_drive: free`); a rack-pinion mate feeds the platen off the
knob axis at the NET through-train travel (documented kinematic cheat across the
Appendix C #8 engage gap — geometry unchanged). Build GREEN: belt OK (~124s),
necessity gate `7 under-constrained >= 1 free DOF`, interference 0. See
[[default-free-dof-park-drivers]].

**Gotcha found doing this — the rack-pinion mate needs DISTINCT entity marks**
(rack=64, pinion=128; SW *Create Rack and Pinion Mate* example). The adapter's
`_MATE_DEFAULT_MARKS` had NO `rack_pinion` entry, so both entities got mark 1 and
`CreateMate` returned null ("CreateMate failed for rack_pinion mate"). Fixed in the
adapter (per-index marks by entity order). This path had no prior use — latent bug.

**blank_sketch:** exposed `IModelDoc2::BlankSketch` as an adapter method to hide
construction sketches (the chain-path spline + the belt's own generated sketch).
