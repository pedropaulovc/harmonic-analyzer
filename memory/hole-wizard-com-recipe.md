---
name: hole-wizard-com-recipe
description: Hole Wizard COM — full working recipe (cad/scripts/_holes.py) + the InitializeHole-blind session-poison trap, early-bind-the-definition trick, HoleWizard5 value slots
metadata:
  type: reference
---

Everything needed to author native `HoleWzd` features from Python lives in
`cad/scripts/_holes.py` (`wizard_holes` + `HoleSpec`), probe-verified on this
seat by `diagnostics/diag_hole_wizard.py` (6/6 volume-exact, 2026-07-11).
Traps that cost 8 probe rounds — do not re-learn:

- **`InitializeHole(..., swEndCondBlind)` is BROKEN on this build**: it cuts a
  garbage default (~Ø54 through a 60mm block for a #4-40) **and poisons the
  wizard session** — SUBSEQUENT holes silently inherit corrupted diameters
  (a "#47" number drill cut Ø1.41 instead of 1.994). Reproducible. Blind holes
  must go through the positional `HoleWizard5` instead; through-all /
  through-next via `CreateDefinition(25)` → `InitializeHole` → `CreateFeature`
  work exactly.
- **HoleWizard5 value slots** (official 2019 API remarks): taps take
  V1=thread depth, V6=bottom drill angle (RADIANS, 118°=2.0595), V7=cosmetic
  thread type (1=with callout), V8=thread end condition; plain holes take
  V1=screw fit, V2=drill angle; cbores take V1/V2=cbore dia/depth. `Length`
  param = -1 for non-slots. ThreadClass ("1B"/"2B") is ANSI-inch only.
- **Early-bind `IWizardHoleFeatureData2`** (gen_py class via
  `sw_type_info._wrapper_module`, NOT `CastTo` — 'Invalid index'): late-bound
  double reads return 0.0 and several writes silently drop. Even early-bound,
  TABLE-derived dims read 0.0 — pin expected cut diameters from the database
  dump instead (`TAP_DRILL_MM`/`CLEARANCE_MM`/`NUMBER_DRILL_MM` in _holes.py,
  regenerate with `diagnostics/diag_hole_wizard_tables.py`).
- **Property knobs that actually work** (post-create `GetDefinition` →
  `AccessSelections(model, None)` → set → `ModifyDefinition(defn._oleobj_,
  model, null_callout())`): `HoleFit`, `CounterBoreDiameter/Depth`,
  `ThruHoleDiameter` (the cbore through-hole knob — `HoleDiameter` writes are
  IGNORED there). `EndCondition`/`HoleDepth`/`Depth` writes no-op — hence the
  HoleWizard5 blind path. Early-bound calls take plain `None` for null
  dispatch params (a `null_callout()` VARIANT throws "Python instance can not
  be converted"); late-bound calls need the VARIANT.
- **Multi-point**: one auto placement point per feature; edit the placement
  sketch (`SetCoords` + `CreatePoint` via `ModelToSketchTransform`) — the
  rocker-arm-support foot-tap idiom, shared by both creation paths.
- **Create wizard holes BEFORE face-exploding features**:
  `find_planar_face` walks EVERY face of the body with 2-3 COM roundtrips
  each; after the nameplate's engraving cut (112 buffered-ribbon grooves →
  thousands of wall/floor faces) the walk ran >20 min — SolidWorks pegged
  one core servicing the calls, python ~1.5% CPU marshaling, no dialog.
  Looked like a wizard-solve hang but never reached the wizard (the
  post-select phase log never fired); drilling from the opposite pristine
  face changes nothing (the walk is normal-agnostic). Fix = feature order:
  cut holes while the body is prismatic (~15 faces). `find_planar_face`
  now logs the face count and warns >500; `wizard_holes` logs each phase
  (`face selected` / `feature created` / `points placed, rebuilding`) so a
  hang names its phase.
- **Cylindrical faces WORK (radial cross-holes)**: select the cylinder face
  object → same `CreateDefinition(25)`/`InitializeHole`/`CreateFeature`
  through path → the placement is a **3D sketch** whose single point takes
  MODEL coords directly (`SetCoords`, no ModelToSketchTransform). Probe
  `diag_hole_wizard_cyl.py`: #9 through Ø12 shaft removed 228.39 vs 228.41
  analytic. Production helper `_holes.wizard_hole_on_cylinder` (through-all,
  single point, largest-cylinder-face pick); diametral removal volume =
  `cross_hole_volume_mm3` (numeric perpendicular cylinder∩cylinder).
- Table enumeration: `swApp.GetHoleStandardsData(type)` early-bound gives
  every ANSI-inch size token + diameter ([[fastener-policy-us-customary]]).
