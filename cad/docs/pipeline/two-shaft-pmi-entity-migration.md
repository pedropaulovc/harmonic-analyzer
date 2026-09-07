# Two-shaft PMI entity migration

This migration replaces eight PMI attachment picks and two surface-finish
picks in `draw_fulcrum_shaft.py` and `draw_pivot_shaft.py`. Both recipes passed
native build, cold entity/content checks and render inspection at `d8ec09f5`,
as recorded below. The later [production MISS/HIT at `d6ad5aad`](prepared-template-viewport-control.md#production-misshit-at-d6ad5aad)
passed both drawing tasks but did not repeat cold or printed-pair comparisons.
The earlier failed controls remain below as provenance. These results do not
cover the other explicit-entity callers or the full pipeline. No speed
improvement is claimed.

Both source builders name their single solid extrusion `Shaft`. Existing
`ModelEntities`, `FeatureFace` and `FaceBoundary` resolve all roles in one request:

| Row | Fulcrum | Pivot |
|---|---|---|
| Datum A | Shaft cylinder's -Z rim | Same |
| Bearing cylindricity | Same cylinder rim in Front | Controlled cylinder face in Right |
| +Z end perpendicularity | +Z planar face's rim in Right | Same |
| -Z end perpendicularity | -Z planar face's rim in Right | Same |
| Bearing finish | Cylinder's -Z rim in Front | Controlled cylinder face in Right |

The rim stations/radii come from the existing model dimensions, never sheet
coordinates. The Front/-Z routing follows the project's existing front-view
convention; the two-shaft native results below cover this routing.
Feature membership is `FeatureByName("Shaft").GetFaces()` plus exact-one geometric
matching, not an exclusive-owner claim: the API permits shared feature faces and
`IFace2.GetFeature()` returns only the oldest owner.

The typed datum/control/finish rows, part builders, view scales, dimension
curation and other display seeds are unchanged. The two datum rows now request
native placement with `position=None`; numeric placement tolerances are not
widened. No coordinate,
nearest-entity, or visible-entity fallback was added. Layout is not accepted merely
because an attachment is correct.

`project_part_pmi` checks explicit face/edge qualification against the unchanged
PMI row before inserting anything. After the complete insertion/rebuild bank, its
shared witness requires one non-null native attachment of the expected type, exact
entity identity, drawing-view ownership, and exact owning-view identity. Equal
names or diameters do not replace `ISldWorks.IsSame == 1`. Explicit-position surface
finishes use the same identity witness after their existing rebuild. The existing
native-placement paths and coordinate-based unmigrated PMI paths remain unchanged.

## Native acceptance scope

The shared explicit-position finish guard affects **12 production recipes and
13 finish calls**, not only cone-gear-shaft. The first two native checkpoints are
the migrated fulcrum and pivot recipes; passing them does not accept the remaining
ten existing callers. Each needs its unchanged full recipe, attachment/view
witnesses, saved/reopened content and printed/render inspection. Stop a diagnostic
invocation on its first failure; a separate target needs an explicit new run.

| Checkpoint | Recipe (`draw_*.py`) | Explicit-position finish calls | Native attachment type |
|---|---|---:|---|
| First | `fulcrum_shaft` | 1 | EDGE |
| Second | `pivot_shaft` | 1 | FACE |
| Remaining | `cone_gear_shaft` | 2 | FACE |
| Remaining | `alignment_pinion` | 1 | EDGE |
| Remaining | `crank_drive_gear` | 1 | EDGE |
| Remaining | `crank_pinion` | 1 | EDGE |
| Remaining | `crankshaft` | 1 | SILHOUETTE (46) |
| Remaining | `cylinder_gear` | 1 | EDGE |
| Remaining | `rack_pinion` | 1 | EDGE |
| Remaining | `spring_hook` | 1 | SILHOUETTE (46) |
| Remaining | `transgear_feed_pinion` | 1 | EDGE |
| Remaining | `transgear_pinion` | 1 | EDGE |

The typed-PMI guard covers eight newly explicit rows in the two shafts and two
existing cone-gear-shaft rows (datum A and journal cylindricity). Cone tip runout
remains on its coordinate route. Other coordinate-only PMI and finish calls, and
native-position finish calls without `symbol_xy`, do not enter the new guard.
The production callers are direct imports/calls, not hidden behind a shared
recipe wrapper. The separate typography diagnostic
`probe_drawing_annotation_layout.py` also creates one explicit-position finish
and is an affected diagnostic consumer, not a thirteenth production recipe.

Re-run the call-site inventory from this revision with:

```powershell
rg -n -A 14 -g '*.py' -g '!test_*' 'add_surface_finish\(' cad/scripts
rg -n -g '*.py' -g '!test_*' 'add_surface_finish|project_part_pmi' cad/scripts
```

For the finish list, select calls providing `symbol_xy` and either `entity` or
`edge_entity`; absent `entity_type` means EDGE. The second search exposes imports,
aliases and helper references for the transitive-consumer review. No native
success, silhouette identity behavior, or visual acceptance is inferred from this
source inventory.

## First two owned native checkpoints

The existing `diagnostics/probe_datum_policy_recipes.py` now has explicit
`fulcrum_shaft` and `pivot_shaft` manifests. Its default remains rocker then
lever. Each shaft uses its unchanged production dimension manifest (diameter and
length), recipe, builder and specification; no part rebuilding is authorized by
this diagnostic. The pinned 2026-09-06 native input hashes are:

| Part | SHA-256 |
|---|---|
| `fulcrum-shaft.SLDPRT` | `73eeb75dcb1f24ca70b5f5ad2212d7b829a94af3a518b7c3830ff6c58e47d740` |
| `pivot-shaft.SLDPRT` | `e5bcdb79849aac9ce6068188ccf0c6e2fd1222e82f1d8b4d75e0fd2723f01dc5` |

Their execution-token contents matched those hashes. This establishes exact
input identity, not proof that current builder bytes originally produced them.
The receipt separately fingerprints the builder/specification, archived recipe,
all runtime helpers/config/templates and the actual imported adapter package.
Final file guards also run after failure and retain any additional error without
masking the primary failure.

The diagnostic observes the unchanged production attachment validator, requiring
all four PMI rows plus the finish. After the complete recipe it rechecks exact
annotation/view/entity identities and the controlled source face/boundary shapes.
Cold reopen uses newly resolved source entities, not old closed-document handles;
the expected annotation coverage, geometry and view membership must persist.
The existing full drawing content/layout/cold-title gates remain unchanged.
Named dimensions and controlled roles do not prove full in-memory source
immutability. Source-copy disk saves still fail; originals are never opened.

After review, a fresh explicit seat/PID grant and a frozen runtime, run **one**
target per invocation from the integrated checkout. Set
`HARMONIC_SW_AUTOSTART=0`, `HARMONIC_REMOTE_CACHE_MODE=off` and
`HARMONIC_DIAGNOSTIC_SW_PID` to the independently verified existing process.
The same source and guard directory is intentional: initial/final exact hashes
and shared ownership protect one original; no redundant guard file is required.

```powershell
uv run --no-sync python cad/scripts/diagnostics/probe_datum_policy_recipes.py --target fulcrum_shaft --candidate HEAD --source-root C:/src/harmonic-analyzer/cad/out/sldprt --guard-root C:/src/harmonic-analyzer/cad/out/sldprt
```

Pivot is a separately authorized invocation with `--target pivot_shaft`, not an
automatic retry/continuation after a failed fulcrum. Outputs use unique registered
directories; a successful recipe still requires its native/PDF/PNG, fresh cold
witness and an eye pass. This is not the full doit merge gate or a speed trial.
These two shaft results do not establish acceptance of the other ten production
callers or the typography diagnostic. In particular, a general attachment
snapshot's type-46 exclusion is not silhouette identity evidence.

Offline runner/role acceptance regression:

```powershell
uv run python -m pytest cad/scripts/test_shaft_recipe_acceptance_drawing.py cad/scripts/test_datum_policy_recipes_drawing.py cad/scripts/test_recipe_template_factory_drawing.py -q
```

### First fulcrum native control and datum-only correction

At root `37a58501` / adapter `e77bfda`, the normal-factory owned fulcrum control
stopped after **5.946373899991158 s** of recipe execution. The old requested datum
anchor was `(55, 229)` mm; native readback was
`(55.00000000000015, 194.30287392280807)` mm. The 34.697126 mm difference exceeded
the unchanged 0.1 mm explicit-position limit. This is a failed placement contract,
not evidence that the datum API or exact entity selection cannot work.

Receipt: `cad/out/reports/datum-policy-gt3wao0c/pilot.json`, SHA-256
`2186170794a511c29b43c35914b5d32f7671ba60304925ab13d46f7bc42e8de0`.
Its three protected originals and owned fulcrum copy retained their exact hashes;
final runtime guards were clean. The failure-only PDF/PNG retained the incomplete
sheet without a native drawing/source save. Eye inspection of
`fulcrum_shaft/failure.png` shows A clearly below the circular end. The other
controls/finish were not inserted, so this is not complete-sheet acceptance.
The earlier seed remains reproducible with the owned pilot command above and
`--candidate 37a58501`; a new native invocation still requires review/seat grant.

`PmiDrawingPlacement.position=None` now explicitly requires a model `entity` and
forbids a fixed leader endpoint. The two shaft datums use the existing
`add_datum_feature(symbol_xy=None)` path, with **no `SetPosition2` call**. The
complete native-PMI bank requires individual visibility state 1, non-dangling
attachment and a finite on-sheet anchor, in addition to exact entity/view and
typed-content checks. The owned pilot repeats these checks over all five guarded
annotations after the finish is inserted and after cold reopen. Visibility state
alone does not prove an unhidden layer, and anchor fit does not prove body/text
clearance; full layout/cold/printed checks remain required.

The existing direct native-insertion test intentionally allows an off-sheet
anchor to emit a diagnostic before later layout. That helper/test contract stays
unchanged; the stricter assertion belongs to completed native-PMI/acceptance
banks. Other explicit positions retain their exact position assertions.

```powershell
uv run python -m pytest cad/scripts/test_native_pmi_datum_drawing.py cad/scripts/test_shaft_recipe_acceptance_drawing.py cad/scripts/test_shaft_pmi_entities_drawing.py cad/scripts/test_native_annotation_placement_drawing.py -q
```

The new native-PMI tests failed first: 11 failures / 3 passes exposed missing
visibility/dangling/overflow checks and the still-explicit recipe datum seeds.
No tolerance assertion was relaxed. API references: `IAnnotation.Visible`,
`swAnnotationVisibilityState_e`, `IAnnotation.IsDangling` and
`IAnnotation.SetPosition2` (documented placement restrictions can clamp a datum).

### Native-position attempt: unresolved source/view identity

Root `3db3efe2` / adapter `e77bfda` reached the complete PMI bank and failed its
datum-A entity identity check after **7.40359040000476 s**. Receipt:
`cad/out/reports/datum-policy-yic4qtbp/pilot.json`, SHA-256
`e7ad58f741194cef28bbfb31a4c78133a048217f4438bc2c10101639865bfe17`.
The failure evidence is complete with no capture errors; original/source-copy
hashes and final runtime guards remained exact. Failure-only PDF/PNG were made,
not a saved native drawing or a cold/whole-sheet acceptance result.

The retained datum circle geometry equals its intended source rim exactly in
the existing serialized geometry witness: center `(0, 0, -0.091)` m, radius
`0.003175` m. The three FCF signatures also match their intended source rims.
This is **not** an identity proof. The immediate native datum check compares the
handle returned by `SelectionMgr.GetSelectedObject6`; the final bank compares
the original `ModelEntities` handle. The receipt did not retain the intermediate
native identity matrix, so it cannot distinguish different source/view contexts
from attachment replacement during subsequent insertions/rebuilds.

The same owned pilot now records `entity_context_observations` for explicit-role
recipes. It observes the existing selection, immediate native validation and
final explicit-bank boundaries without changing any production validator or
selection. The matrix retains `IsSame` results for original source, selected,
corresponding-view and attached entities, plus their reverse-mapped part entities.
It uses documented `IView.GetCorrespondingEntity(source)` and, as in the bundled
*Get Corresponding Entities Between Parts and Views* example,
**the source part's** `Extension.GetCorrespondingEntity2(view_entity)`.
No document activation, selection, source write, or new retry is introduced.

Null mappings, unknown (`-1`) identity and read errors are recorded distinctly.
They cannot convert the original failure into acceptance. Every read group and
stage is timed; these diagnostic reads are included in `recipe_seconds`, so the
instrumented run is not an uninstrumented speed measurement. The pilot stores
the matrix even when its original attachment check aborts. Expected same-session
disambiguation: selected-to-attached stays 1 while source-to-selected is 0 and
source-to-reverse is 1 for a context difference; a later selected-to-attached
change is separate evidence of replacement. Neither outcome is assumed in code.

The existing one-target command above reruns this control after review and a
fresh exclusive seat grant. The observer's initial implementation had only mock
verification; its subsequent native result is recorded in the next section.
The mocks deliberately distinguish equal-geometry native handles and retain the
real production rejection; they also cover null/unknown/read-error mappings,
multiple/null attachments, interruption and restoration of all three observers.

```powershell
uv run python -m pytest cad/scripts/test_annotation_entity_context_drawing.py cad/scripts/test_shaft_recipe_acceptance_drawing.py -q
```

### Mapping control confirms a context mismatch, not datum replacement

The observer ran at root `b63fc27e` / adapter `e77bfda` on the exact owned fulcrum
copy. Receipt `cad/out/reports/datum-policy-frqt5lvn/pilot.json`, SHA-256
`2692010d4d53ee3a9598fe71ae6bab952e7a3f8a0a2c3ad74d343a6171e73d08`:

| Native equality/readback | Immediately after datum insertion | Final PMI bank |
| --- | ---: | ---: |
| Original source versus selected view entity | 0 | 0 |
| Selected view entity versus actual attachment | 1 | 1 |
| Source versus reverse-mapped selected entity | 1 | 1 |
| Source versus reverse-mapped attached entity | 1 | 1 |
| Source versus unconverted attachment | 0 | 0 |

All four selected PMI entities reverse-mapped to their exact original model
roles. Forward mapping returned null for the Front rim used by datum A and
cylindricity, but returned the exact selected edge for both Right-view end rims.
Thus a forward-map fallback would impose an unsupported extra requirement on
this proven reverse-mapping call shape. The datum did not change attachment
between its immediate and completed-bank witnesses.

The unchanged old direct comparison still failed. Recipe time was
17.721189600008074 s, including 3.553409700456541 s of instrumented read groups
(3.5550348999677226 s observer wall time). An offline gate ran concurrently;
this is not a speed comparison. All source/runtime hashes remained exact,
failure evidence had no errors, and owned cleanup restored the empty baseline.
The four PMI items were visible in the failed-scene PNG, but SF insertion,
native save, full cold reopen and complete-sheet acceptance were not reached.

Production now declares `AnnotationEntityContext.MODEL` on each shaft's four
PMI roles and its finish: eight PMI roles and two finishes across both shafts.
The validator first requires exact annotation owner,
attachment count/type and view identity, then maps the actual attached drawing
edge/face through the referenced source **part** extension and requires
`IsSame(expected_original_role, mapped) == 1`. Null mappings, read errors and
unknown identity fail; geometry, names, forward mapping and direct-identity
fallbacks cannot substitute. Existing cone PMI and other view-derived explicit
SF callers keep the default `VIEW` contract and its direct native comparison.
No source geometry, specification, display seed or tolerance changes.

The owned observer requires the same original source-role identity. Its complete
built and cold banks explicitly use model context against freshly resolved
source handles; cold tests use distinct new source/view handles and forbid old
view access. Fourteen new context tests failed first on the old API. Tests cover
both mapping directions' context separation, null/wrong/unknown/throwing reverse
mapping, wrong document/view, direct-view silhouette preservation and the real
native datum/SF call paths. Type-46 **model** reverse mapping is not claimed;
the two existing silhouette SF callers retain their direct-view contract.

```powershell
uv run python -m pytest cad/scripts/test_annotation_attachment_context_drawing.py cad/scripts/test_native_pmi_datum_drawing.py cad/scripts/test_shaft_recipe_acceptance_drawing.py -q
```

The owned command above with `--candidate b63fc27e` retains the old recipe's
direct-view expectation for replay of the mismatch. The corrected model-context
recipe's subsequent native and cold results are recorded below; its implementation
tests alone did not establish that acceptance.

Re-runnable offline proof:

```powershell
uv run python -m pytest cad/scripts/test_shaft_pmi_entities_drawing.py cad/scripts/test_fulcrum_shaft_drawing.py cad/scripts/test_pivot_shaft_drawing.py cad/scripts/test_entity_resolution_drawing.py cad/scripts/test_gtol_spec.py cad/scripts/test_native_annotation_placement_drawing.py cad/scripts/test_drawing_surface_finish_validation.py cad/scripts/test_part_isolation.py -q
```

The new tests failed first on the old implementation: it accepted a substituted
same-diameter face, a same-named different view, missing attachment/type evidence,
and a wrong controlled end. Fixtures also reject missing/ambiguous feature faces
and rims, prove that unrelated same-diameter faces are never searched, and check
that a later insertion cannot silently change an earlier datum's attachment.
The explicit-SF fixture preserves its original assertions and now supplies native
owner/type fields. No intentional existing test contract was changed.

API references consulted from the bundled official documentation:
`IView.SelectEntity`, `IFeature.GetFaces`, `IFace2.GetEdges`,
`IEdge.GetTwoAdjacentFaces2`, `IAnnotation.GetAttachedEntities3`,
`GetAttachedEntityTypes`, `GetAttachedEntityCount3`, `Owner`, `OwnerType`, and
`ISldWorks.IsSame`; associated selection/attachment examples and owner/select enums.

### Full fulcrum build: five explicit roles pass, cold title still fails

Root `edde1174` / adapter `e77bfda` built and saved the fulcrum native drawing,
PDF and PNG in 21.2943858000217 s (`recipe_seconds`, including diagnostic
context observations). Receipt `cad/out/reports/datum-policy-ges4a7q0/pilot.json`
has SHA-256
`47db15fe4c750df94a331060a3ddd59ffc2355733df595bf2fe62b3296e6fb41`.
The built explicit bank contains all four PMI roles and the surface finish,
with exact MODEL-context reverse mapping to their original controlled entities;
11 context observation stages were retained. This is not an uninstrumented
speed comparison.

Cold reopen rejected only the linked TITLE `Sheet1/DetailItem245`: its X text
origin moved from 0.35389179984999647 to 0.35789913560224523 m, a
4.007335752248764 mm displacement repeated in three measured paths. The final
cold explicit-entity bank was therefore not reached. That substantive title
movement remains a failed gate, independently of the source-PMI near-zero
serialization correction in the [selected-view control](selected-view-model-pmi-control.md).

Original and owned-copy hashes remained exact; runtime guard errors were empty.
Failure capture was complete with no errors, and owned cleanup restored the
empty baseline without error. Main's eye review found all five symbols clear
but the original DWG/REV title-block text overlapping. There is no full-sheet
visual/cold acceptance or pivot native acceptance from this fulcrum result.

### Both shafts pass with the populated title-block candidate

Frozen root `d8ec09f5` / adapter `e77bfda4`, existing SW PID 31860, ran the
complete fulcrum then pivot recipes with `--factory prepared` and the project
template SHA-256 `2b1bbe3dfff265e8bb35ea79f0f9690f808049f5cef764cab8959c1eaee5e849`.
Receipt `cad/out/reports/datum-policy-7wjzdu9q/pilot.json` has SHA-256
`f0e7ab9419a1879f3e8852d7737c67997760f913d95e9395662c0635dd2c3a4a`.
Both trials passed the full recipe, saved native/PDF/PNG artifacts, exact cold
annotation comparison (no roundoff allowances), and all five explicit entity
roles before and after reopening: datum A, bearing cylindricity, both end
perpendicularities and bearing finish. Cold roles were resolved freshly, not
compared through closed-document handles.

Recipe timers were 23.099 s and 19.035 s; prepared instantiation inside those
timers was 1.587 s and 1.295 s. The 262.787 s diagnostic total also includes
separate preparation, source/attachment observations and cold verification.
These are instrumented functional controls, not an unpaired speedup claim.

Original and owned-copy source hashes stayed exact at every checkpoint, runtime
guard errors were empty, and cleanup restored the empty baseline without error.
Main inspected both complete PNGs: all five symbols are readable, and the title,
drawing number, revision, finish and material no longer overlap. Pivot retains
long but clear leaders. Fulcrum's previous 4.007 mm title movement is absent;
the comparison itself was not weakened.

This proves the two recipes with the revised template and prepared constructor.
The subsequent explicit production factory/runner passed its
[MISS/HIT boundary at `d6ad5aad`](prepared-template-viewport-control.md#production-misshit-at-d6ad5aad),
with both PNGs inspected and source hashes unchanged. That production run did
not cold-reopen the drawings or compare printed normal/MISS/HIT pairs; the cold
role proof above belongs to `d8ec09f5`. Neither run covers the remaining
VIEW/silhouette callers or fleet acceptance.
