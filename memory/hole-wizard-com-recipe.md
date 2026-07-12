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
  model, null_callout())`): `CounterBoreDiameter/Depth`, `ThruHoleDiameter`,
  `HoleDiameter`. `EndCondition`/`HoleDepth`/`Depth` writes no-op — hence the
  HoleWizard5 blind path. Early-bound calls take plain `None` for null
  dispatch params (a `null_callout()` VARIANT throws "Python instance can not
  be converted"); late-bound calls need the VARIANT.
- **`HoleFit` is a NO-OP on a plain (type-2) clearance hole** — the API applies
  it to counterbore/countersink features ONLY (per the
  `IWizardHoleFeatureData2.HoleFit` remarks). So a plain clearance hole ships
  the NORMAL-fit diameter regardless of `spec.fit`: probe 2026-07-11 a 1/4
  "close" hole still cut Ø7.137 (normal), not Ø6.756. To set a plain hole's
  fit, FORCE the pinned dia via BOTH `HoleDiameter` AND `ThruHoleDiameter` —
  on a plain hole the DRIVING knob is `ThruHoleDiameter`; a `HoleDiameter`-only
  write is silently dropped (setting only `HoleDiameter` still cut 7.137;
  setting both cut 6.756). `wizard_holes` does this ONLY for non-normal fits;
  the initialized normal fit must remain untouched. (On a cbore the through-
  hole knob is likewise `ThruHoleDiameter` — `HoleDiameter` ignored.)
- **Never redundantly write a NORMAL clearance diameter.** Platen-guide's #4
  hole table exposed the failure: every B row showed the correct `Ø3.25 THRU
  ALL` plus bogus `Ø0.00 X 0°, FAR SIDE`. An isolated native repro is
  `diagnostics/repro_hole_table_zero_diameter.py`: A1-A4 use a #4 normal
  clearance with an explicit table-equivalent `HoleDiameter=3.251` override
  and reproduce the bad second line; B1 is a native #30 drill and stays clean.
  Live definition state before the fix was contradictory: `Type=26`
  (`swHoleThruCounterSinkBottom`), `FarSideCounterSink=False`, far diameter /
  angle `-1/-1`. Pedro's decisive UI experiment — enable then disable **Far
  side countersink** — normalized it to `Type=25` (`swHoleThru`), far-side
  false, far dimensions `0/0`, and the table immediately became clean. The
  recorded VBA macro did not include PropertyManager edits, so COM state was
  the useful evidence. The documented `FarSideCounterSink` and `Type` setters
  are get-only in this API build (the old official toggle example is stale):
  `FarSideCounterSink=True` + valid dimensions + `ModifyDefinition` returned
  success but the flag stayed false. Root cause was not missing UI automation:
  the redundant `HoleDiameter` + `ThruHoleDiameter` ModifyDefinition itself
  converted a correctly initialized type-25 normal hole into type 26. Fix:
  skip the edit flow entirely for normal clearance fit; retain explicit writes
  only for non-normal fits or deliberate overrides. Untouched #4 normal reads
  `ThruHoleDiameter=0.0032639 m` (the #30 drill size), so pin
  `CLEARANCE_MM[("#4", "normal")]=3.264`. Production rebuild proved type 25,
  far-side false, Ø3.2639 geometry, volume green; regenerated platen-guide
  drawing shows B1-B4 only `Ø3.26 THRU ALL`.
- **What did not fix the phantom line:** custom/manual table text (rejected as
  a hack); ANSI letter/number display; selecting the face or explicit visible
  rims; reversing the drilling direction; flipping Front/Back drawing views;
  setting countersink diameters/angles to `-1`; writing `Diameter`; pre-create
  sentinel values; or trying the get-only far-side boolean setter. These
  changed presentation or no-op'd because the corrupt type-26 subtype remained.
- **Multi-point**: one auto placement point per feature; edit the placement
  sketch (`SetCoords` + `CreatePoint` via `ModelToSketchTransform`) — the
  rocker-arm-support foot-tap idiom, shared by both creation paths. Wrap the
  point placement in `SketchManager.AddToDB=True`: a point authored within
  snap distance of a reference otherwise INFERENCE-SNAPS to it and picks up a
  coincidence that `EditRebuild3` re-applies, MOVING the drilled hole. Bit
  support-bar's x=-2 bracket hole — it snapped to the origin (x=0), the
  position-independent volume check still PASSED, and the misplaced hole only
  surfaced as a 43 mm^3 screw/bar interference in the paper_drive assembly.
  Holes far from any reference never snap (see
  [[oblique-views-break-on-axis-occlusion]] for the sibling inference class).
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
