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

## Status 2026-07-13

**[BUILD] tier committed** on branch `pedro/zero-late-binding` (main repo, HEAD
338651e0), stacked on **#271** (`agent/pipeline-performance-v020`).

**BLOCKED on #271 base regression (NOT ours).** #271 carries a rectangle-sketch
refactor (`Keep native rectangles for non-square profiles` / `Limit rectangle
dimension repair to square sketches` / `Define centered rectangles without
sketch warnings` / `Center rectangles on sketch origins`) that leaves **slot/bar
sketches under-defined** → 16 parts fail `sketch not fully defined
(state='under_defined')` (support_bar, cone_pivot_screw, swing_stop_screw,
wheel_bar, foot_screw, cone_tip_pinch_screw, arbor_pedestal, top_frame, …). PROOF
it is #271's, not the rebinds: `git diff #271-tip..HEAD -- cad/scripts/_common.py`
is ONLY the one GetBodies2 line — my sketch code is byte-identical to #271's; the
same parts build green on main. The build dies in the PART phase, so a full
zero-fallback validation is impossible until #271 is fixed.
**User decision (2026-07-13): poll #271 for further commits; continue task #7
where possible until then** (do NOT rebase onto main, do NOT fix #271 myself). A
persistent Monitor polls `origin/agent/pipeline-performance-v020` every 5 min.

**The map UNDER-COUNTED — real fallback surface is bigger.** The authoritative
part-tier inventory (from build b0iqi2kmu, part phase only — assemblies/verify/
drawings never ran) shows the bulk of remaining stragglers live in the SUBMOD
adapter part-path, missed by the main-repo grep:
IModelDoc2.FeatureByName ×101, IModelDoc2.ViewZoomToFit2 ×87 (case→`ViewZoomtofit2`,
pywin32_adapter.py:1980 part-image zoom), IPartDoc.EditRebuild3 ×84,
ISketchArc.Select2/Select4 ×72 each + ISketchLine.Select2/Select4 ×16 each (sketch
segment selection), IModelDoc2.GetSaveTime ×12, GetFirstView/CreateDrawViewFromModelView3
×6 each, GetBodies2 ×3, IAssemblyDoc.{SelectionManager,EditRebuild3,ClearSelection2}
×3 each. Re-derive the FULL surface only once a green full build (post-#271-fix)
reaches assemblies+verify+drawings.

**[SUBMOD] tier DONE** — submodule branch `pedro/zero-late-binding` (off
`personal`/88819f9), **draft PR pedropaulovc/SolidworksMCP-python#87** → base
`personal`. All 25-member SUBMOD sites rebound (mapped by two agents): FeatureByName
→ doc-typed via new `sw_type_info.early_bound_doc(obj)` (GetType→IPartDoc/
IAssemblyDoc/IDrawingDoc); GetBodies2→IPartDoc; sketch Select2/Select4→**ISketchSegment**
(NOT IEntity — DISPID 65556 collides w/ ISketchSegment.Select2); ViewZoomToFit2→case
`ViewZoomtofit2`; EditRebuild3/ClearSelection2/SelectionManager→IModelDoc2 handle;
GetComponents/GetComponentByName/CreateMate/CreateMateData→IAssemblyDoc; drawing verbs
→IDrawingDoc via a `_ddoc` helper (keep `_draw()` IModelDoc2 for EditRebuild3/
ClearSelection2); GetSaveTime→SummaryInfo(9). **725 adapter tests pass, ruff clean.**
Gotcha fixed: a function-local `from .. import sw_type_info` shadowed the new
module-level import → UnboundLocalError; removed the redundant local. Mock convention:
objects flowing through `early_bound` need `_oleobj_ = None` to pass through.

**#271 regression flagged**: commented on PR #271 (issuecomment-4958691999) with the
16-part slot/bar under_defined evidence.

**STILL TODO (all need #271 green / a full build):** [DIAG] tier (~62 hand-run
`cad/scripts/diagnostics/` sites, non-gate); flip `_fallback_subclass.__getattr__`
→ **RAISE AttributeError** (must raise AttributeError specifically — `getattr(obj,
name, default)` guards depend on it, e.g. pywin32_adapter GetComponentByName);
NOTE the flip also affects every `_flag_feature_methods(obj, iface, *methods)` site
whose flagged method isn't on `iface` (landmines — a full green build's zero-fallback
grep is the only complete checklist); motion.py's TLB-absent methods use
`flag_method_names` on a RAW dispatch (NOT `_fallback_subclass`), so the flip does
not touch them; bump submodule pointer + final full build with ZERO `early-bound
fallback:` warnings.
