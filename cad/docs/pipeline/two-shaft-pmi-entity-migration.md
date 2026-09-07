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

The shared guards also apply to the existing explicit-entity cone-gear-shaft PMI
and finish calls; those require adjacent native verification before release.

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
