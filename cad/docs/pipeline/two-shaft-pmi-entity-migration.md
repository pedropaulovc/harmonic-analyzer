# Two-shaft PMI entity migration

This bounded candidate replaces eight PMI attachment picks and two surface-finish
picks in `draw_fulcrum_shaft.py` and `draw_pivot_shaft.py`. It has **offline proof
only**; native build, saved/reopened identity and render acceptance remain required.
No speed improvement is claimed.

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
convention; selection and placement on these two native files still need a pilot.
Feature membership is `FeatureByName("Shaft").GetFaces()` plus exact-one geometric
matching, not an exclusive-owner claim: the API permits shared feature faces and
`IFace2.GetFeature()` returns only the oldest owner.

The typed datum/control/finish rows, part builders, view scales, dimension
curation, display positions and placement tolerances are unchanged. No coordinate,
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
The other ten production callers and the typography diagnostic remain pending
separate enrollment/acceptance; in particular type-46 silhouette geometry is not
silently accepted by the current general attachment snapshot's exclusion list.

Offline runner/role acceptance regression:

```powershell
uv run python -m pytest cad/scripts/test_shaft_recipe_acceptance_drawing.py cad/scripts/test_datum_policy_recipes_drawing.py cad/scripts/test_recipe_template_factory_drawing.py -q
```

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
