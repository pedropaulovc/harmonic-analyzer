---
name: hole-wizard-drawing-locators
description: How to make a SolidWorks Hole Wizard hole's X/Y LOCATION dims parametric AND import to a drawing (the swInsertHoleWizardLocationDimensions bit)
metadata:
  type: reference
---

Making a Hole Wizard tapped hole's position show as X/Y locator dimensions on a
drawing — model-driven, no drawing-authored dims. Verified live on pen-v-block
(SW 2026, PR #213). Two independent pieces are BOTH required:

1. **Dimension the wizard's OWN positioning sketch** (the model side). The
   data-object flow (`CreateDefinition(swFmHoleWzd)` → `InitializeHole` → select
   FACE → `CreateFeature`) drops the location point UN-dimensioned (an under-defined
   pick), so the hole position is neither parametric nor drawable. You CANNOT place
   the wizard on a pre-dimensioned normal sketch point — `CreateFeature` REJECTS a
   pre-selected `SKETCHPOINT`/`EXTSKETCHPOINT` (returns null; the wizard always makes
   its own positioning sketch). Instead, after creating the hole by FACE, reach into
   the `HoleWzd` feature's sub-features, find the positioning sketch (the sub
   `ProfileFeature` holding exactly ONE point — the profile sketch has ~6), enter
   `EditSketch` on it, and dimension that point (anchor to origin). This is
   `adapter.edit_hole_position(hole_name, rename_sketch)` in the submodule's
   `manufacturing.py`. Rename the sub-sketch first so its dims are addressable by a
   stable name; the dims come out as `D1@<name>`/`D2@<name>` (horizontal then
   vertical for a general off-axis point) and can be equation-driven by raw full
   name (`_feature_by_name` CANNOT find an absorbed sub-sketch, so [[parametric-naming-round-trip]]'s
   `SketchDims.apply` won't work — drive them by raw `D1@<name>` instead).

2. **Set `swInsertHoleWizardLocationDimensions` (0x20000)** in the
   `InsertModelAnnotations3` `Types` mask (the drawing side). The wizard's location
   dims live on that ABSORBED positioning sketch, which the marked (0x8000) /
   not-marked (0x80000) masks NEVER reach — verified that even `HiddenFeatureDims=True`
   pulls other hidden wizard dims but not these. This dedicated bit is the ONLY way
   to import them. `insert_model_dims` in the submodule's `drawing.py` now always ORs
   it in (no-op when the model has no dimensioned wizard holes). There is also
   `swInsertHoleWizardProfileDimensions` = 0x10000 for the cross-section dims.

**Why:** the user (SW expert) correctly doubted the fallback claim that locators had
to be authored in the drawing. The real blocker was the missing import bit, not an
inherent SW limitation. The SW "Model Items" PropertyManager exposes these as the
"Hole Wizard Locations" / "Hole Wizard Profiles" toggles — the enum ints came from
the doc bundle's `swInsertAnnotation_e` (values ARE listed there, unlike the
`swFeatureNameID_e` Hole Wizard ints which needed interop-DLL reflection — see
[[developing-solidworks]] flow).

**How to apply:** any future part drawing that must show a Hole Wizard hole's
location reuses both halves — the part build calls `edit_hole_position` + anchors +
drives; the drawing gets locators for free because `insert_model_dims` carries the
bit. Related: [[default-free-dof-park-drivers]] is unrelated; [[verify-sw-api-with-research]]
(this was solved by web-researching the SW "Model Items" help + macro-recorder intent).
