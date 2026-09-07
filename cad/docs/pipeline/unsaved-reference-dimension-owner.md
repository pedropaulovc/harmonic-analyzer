# Unsaved reference-dimension owner evidence

The first lever factory run at `eaf09464932b2c85adb8b17f3c9aa30160c3f69f`
failed on the separately corrected late-bound `GetAnnotation` call. Its failure
capture was partial because the attachment diagnostic assumed every drawing
reference dimension had a saved drawing path:

- Receipt: `cad/out/reports/datum-policy-gyx30dw5/pilot.json`
- SHA-256: `cb52ce7b8639dcda4abff317648e019b96416a0f805d2d3d1f1c864ee7822bff`
- Raw drawing state: path `""`, title `"Draw90 - Sheet1"`.
- Rejected native dimension: `RD1@Drawing View1@Draw90.Drawing`.
- Both `before.semantics` and `after.semantics` rejected that owner; the original
  primary failure remains unchanged. Recipe duration was 25.78618529997766 s,
  not a successful build or performance comparison.

The new branch applies **only** to drawing-reference dimensions with an exactly
empty native `GetPathName`. It requires the supplied drawing to be the exact
active native drawing, the annotation owner to be the exact view from that
drawing's existing inventory, and the display dimension's `GetAnnotation`
roundtrip to return that annotation. Missing, wrong or unknown native identities
fail before accepting a name.

`GetTitle` supplies the document name. Only its exact current native sheet suffix
(`" - " + GetCurrentSheet().GetName()`) and the documented optional `.SLDDRW`
extension may be removed. There is no generic dash split or arbitrary
`.Drawing` suffix fallback. The complete native dimension name must equal
`Name@exact view name@derived title owner.Drawing`. Raw title/sheet/view/derived
owner are retained under `dimension_observations[].unsaved_owner`.

Bundled official documentation was read for `IModelDoc2.GetPathName/GetTitle`,
`ISldWorks.ActiveDoc/IsSame`, `IAnnotation.Owner/OwnerType`,
`IDisplayDimension.GetAnnotation`, `IDimension.FullName`, `IView.GetName2`,
`IDrawingDoc.GetCurrentSheet`, and `ISheet.GetName`, with the native drawing
dimension traversal example. The exact `"Draw90 - Sheet1"` title shape is backed
by this receipt, not generalized from an undocumented window-title parser.

Existing saved-owner tests deliberately reject foreign `.Drawing`/`.Part`
owners; they are unchanged. The failure-retention test deliberately injects an
arbitrary semantic error and remains unchanged, because retaining partial
evidence on a real diagnostic failure is still required. Source-part dimensions
in unsaved drawings continue using the exact saved source-part identity.

The new fail-first fixture reproduced the retained owner rejection before the
fix. Focused tests cover valid title forms, wrong title/view/sheet/source owner,
missing native identities, display substitution, unchanged saved-path behavior,
and equivalent saved/unsaved semantic normalization without losing view/content
checks. No COM invocation, original artifact write, VIEW observer change or
type46 change is part of this slice. Native recovery of the missing failure
semantics remains to be observed in a parent-granted run.

Verification: 254 focused/adjacent offline tests passed in 6.03 s, including the
unchanged failure-retention, MODEL shaft, VIEW and silhouette suites. Ruff and
`git diff --check` passed.
