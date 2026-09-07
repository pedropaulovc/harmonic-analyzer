# VM2: remove coordinate selection from three turned-part drawings

Migrate the crank pin, pinion lift rod and pinion pivot shaft drawings to explicit
model entities. Use the accepted resolver from #685. SolidWorks may choose
annotation positions; view layout, spacing and scale may change if the resulting
production print remains correct and readable. Preserve all manufacturing data.

This is a new assignment, not completed validation. It does not replace the
assembly-dependency assignment in #686/#687. If that work has a native run in
progress on VM2, finish it before starting another native workflow. Preserve all
accepted worktrees, outputs and receipts. VM1 owns parent integration and merging;
VM2 owns only the files listed below. Neither machine needs the other's CAD files.

## Frozen starting point

Repository: `https://github.com/pedropaulovc/harmonic-analyzer`.

- Base: `442cd6a2885ba789548c5f3b93509656a5e9dee1`, accepted #685.
- Adapter: `25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`, unchanged.
- New branch: `perf/turned-part-semantic-entities`.
- New checkout: `C:/src/ha-turned-part-semantic-entities`.
- PR parent: `perf/entity-resolver-batching` (#685).

Load `/developing-solidworks` first and read the checkout's `AGENTS.md`. Use its
bundled API documentation, Windows-native tools and a separate uv environment.
Inspect any existing destination or branch before creating it; do not overwrite
another experiment. From an existing clone containing the accepted branches:

```powershell
git fetch origin main perf/entity-resolver-batching
git worktree add -b perf/turned-part-semantic-entities C:/src/ha-turned-part-semantic-entities 442cd6a2885ba789548c5f3b93509656a5e9dee1
Set-Location C:/src/ha-turned-part-semantic-entities
git submodule update --init --recursive
uv sync --frozen
git rev-parse HEAD
git -C SolidworksMCP-python rev-parse HEAD
```

This historical base keeps the paired experiment independent of VM1's moving
integration stack. Record newer main commits, but do not mix them into the
baseline/candidate comparison. VM1 will rebase and revalidate the integrated
stack before merge. If the parent has moved or merged, report the difference
before changing the experiment base or PR target. Do not rewrite parent branches.

Read these documents at the frozen base:

- `cad/docs/performance/entity-resolver-batching.md`.
- `cad/docs/pipeline/crank-arm-entities-results.md`, including acceptance limits.
- The three recipes, their builders, specs and existing tests.

The #685 speedups are evidence for its crank-arm experiment, not predictions
for these three drawings. Establish fresh local baselines.

## Exclusive file ownership

Production and existing tests:

```text
cad/scripts/draw_crank_pin.py
cad/scripts/draw_pinion_lift_rod.py
cad/scripts/draw_pinion_pivot_shaft.py
cad/scripts/test_crank_pin_drawing.py
cad/scripts/test_pinion_lift_rod_drawing.py
cad/scripts/test_pinion_pivot_shaft_drawing.py
```

New batch-specific files:

```text
cad/scripts/diagnostics/probe_turned_part_entities.py
cad/scripts/test_turned_part_entities_drawing.py
cad/docs/pipeline/turned-part-entities-results.md
```

VM1 will leave these nine paths to VM2 during this assignment. Read shared helpers
as needed, but coordinate before editing the resolver, `_drawing_common.py`,
factory/layout code, diagnostic runners/registries, `dodo.py`, adapter, builders,
specs, configuration, templates, memory or any other recipe. Do not change
#676 through #678, #680 through #682, #685, or the assembly extraction branches.
Keep the withdrawn mass-read optimization out of this work.

## Selection inventory and geometry traps

There are 11 annotation constructions using coordinate selection at this base:

| Recipe | Constructions | Intended model roles |
|---|---:|---|
| crank pin | 3 | Big-end diameter, small-end diameter, taper-seat finish |
| pinion lift rod | 4 | Datum A, rod cylindricity, front-face perpendicularity, bearing finish |
| pinion pivot shaft | 4 | Datum A, shaft cylindricity, crown profile, bearing finish |

The crank's two diameter calls share one `SelectByID2` site in a local helper.
Do not confuse the 11 executed constructions with unique source call sites,
COM call counts or unique edges. Text/frame coordinates are placement, not
geometry selection, and may remain.

Resolve one bounded `ModelEntities` bank per live source document. Use feature
ownership and geometry predicates, reject missing/ambiguous matches, and release
the handles before closing or replacing that source. Do not use nearest-point
searches, first-match selection, sheet-coordinate fallbacks or cross-run handles.

The following are candidate mappings to verify against native geometry, not
accepted attachments:

- Crank pin: feature `Pin`, axis +X, end planes at model X=0 and `PIN_LENGTH`.
  Resolve each end circle through its own planar face boundary. Resolve the
  taper finish through the controlled cone face from `SURFACE_FINISHES` and its
  big-end circular boundary. Import dimensions from the spec; do not duplicate
  literals or substitute an unrelated coplanar circle.
- Lift rod: `Rod`, axis +Z. Datum A uses the cylinder's front circular boundary
  at Z=0. Resolve cylindricity and bearing finish to the rod's cylindrical face;
  resolve front perpendicularity through the front planar face boundary. This
  replaces two silhouette picks without changing the controlled surfaces.
- Pivot shaft: `Shaft`, axis +Z. Datum A and cylindricity use the front circular
  boundary; bearing finish controls the shaft cylinder. `Capfront` and `Capback`
  own separate spherical crowns. Record both crowns independently and identify
  the one selected by the unchanged baseline before assigning the profile role.
  Sheet-right does not establish which model end it is. Preserve the existing
  single `BOTH CROWNS` form-only profile frame and its absence of datum references.

The crank's end circles are edge-on in the side view. Read the local
`IView.SelectEntity`, `IModelDoc2.AddDimension2` and `IDisplayDimension.Diametric`
contracts and examples, then obtain a native positive control for this exact
call shape. `add_entity_dimension` requires two entities and is not a direct
replacement for the one-circle helper. A successful selection or non-null
dimension alone is insufficient: verify the attached source circle, owning
view, native dimension type, raw value and actual diameter display. The print
must show the specified true diameters, not profile radii or swapped end labels.

Use existing annotation helpers with their actual argument shapes. Datum/FCF
calls accept `entity` but not `entity_context`; source-owned surface finish also
needs `entity_context=AnnotationEntityContext.MODEL`. Positioned datum/FCF calls
at this base do not perform the explicit model-context reverse-identity check.
Add recipe-local post-return attachment type/count, owning-view and native
source-role identity checks, following the accepted crank-arm pattern. Preserve
the helpers' existing validators as well. A helper failure
requires the exact call and a working positive control before concluding that an
API cannot support the migration.

Preserve dimension names, values, tolerances, BASIC/reference state, fits,
precision, all datum/FCF/finish contents, linked notes and truthful scale labels.
In particular, retain the crank's 1:48 taper and keeper-hole instructions, the
lift rod's crown-radius/sag/overall-length information, and the pivot's two-crown
requirement. The specs and native readbacks own the values.

Existing tests deliberately assert coordinate-pick spellings, including the
rods' `edge_xy=end_top` datum calls. Report the exact assertions and the
manufacturing requirements they protect before replacing those contracts.
Raise any substantive requirement contradiction; do not weaken assertions to
obtain a pass. New tests must prove explicit roles, coverage and readback.

## Native baseline and acceptance

Use one licensed SolidWorks instance on VM2 and the machine-global COM seat lock
for every native task, including probes. Inventory the actual PID and open
documents; attach with `HARMONIC_SW_AUTOSTART=0`. Launch only through the licensed
3DEXPERIENCE path when needed. Preserve borrowed documents, keep the watchdog,
and never interleave experiments just because individual calls take the lock.
Freeze source, tests, configuration and adapter files throughout each native run.

1. Build the three source parts through doit in this checkout with remote cache
   disabled. Require actual successful native part builds. Record each original
   SHA, exact execution token, root/adapter commits, import paths, host and SW
   revision. Do not copy ledgers, tokens, gate stamps, prepared entries or venvs
   from another checkout, or restamp them to match an expected source.
2. Run each unchanged production drawing and retain its native file, PDF, PNG,
   telemetry and source-before/after hashes. Capture selected/attached identities,
   raw dimensions and annotation contents, especially the pivot crown end and
   crank diameter behavior. Baseline failures must remain visible. Preserve this
   baseline before candidate outputs reuse any production path.
3. Build the candidate, require all 11 constructions to use explicit entities,
   and compare actual selected/attached model identities and owning views.
   Source and token hashes must remain unchanged through drawing work. Use owned
   source/drawing copies and the existing guarded factory/save path for probes.
4. Close only owned documents and release their handles. Reopen source and
   drawing with fresh handles, resolve roles again, and verify dimensions, text,
   native PMI contents and attachments. On owned copies, move and rescale views,
   verify again, save, then repeat the fresh-handle cold reopen. Compare geometry
   as well as ownership so equal-looking opposite ends cannot be exchanged.
5. Export and inspect production and cold full-sheet prints plus readable detail
   crops. Check ink/leader collisions, datum routing, diameter marks, crown
   controls, finish symbols and title/scale fields. A deliberately crowded
   move/scale experiment proves associations, not production print quality.

Once dependencies are genuinely current, force only a drawing for matched
measurements, for example:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
uv run python -m doit -a -s drawing:crank_pin
uv run python -m doit -a -s drawing:pinion_lift_rod
uv run python -m doit -a -s drawing:pinion_pivot_shaft
```

`-s` prevents forced dependencies from rebuilding the parts and changing their
identities. Do not use it to bypass stale prerequisites. Compare baseline and
candidate on the same saved sources, adapter and factory state, alternating at
least three ABBA blocks per recipe. Freeze each variant while it runs. Separate
instrumented identity probes from uninstrumented production timing; report
resolver, recipe, save/export and total wall time, with every failure and retry.
Do not infer a below-5% failure rate or a fleet speedup from this small batch.

## Diagnostic coverage and tests

Compose the existing owned-session/document, source snapshot, factory and
cold-reopen helpers in the new batch-specific probe. Read their contracts and
tests first. The probe must run independently without shared target enrollment.

`_recipe_entity_acceptance.EntityAcceptance` does not cover this entire batch:
its annotation-kind mapping and observer path do not cover the crank's local
diameter helper. Merely adding names to a manifest cannot certify those two
dimensions. The crank-arm probe also contains recipe-specific source pins and
dimension rules. Reuse suitable operations, not its acceptance claim or hashes.
Declare this batch's complete role/type/dimension requirements locally. Collect
raw values, tolerances, precision and displayed text beyond the rounded fields
provided by the generic snapshot helper.

Use the APIs that exist at this base: `probe_drawing_attachments.snapshot` has
no `view_observer` argument or `referenced_document` helper, and the shared source
dimension reader uses the older tolerance accessors. Inspect the bundled native
contracts for additional readbacks needed by this probe. Do not import VM1's
later helper versions, silently ignore accessor status or widen comparison rules.

Retain ownership, source-immutability and factory guards at every mutation,
including save/export and cleanup. Preserve original errors and partial reports
on failure. Test the composed callback, wrong documents/views, swapped ends,
same-shaped foreign geometry, missing/duplicate roles, null selection/insertion,
failed save/export, cleanup and fresh cold handles. Mocked wrappers alone do not
prove the actual recipe called the intended entities.

Name all new tests `test_*_drawing.py`. Confirm their inclusion in the actual
`check:recipe` invocation and freshness dependency list; discovery by standalone
pytest is insufficient. Run the focused tests and full COM-free recipe, graph,
part-isolation and applicable layout checks. The accepted parent reports a
fillister registration/test contradiction. Reproduce it, leave both sides
unchanged in this batch, and report it separately from any new failures. It
remains a merge blocker until the parent resolves it; it is not an allowed pass.

## Review and delivery

Push early, open a draft child PR and attach the `watch-pr` monitor immediately.
Mark it ready when code-complete, before the remaining tests. Obtain one clean
CodeRabbit OR Codex review of the latest child diff. Use the installed Windows
CodeRabbit CLI when hosted quota is unavailable; no WSL or billing changes.
Retain the complete local receipt, actual base/head, reviewed diff and verdict.
API/auth/quota failure is not a clean review; report the exact error.

Return the PR/head, exact nine-file ownership or approved deviations, base and
adapter, removed-selection inventory, local source/token manifest, all commands
and test results, native/cold/print evidence, complete timing samples and review
receipt paths/hashes. Separate accepted behavior from failures and untested work.
Keep the accepted #682/#685 artifacts and branches intact.

Leave the PR open. VM1 owns rebasing onto current parents, new source baselines
where required, the full-stack `uv run python -m doit -n 4`, affected render/print
inspection and final merge. That exact-head full build remains mandatory even
if this isolated experiment passes. Merge bottom-up without squash or deletion
of parent branches. A shared-helper change or newly discovered baseline defect
needs a separate coordinated patch and its own evidence.
