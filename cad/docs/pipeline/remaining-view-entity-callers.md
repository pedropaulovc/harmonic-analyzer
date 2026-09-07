# Remaining explicit annotation callers: VIEW provenance audit

Read-only source audit at `db33e21f`, covering the ten remaining recipes in
[the two-shaft migration scope](two-shaft-pmi-entity-migration.md). Every explicit
handle originates in its intended drawing view's visible-entity inventory.
**No source-model origin requiring `AnnotationEntityContext.MODEL` was found.**
This is a provenance conclusion, not native rebuild/save/reopen acceptance.

`_drawing_common.visible_view_entities` (`:2789`, inventory `:2820–2822`) calls
the supplied `IView.GetVisibleComponents()` and `GetVisibleEntities2(component,
kind)`. It returns those handles, not entities traversed from a source part.
`_gear_drawing_entities.visible_circle_edge` (`:33`, enumeration `:93`) filters
that EDGE inventory by radius, then sorts centers; it returns the same IEdge.
Reading model-space circle parameters does not change an object's context.

| Recipe | Resolver / assignment | Explicit-position SF call |
| --- | --- | --- |
| `cone_gear_shaft` | Side `_cylindrical_face` (`:112`, enumeration `:115`), pivot/tip at `:188–189` | `:248`, `:258`, same Side FACE handles |
| `alignment_pinion` | Front `visible_circle_edge`, `:133` | `:162`, EDGE |
| `crank_drive_gear` | Front `visible_circle_edge`, `:133` | `:169`, EDGE |
| `crank_pinion` | Front `visible_circle_edge`, `:131` | `:167`, EDGE |
| `cylinder_gear` | Front `visible_circle_edge`, `:158` | `:206`, EDGE |
| `rack_pinion` | Front `visible_circle_edge`, `:132` | `:155`, EDGE |
| `transgear_feed_pinion` | Front `visible_circle_edge`, `:137` | `:160`, EDGE |
| `transgear_pinion` | Front `visible_circle_edge`, `:132` | `:155`, EDGE |
| `crankshaft` | Right `_visible_journal_silhouette` (`:154`, enumeration `:161`), assigned `:335` | `:420`, SILHOUETTE 46 |
| `spring_hook` | Front `_shank_silhouette` (`:79`, enumeration `:96`), assigned `:197` | `:198`, SILHOUETTE 46 |

Line numbers refer to `cad/scripts/draw_<recipe>.py` at the audited revision.
The shared gear selector's diameter/center qualification, crankshaft's longest
journal silhouette, and spring-hook's longest-segment/midpoint ordering remain
their existing strategies. This audit does not prove unique semantic feature
resolution or recommend preserving those strategies indefinitely.

Additional explicit PMI handles follow the same provenance:

- Cone datum A (`:226`) reuses the Side pivot FACE. Journal cylindricity
  (`:232`) uses the End EDGE assigned `:209` by `_outer_end_edge` (`:95`),
  which enumerates visible edges and chooses the largest circle. Tip runout
  (`:237`) remains a coordinate SILHOUETTE route.
- Crank-drive/crank-pinion datum A uses the Front bore EDGE (`:136` / `:134`).
  Their tooth-tip FCFs (`:157` / `:155`) use Right-view silhouettes assigned
  `:134` / `:132`; `_gear_drawing_entities.visible_tooth_tip_silhouette`
  (`:147`, enumeration `:175`) returns the same view-enumerated silhouette.
- Cylinder-gear FCF (`:187`) uses the Front planar FACE assigned `:159` by
  `_largest_visible_planar_face` (`:83`, direct visible-face enumeration `:90`).
  The frame's numeric seed mentioning `RIGHT_CENTER` does not change its owner
  view or handle context.
- Crankshaft datum B/FCF (`:365`, `:373`) use Right end-circle edges from
  `_visible_shaft_end_edges` (`:230`, assigned `:353`). Position FCF (`:407`)
  uses the Right visible edge assigned `:388` by `_visible_cross_hole_edge`
  (`:192`). Adjacent cylindrical faces qualify that edge; they do not replace it.

The SF helper's silhouette `GetFace()` similarly qualifies the controlled
surface; its explicit annotation target remains the original silhouette.
Comments saying "model edge", source parts being open, and model-space endpoint
coordinates are not evidence of a source-part handle.

## Native acceptance still needed

All ten unchanged full recipes need separate owned acceptance. A family control
does not accept every caller. Start with cone (two PMI plus two SF explicit
handles), then one bore-edge gear mechanism control, then the remaining recipes.
Keep original/source-copy/runtime hashes, exact document ownership and cleanup,
typed content/dimension/BASIC checks, cold reopen, final collision gates and an
eye pass. Stop each invocation on its first failure.

At selection, completed insertion/rebuild and final pre-close boundaries, retain
original view handle → selected handle → actual attachment, exact annotation and
view ownership, attachment count/type, and unchanged typed contents. Cold checks
must resolve fresh roles in the freshly reopened view; old COM handles cannot
cross a closed-document boundary. A later mismatch is a diagnostic, not permission
to switch contexts or accept equal names/radii as identity.

**Type 46 affects five whole recipes:** crankshaft and spring-hook finishes,
crank-drive/crank-pinion tooth-tip FCFs, and cone's coordinate tip-runout FCF.
`probe_drawing_attachments.py:49,395` currently excludes it. The existing
`EntityAcceptance` also expects source `FeatureFace`/`FaceBoundary` roles and
reverse-maps VIEW inputs; simply enrolling these ten targets would not provide
the required proof. A VIEW observer needs direct handle identity and an explicit
silhouette witness. Documented `ISilhouetteEdge.GetView`, `GetFace`, `GetCurve`,
`GetStartPoint` and `GetEndPoint` expose the owning view and controlled geometry;
their native same-session/cold behavior must be positively checked, not inferred.
No MODEL reverse mapping for silhouettes is claimed.

Bundled primary references consulted: `IView.GetVisibleComponents`,
`IView.GetVisibleEntities2`, *Get Visible Components and Entities in Drawing View*
example (which supplies `SelectData.View`), `ISilhouetteEdge.Select2`, `GetView`,
`GetFace`, and `GetCurve`. These support the declared VIEW-origin selection
contract; none promises persistent COM identity across rebuild/save/reopen.
