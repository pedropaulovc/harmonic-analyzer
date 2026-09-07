# Second VM task: crank-arm drawing entity selection

Use this document as the next VM's task prompt. It defines one bounded migration;
it does not report completed native validation or merge readiness. The
[project board](https://github.com/users/pedropaulovc/projects/1) owns scheduling.

## Task and checkout

Replace sheet-coordinate feature picking in `cad/scripts/draw_crank_arm.py`
with explicit, validated model entities and named dimensions. Preserve the part
and its manufacturing requirements. SolidWorks may choose annotation positions;
you may change drawing layout, view spacing and placement. Do not build another
coordinate-search solver.

Start with the developing-solidworks skill and the checkout's `AGENTS.md`. Read
the bundled API contracts and examples before introducing native calls. Use uv
and this worktree's own virtual environment.

Repository: `https://github.com/pedropaulovc/harmonic-analyzer`.
Frozen starting commit: `7c86fdbaf4e6d3d274d6be39831c68d4e4e98e16`, published on
`perf/cad-build-and-drawing-entities`. Its adapter gitlink is
`25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`.

Use these new local destinations on the second VM. If either already exists,
inspect it and coordinate a new name; do not overwrite it.

```powershell
git clone --recurse-submodules --branch perf/cad-build-and-drawing-entities https://github.com/pedropaulovc/harmonic-analyzer.git C:/src/ha-crank-arm-vm-seed
git -C C:/src/ha-crank-arm-vm-seed worktree add -b perf/crank-arm-semantic-entities C:/src/ha-crank-arm-semantic-entities 7c86fdbaf4e6d3d274d6be39831c68d4e4e98e16
Set-Location C:/src/ha-crank-arm-semantic-entities
git submodule update --init --recursive
uv sync
git fetch origin main
git log --oneline HEAD..origin/main
```

Follow the repository's rebase policy before native work. If that changes the
starting revision, record the new exact root and adapter commits and regenerate
the baseline there. Do not repeatedly pull the moving drawing branch while
measuring. Freeze all imported Python and adapter files for each native run.

## File ownership

You own `cad/scripts/draw_crank_arm.py`,
`cad/scripts/test_crank_arm_drawing.py`, additional crank-arm-specific tests
named `test_*_drawing.py`, and a crank-arm evidence document under
`cad/docs/pipeline/`.

Read shared code, but coordinate before changing `_drawing_common.py`, entity
resolvers, layout/checking helpers, the prepared-template or factory code,
diagnostic registries/runners, `dodo.py`, source-authoring helpers, the adapter,
or any other recipe. Do not modify `build_crank_arm.py`, `crank_arm_spec.py`,
configuration or part geometry as part of this drawing migration. A required
shared change or pre-existing source mutation is a separately reported issue,
not permission to expand this patch.

## What the frozen audit found

The recipe has 15 static coordinate-selection sites. This counts source calls,
not native calls or unique features; one dimension selects two entities and
the search can try several points. Line numbers below refer to the frozen base.

| Sites | Required role and current recipe lines |
|---|---|
| Five `add_edge_dimension` calls | stock width (223), shaft-to-pivot centres (240), pivot transverse location (249), dimple transverse location (274), cross-hole station (299) |
| One `find_edge_near` call | datum-A boundary for the cross-hole station (302) |
| Three datum calls | broad face A (363), shaft axis B (381), width side C (414) |
| Three FCF calls | cross-hole position (326), pivot position (422), broad-face parallelism (460) |
| Two native hole callouts | cross-hole (337), handle pivot (453) |
| One surface-finish call | shaft bore (507) |

Trace these through `_select_annotation_entity` and `_select_view_entity` in
`_drawing_common.py`: without an entity handle they eventually call unnamed
`SelectByID2` with sheet X/Y. Many points are derived from spec dimensions and
view centres. That is still a hit test, but it is not evidence that every point
is currently wrong. Text/frame positions and native placement seeds are outside
this feature-selector count and may remain coordinates.

Relevant building blocks already exist at the frozen revision:

- `_drawing_entities.py` provides `ModelEntities`, `CircleEdge`, `LineEdge`,
  `FeatureFace`, `FaceBoundary` and `EdgeAdjacentFace`. Feature-scoped requests
  resolve through named source features; selectors reject missing or ambiguous
  matches. A model-coordinate geometry predicate is not a sheet-coordinate pick.
- `_drawing_common.py` provides `add_entity_dimension`, explicit `entity` /
  `edge_entity` annotation arguments, `AnnotationEntityContext.MODEL`, and
  `add_native_hole_callout(..., edge=...)`. Use the real argument shapes and
  source/view ownership contract; do not rely on default VIEW context for a
  source-owned annotation entity.
- `draw_channel_lever.py`, `draw_arbor_pedestal.py`, `draw_fulcrum_shaft.py` and
  `draw_cone_pivot_screw.py` contain relevant resolved-entity examples. Their
  existence is not native proof for the crank arm's faces or interrupted edges.
- Crank arm already imports the prepared drawing factory and the read-only
  `verify_dimension_callouts` contract. It does not yet import `ModelEntities`
  or `add_entity_dimension`; adding those existing imports is within scope.

Read `crank_arm_spec.py` and the builder rather than using old comments as
geometry. For example, the frozen spec has `ARM_C2C = 75.0`; older drawing
comments still discuss 66 mm. The builder names `Arm`, `ShaftBore`, `PivotBore`,
`Dimple`, `AnchorTap` and `PinHole`. These are candidate ownership scopes, not
proof that each final edge survives on the feature you first expect.

Preserve the exact marked-dimension union from `DRAWING_DIMENSIONS`, the five
added dimensions and their centre-versus-tangent interpretation, and the
existing BASIC state of pivot longitudinal/transverse and cross-hole station
dimensions. Do not make the dimple transverse dimension BASIC by inference.
Preserve A/B/C meanings, all three FCF contents and datum orders, the shaft-bore
finish, both Hole Wizard callouts, source fits/precision and linked notes.
The source notes require an isometric at 1:1; keep that truthful without editing
the part. Drawing layout changes must not change the manufactured dimensions.

## Build your own baseline

Use only this VM's licensed SolidWorks and artifacts produced from the chosen
frozen branch. Do not copy the first VM's `cad/out`, templates cache, `.doit.db`,
virtual environment, source SHA pins or `.execution` files. The native output
of a genuine local build may have a different SHA and persistent identities.

Inventory the session before starting. Ordinary build wrappers can close
documents or recover SolidWorks, so use a dedicated session without user work.
Use the machine-global seat lock for every native job, including diagnostics.
Do not fake `HARMONIC_COM_SEAT`, bypass the watchdog, drive the other VM or run
two native jobs at once. Use the installed licensed launch path when needed.

In this worktree, after recording the frozen revision and obtaining the local
seat, build the source through doit with cache disabled:

```powershell
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
uv run python -m doit -a part:crank_arm
```

Require a real successful `part.build` trace, not a cache restoration. Before
any drawing run, record the output SHA, its exact execution token, source size,
root/adapter commits, actual import paths, SolidWorks version and host. Preserve
that source and token. Never restamp a token, substitute another SHA, loosen a
pin, or adopt post-drawing bytes to make a comparison pass. Deliberately created
scratch copies are permitted only under the existing document-ownership rules.

Run and retain the unmodified drawing baseline before editing the recipe:

```powershell
uv run python -m doit -a drawing:crank_arm
```

Hash the source before and after. Capture raw dimensions, tolerances, callout
text, attachment roles and source dirty flags around the drawing experiment.
Keep the baseline native drawing, PDF, PNG and telemetry as evidence. A failing
baseline remains a failure; document it before proposing a separate fix. Do not
overwrite the only retained baseline while producing candidate outputs.

## Implement and prove the migration

1. Map each of the 15 sites to a source feature, geometric role and intended
   view. Resolve one bounded bank and reuse its handles within that live source
   document. Reject zero/multiple matches and a wrong source/configuration.
   Do not choose the first edge, search nearby sheet points or retain handles
   across close/reopen. Keep manufacturing measurements tied to native values.

2. Get a native positive control for the actual selection shapes before
   replacing every caller: a shaft-bore role, a planar boundary used for a
   dimension/datum, and the Hole Wizard edges. Check native selected and attached
   identities, owner/view/source and the resulting dimension or symbol. A True
   return alone is insufficient. If a shape fails, retain the arguments and
   raw result and compare it with a working call; do not declare the API dead.

3. Add mocked full-recipe tests as well as resolver negatives. Prove that all
   feature attachments use explicit handles, all required dimensions/PMI remain,
   missing or ambiguous entities fail before insertion, and no sheet-picking
   fallback survives. The existing tests deliberately assert `edge_xy=DATUM_B_RIM`,
   radial placement, `find_edge_near` and several `add_edge_dimension` spellings.
   Report those contradictions before changing assertions. Replace only the
   approved implementation/layout expectations with native-role/readback tests;
   retain the manufacturing requirements they were protecting.

4. Run the changed production recipe through doit. Allow native placement or
   changed view layout, but retain all existing final layout/attachment checks.
   Measure resolver cost and total recipe cost with the same inputs and final
   checks. A change in layout is not a reason to skip collision checks or infer
   a speedup from fewer Python calls.

5. Validate the saved drawing on owned copies after view movement/scale and
   save/reopen. The existing `diagnostics/probe_drawing_attachments.py` accepts
   a drawing path and uses the locked owned-document runner; read its contract
   and retain its full report, including exclusions. `crank_arm` is not enrolled
   in the fixed-source `probe_datum_policy_recipes.py` target manifest at this
   base. Do not invent a `--target crank_arm` invocation or copy another VM's
   pins into that manifest. Coordinate any needed enrollment or shared harness
   change; reuse existing ownership/snapshot helpers rather than a new framework.

   A successful attachment probe alone is not full cold/print acceptance. Close
   only owned drawing/source copies, reopen the source and drawing with fresh
   handles, and verify dimension names/values/tolerances/BASIC, callout text in
   actual displayed text, all annotation contents and attachments, view/sheet
   scales and source immutability. Use the existing boundary-specific comparison
   rules; do not add tolerances or exclusions to hide failures. Export and inspect
   fresh full-sheet PNGs plus readable detail crops before and after reopen.
   Check dimension/leader crossings, model-ink overlap, datum routing, finish
   symbol, hole text and title fields. Record any unsupported validation before
   claiming acceptance.

## Review and completion

Push your implementation branch and open an early draft PR. Stack it on
`perf/cad-build-and-drawing-entities` while that parent is open; use `main` if the
parent has merged. Do not force-push the parent or another agent's branch.
Immediately invoke the watch-pr skill after `gh pr create --draft` and keep its
monitor running. Mark the PR ready when code-complete, before the remaining test
runs, so review and testing can proceed together. Address actual CI/review
failures; do not lower thresholds or rewrite deliberate tests silently.

Run the recipe-specific tests and the relevant offline graph/isolation/layout
checks. Before merge, satisfy the repository's full graph/build gate on the
latest code with `uv run python -m doit -n 4`, explicitly rerun and validate
`drawing:crank_arm`, complete the native cold/render checks above, and obtain
one clean CodeRabbit OR Codex review of the latest code. Follow the current
stack sharing rules; a local focused test run is not the full build gate.
Do not squash or delete a parent branch while children still target it.

Hand back the commits/PR, removed-site inventory, actual source/build provenance,
commands, test results, trace/report hashes and paths, fresh rendered evidence,
cold result and measured timings. Keep unresolved failures explicit. This task
does not authorize a fleet migration or a shared-helper redesign.
