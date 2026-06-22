---
name: parametric-naming-roundtrip
description: How to make a build script emit human-named SW globals/sketches/features/dimensions so the part is GUI-editable and round-trips; top-frame is the reference; three hard-won COM gotchas
metadata:
  type: project
---

Goal the user is driving toward: make fine GUI adjustments to parts and have them
reflected back in the scripts. Chosen path (NOT authored-part tiers, NOT a
feature-tree decompiler): keep scripts as source, but have each build script emit
a fully **named** model — equation-manager globals + named sketches/features/
dimensions — so a GUI edit (and macro-recorded edits) reference stable names, and
values can be harvested back. **top-frame is the validated reference** (`build_top_frame.py`,
landed working 2026-06-21: part builds, "equations neutral" volume check passes,
renders a correct ring).

New lib helpers in `cad/scripts/_common.py` (all raw COM — the adapter has no
rename/enumerate surface): `name_last_feature` (rename most-recent feature via
`IFeature.Name`), `name_last_feature` also names sketches now (the old `name_sketch` tracker-sync
wrapper is gone — see gotcha 2, fixed in the adapter),
`name_dimensions` (rename a feature's display dims in CREATION order via
`GetFirst/GetNextDisplayDimension`→`GetDimension2`→`IDimension.Name`),
`dump_dimensions` (introspection / harvest seed), `set_global` /`drive_dimension`
(wrap `set_global_variable`/`create_equation`), `force_rebuild` (`EditRebuild3`).

**Self-naming refactor (the shape to copy, NOT the first cut).** The first
top-frame draft named dims with hand-written positional lists far from the
geometry (`RECT_DIMS=["Width","Depth",...]`) + separate `_drive_*` funcs — fragile
because the helper, not the script, owns dim emission ORDER and COUNT (an on-axis
circle centre is 1 dim, off-axis is 2 — `anchor_point_to_origin`; a hard-coded
3-per-circle silently mis-maps). Fixed by pushing recording INTO the emitting
helpers: `SketchDims` (per-sketch accumulator; helpers call `.record(name, drive)`
as they emit each dim; `.apply(feat)` renames + asserts recorded count == actual
display-dim count == loud structural guard, returns deferred `(dim@feat, expr)`
drive jobs); `define_circle` gained `dims=/names=(x,z,dia)/drives=` and records
only the dims actually emitted; new `define_centered_rectangle` (semantic
width/depth/corner wrapper over the generic `define_rectilinear_chain`, which
stays UNCHANGED — 67 other callers). Per-sketch pattern now: `SketchDims()` →
`create_sketch` → `define_*(…, dims=, names=, drives=)` → `ensure_fully_defined`
→ exit → `name_sketch` → `drive_jobs += sd.apply(feat)` → feature →
`name_last_feature`. Globals up front; run `drive_jobs` in ONE deferred batch
after a `force_rebuild` (targets must resolve against the finished model), then a
neutrality `volume_check`. Behaviour byte-identical to the first cut (same
1151664.1 mm³). Per-part cost ≈ 4 declarative lines/sketch.

Three COM gotchas that each cost a run (see [[solidworks-modeling-pitfalls]]):
1. **Never `sw_type_info.flag_methods` (i.e. `_FlagAsMethod`) on `IFeature` or the
   shared `adapter.currentModel`.** Flagging mutates the gen_py *type-shared*
   dispatch repr, so flipping `GetTypeName2`/`FirstFeature` to method dispatch
   breaks the adapter's OWN bare-property reads — its `create_cut_extrude`
   ProfileFeature walk then finds no profile → `FeatureCut3 ... Parameter not
   optional`. Walk property-style via `_read_member`; arg-taking methods
   (`GetNextDisplayDimension`, `GetDimension2`, `Select2`) work UNFLAGGED.
2. **Cut profile selection broke on rename — now FIXED in the adapter.** Root
   cause ran deeper than "stale `_last_sketch_name`": `create_cut_extrude`'s
   primary by-type walk read `model.FirstFeature`/`GetTypeName2`/`GetNextFeature`
   as BARE properties, which is dead under this binding — the active doc arrives
   as a late-bound **CDispatch** (`<unknown>`) whose feature methods don't resolve
   by name without `flag_methods`, so the walk raised `Member not found`, found
   nothing, and EVERY cut silently fell to the `SelectByID2(_last_sketch_name)`
   string fallback — which goes stale the instant a sketch is renamed. Fix
   (SolidworksMCP-python, branch `pr67-build`, `features.py _create_cut_extrude_impl`):
   select via `_profile_feature_names(adapter)[-1]` (the adapter's EXISTING
   flagged, live-name tree walk) + `SelectByID2` — rename-proof and it finally
   makes the primary path work for all cuts. Repo `name_sketch` workaround
   DELETED; sketches now use plain `name_last_feature`.
   **Footgun discovered:** `_common.py` injects a SIBLING checkout
   `C:\src\SolidworksMCP-python` (env `SOLIDWORKS_MCP_ROOT`) onto `sys.path[0]`,
   OVERRIDING the `uv`-installed editable submodule. So the build runs the
   sibling (branch `pr67-build`), NOT `harmonic-analyzer/SolidworksMCP-python`
   (detached `4e7d803`) — adapter edits must go in the SIBLING to take effect;
   the submodule is just what `uv sync` installs. Reconcile (commit sibling +
   bump submodule) for reproducibility.
3. **Documents are INCH; the equation manager evaluates BARE numbers in DOCUMENT
   units.** Driving `Width = 2*"OuterX"` with `OuterX=208` set the dim to 208
   INCHES → part blew up 25.4x in-plane (645x volume). Fix: give length globals an
   explicit `mm` suffix (`set_global(.., f"{x}mm")`); derived globals + equations
   inherit the unit. Same root fact as the pen-driver's "doc units" note.

Next: confirm the GUI-edit→harvest loop on top-frame (edit a global, re-open,
`dump_dimensions`), then roll the naming pattern to other parts. Ties to the
proposed `harvest`/`verify:drift` doit tasks (not yet built).
