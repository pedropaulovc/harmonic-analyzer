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

**#271 "regression" was WRONG — retracted.** I claimed #271's rectangle commits
broke 16 slot/bar parts with `under_defined`, from a failing build + "byte-identical
sketch code" reasoning — WITHOUT ever running plain #271 as the positive control. The
user ran #271 @050d0b6 + submodule 88819f9 → green (exit=0, 0 `under_defined`). A
clean re-run on my side ALSO showed 0 `under_defined`: the original failure was a
DIRTY-WORKTREE artifact (the prior session's half-applied `_register_fallback_classes`
edit). Retracted on PR #271. LESSON (see [[negative-result-needs-positive-control]],
[[no-untested-failure-assumptions]]): run the positive control before declaring a
shared component broken. **#271 is now MERGED to main** — the "blocked" premise is
fully gone.

**REAL bug the clean build found — my SUBMOD regression (FIXED).** The clean 16-part
build failed on `add_sketch_dimension: Failed to select primary entity 'Line_1.start'`
— my `select_entity` blanket `early_bound(entity,"ISketchSegment")` rebind broke
POINT selection. Sketch POINTS are `ISketchPoint`, which declares Select/Select2/
Select4 at DISPIDs **7/19/25** — nothing like ISketchSegment (65545/65556/65562) or
IEntity (65543/65552/65556); forcing ISketchSegment on a point calls a DISPID its
dispinterface lacks → select fails. Fix: `select_entity` rebinds ONLY derived segments
(`_DERIVED_SKETCH_SEGMENT_INTERFACES`) to ISketchSegment; points pass through as
ISketchPoint. `_resolve_entity_ref`/`_resolve_origin_point` now bind resolved points
to ISketchPoint at the source. **CRITICAL LESSON: the 725 mock tests did NOT catch
this** (mock adapter never exercises real COM interface binding) — the SUBMOD tier is
only truly validated by a REAL doit build, not pytest.

## Status 2026-07-13 (cont.) — the under_defined was a SESSION PREFERENCE, not my code

After the point-fix the 16-part build STILL failed `under_defined` (foot/slot/bar
sketches). I isolated it decisively: built `arbor_pedestal` with submodule **88819f9**
(the user's exact green submodule) + my main → STILL `under_defined`. So NOT my
submodule. Then confirmed my main commit 338651e0 does not touch the sketch path
(its only `_common.py` change is `apply_color`'s GetBodies2, which runs long after the
foot sketch) and `define_centered_rectangle` is byte-identical to `origin/main`. Same
code, same submodule, different result ⇒ **environmental**. See
[[solidworks-center-rectangle-determinism]] for the full root cause: the SolidWorks
system option **`swSketchAddConstToRectEntity`** (swconst id **584**) was **OFF** on my
seat, so native `CreateCenterRectangle` at the origin never auto-added the centre→origin
coincidence → the rectangle floats. The pref is READable but **won't set** via
`SetUserPreferenceToggle` on 3DEXPERIENCE R2026x. Fix lives in code:
`define_centered_rectangle` Path A now captures a construction diagonal and, when the
profile isn't already fully defined, pins its midpoint to the origin (idempotent).
Shipped as **standalone main PR #283** (`pedro/deterministic-center-rectangle`,
separate from this task). Verified green on the 584=False seat for arbor_pedestal +
support_bar + wheel_bar + foot_screw + swing_stop_screw + top_frame + cone_pivot_screw.

This also VINDICATES the earlier retraction: the under_defined was never #271's fault
nor my rebinds' — it was seat option-state all along (LESSON reinforced:
[[negative-result-needs-positive-control]] — the positive control that broke the tie
was building the SAME part on the user's exact submodule).

Point-fix committed to submodule branch as **987b1e8** (reworded from WIP), pushed to
PR #87; 726 adapter tests pass (was 725, +1 for the new segment-vs-point test), ruff
clean.

## Status 2026-07-13 (cont.) — rebinds MERGED, flip done, DIAG skipped

All three rebind PRs **MERGED** 2026-07-13: **#283** (determinism → main),
**#87** (SUBMOD rebinds → personal, merge `3752e6c`; point-fix `987b1e8` durable
in history), **#281** (BUILD/verify-tier rebinds + submodule pointer bump to
`987b1e8` → main, merge `17b6b215`). Each cleared build-green + Codex-👍; a clean
full `doit -n 4` on the rebased #281 head had **ZERO** `early-bound fallback:`
warnings. That completed the whole rebind surface (642 occ / 25 members → 0).

**The flip is DONE** — submodule branch `pedro/fail-loud-fallback` off `personal`,
**draft PR pedropaulovc/SolidworksMCP-python#88**. `_fallback_subclass` →
`_strict_subclass`: `__getattr__` AND `__setattr__` now RAISE `AttributeError`
(naming the interface + member) on any undeclared member instead of forwarding to
late binding. Removed the dead forwarding machinery (`_late_bound`/
`_late_bound_dispatch`, `_warn_fallback_once`/`_fallback_warned`,
`_all_method_names`); renamed `_register_fallback_classes` → `_register_strict_classes`.
The `_`/dunder guard is UNCHANGED so `getattr(obj, "_FlagAsMethod", None)` still
misses. AttributeError specifically (getattr-with-default guards depend on it).
745 adapter tests pass. Validating via a cold `HARMONIC_REMOTE_CACHE_MODE=off
doit -n 4` (submodule-digest change forces a from-scratch rebuild of every
part/assembly/verify/drawing, exercising all COM paths with the flip live).

**[DIAG] tier — SKIPPED by user decision 2026-07-13.** The ~62 off-interface
sites across ~100 hand-run `cad/scripts/diagnostics/` probes are NOT rebound: they
are non-gated one-off debugging scripts, many stale. Under the flip a probe that
hits an off-interface member now raises a clear "rebind to the owning interface"
`AttributeError` — the fail-loud contract working as intended. Rebind a probe
lazily only when it is actually needed. (Rebinds there can't be mock-validated
anyway — only a real SW run catches interface binding.)

**Remaining:** (1) confirm the cold flip-validation build is green (zero crashes);
(2) merge #88 → personal; (3) main-repo PR bumping the submodule pointer to #88's
personal merge commit — validated by the same cold build (pointer content ==
flip content) — → main. NOTE the flip also affects any `_flag_feature_methods(obj,
iface, *methods)` site whose flagged method isn't on `iface`; the cold build's
zero-crash result is the complete checklist. motion.py's TLB-absent methods use
`flag_method_names` on a RAW dispatch (NOT the strict subclass), so the flip does
not touch them.
