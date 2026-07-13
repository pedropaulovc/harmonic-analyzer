---
name: zero-late-binding-task
description: In-progress task #7 — eliminate ALL late-binding fallback (flip _fallback_subclass.__getattr__ to RAISE); the 25-site empirical surface + plan
metadata:
  type: project
---

Follow-on to the early-bound COM migration (PRs #86/#269/#278 merged 2026-07-13).
User decision: **zero late binding** — convert `_fallback_subclass.__getattr__`
in `SolidworksMCP-python/src/solidworks_mcp/adapters/sw_type_info.py` (~line 379)
to **RAISE** on any off-interface member, AFTER every call site binds the correct
most-derived interface. No silent late-bound fallback remains. Do it on a
`pedro/<topic>` branch off `personal`; validate with a full cold `doit -n 4`.

**The empirical fallback surface** — 25 unique `(interface.member)` sites, 642
occurrences, extracted from the green full-build log via
`grep "early-bound fallback:"`. Re-derive anytime by grepping a build log. Each
must be rebound to the member's real owning interface:

- **Drawing → IDrawingDoc** (mis-bound as IModelDoc2): `ActivateSheet`,
  `ActivateView`, `AddHoleCallout2`, `CreateDrawViewFromModelView3`,
  `GetCurrentSheet`, `GetFirstView`, `InsertModelAnnotations3`, `SetupSheet6`.
- **Assembly → IAssemblyDoc**: `GetComponents`, `GetComponentByName`,
  `CopyWithMates2`, `CreateMate`, `CreateMateData` (all seen as `IModelDoc2.*`).
- **IAssemblyDoc.{ClearSelection2, EditRebuild3, SelectionManager} → IModelDoc2**
  (these are ModelDoc members accessed on an assembly-bound object).
- **Part → IPartDoc**: `IModelDoc2.GetBodies2`.
- **EditRebuild3 → IModelDoc2** (both `IAssemblyDoc.EditRebuild3` and
  `IPartDoc.EditRebuild3` sites).
- **Entity selection → IEntity / ISketchSegment**: `IFace2.Select2`,
  `ISketchArc.Select2/Select4`, `ISketchLine.Select2/Select4`.
- **Case / owner mismatches** (member IS declared but name differs, so
  `__getattr__` fires on the miss): `IModelDoc2.ViewZoomToFit2` (makepy spells it
  `ViewZoomtofit2`), `IModelDoc2.FeatureByName`, `IModelDoc2.GetSaveTime` — verify
  each real name/owner in `_generated/sldworks_2026.py` and `./types/` before
  rebinding; a case fix may suffice.

**Approach:** use `_early_bound(obj, "<Iface>")` at each site (repo build scripts
use the `_common._early_bound` shim; adapter uses `sw_type_info.early_bound`).
Result MUST be reassigned. Determine each owning interface from the developing-
solidworks `./types/` docs + the generated wrapper, not by guessing. After all
sites are rebound and a full build is clean with ZERO `early-bound fallback:`
warnings, flip `__getattr__` to raise `AttributeError`/loud error. See
[[load-bearing-claims-need-repro]] and [[verify-assumptions-in-live-sw]].
Merge once gates clear (build green + Codex happy + visual). fable = reviewer.
