# Hook supplier contour identity

Supplier eye dimensions are references to the **physical finished part**, not to
its nominal stock diagram. Preserve the model frame: eye centre at the model
origin, eye in XY, shank towards −Y. Do not substitute the outer eye, a bend or
tip circle, a nominal carrier, or a nearby curve when the required contour is
absent.

## Channel spring hook (9489T111)

The physical eye OD is 12.7 mm and ID is 6.35 mm. The settled verifier requires:

- the expected finished configuration on both finished views;
- exactly one non-null, non-dangling native attachment, with selection type 46
  (`SILHOUETTE`), and agreement between the native count, entity and type arrays;
- a finite native analytic circle at the model origin (centre coordinates within
  1e-8 m), normal Z within 1e-8 of ±1, and diameter within 1e-5 mm of the
  corresponding physical eye size;
- the expected native drawing view and exact referenced source-part path;
- the attached drawing face mapped unconditionally into the current referenced
  source part with `IModelDocExtension.GetCorrespondingEntity2`; a missing
  correspondence is refused;
- that mapped source face's owning feature being the source part's authoritative
  `Wire`, compared in the same native context with `ISldWorks.IsSame == 1`, not
  a matching name, feature ID or drawing-context feature;
- a finite mapped-source torus at the same origin and Z axis, with the catalogue
  eye mean radius and wire radius, using the unchanged 1e-5 mm diameter tolerance.

Do not compare a post-rebuild annotation with a silhouette handle retained from
before the settling rebuild. The 2026-10-22 native diagnostic at source
`2942dd0651b13be2ad64af9568f8323f2f3bd551` read one EyeOD attachment of type 46;
its captured and attached CircleParams were identical:

```text
(-2.102257677834285e-10, -7.358970724458125e-11, 0,
 0, 0, 1, 0.006350000187332174)
```

The old comparison used a face or feature from the drawing context against an
object from the source-part context. The complete `c34ee90f48590b46e19479f30c959d8b0fcb2cff`
readback distinguishes this from missing geometry: both physical ID entries and
the OD entry are exact circles, but all three first reject at the direct
cross-context owner comparison (`IsSame == 0`). Both feature proxies are named
`Wire`, ID 34, and compare equal to themselves. Matching names and IDs therefore
do not repair this identity test.

The repair retains only dimension keys and contracts, not pre-rebuild COM
handles. For the annotation's current attached silhouette, it maps `GetFace()`
into the current view's referenced source part before testing owner identity
and the source torus. The complete native readback returns a mapped source face
whose owner compares equal to source `IPartDoc.FeatureByName("Wire")` (`1`).
The reverse `IView.GetCorrespondingEntity(source_face)` returns null; that
unsupported-in-practice roundtrip is not used as a substitute identity test.
Both native source builders explicitly name their circular-profile sweep
`Wire` (`diag_build_9489T111._sweep_wire` and
`diag_build_9490T1._sweep_wire`); the finished-stock trim keeps that feature.
`Wire` also owns the bend, so the centre, axis and catalogue torus radii remain
independently mandatory. No fresh visible-entity scan or self-membership test
is used during verification.

The same native enumeration returned two ID entries with identical circle
parameters. Enumerator entries are not annotation attachments: multiple visible
entries must not disable the exactly-one-attachment guard. Wrong diameter,
foreign owner, missing contour and additional annotation attachments are refused.

The complete CH source-eye torus is centred at
`(-2.102257677834285e-10, -7.358970724458125e-11, 0)`, with Z axis, major radius
`0.004762500187332174 m` and minor radius `0.0015875 m`. Source and view both
reference `Default` configuration ID 0, with HLR mode 2 and an exact source path
whose physical file identity also matches. These are actual identity/frame
readbacks, not proof that the repaired recipe has reached native save. Final
native qualification must still exercise the corrected guard and both save
boundaries.

The existing pre-save layout check refreshes every view before the attachment
readback. The attachment verifier itself performs no geometry refresh, rebuild,
repair or source-configuration activation. It runs again on the existing
`after_drawing_save` checkpoint, after a successful native SaveAs3 context and
file check, before PDF export. It temporarily activates drawing sheets and
restores FINISHED for the established export semantics; this is drawing UI state,
not part-configuration activation.

This second check proves the **still-open post-save document**. It is not a cold
reopen, nor independent proof of bytes persisted on disk. The shared checkpoint
also reports attempted saves on failure, so an after-event without successful
save/leaf evidence must never be presented as save proof.

## Counterweight boss hook (9490T1)

The required physical eye ID is 7.9375 mm. Its modelled physical OD is 17.5895 mm;
the nominal as-supplied stock diagram is a separate source and is not a contour
oracle. Keep the exact physical-ID criteria: centre within 1e-8 m of the model
origin, normal Z within 1e-8 of ±1 and diameter within 1e-5 mm. Discovery and
post-rebuild identity must agree on the actual native contour type and finished
source configuration; absence is an error, never permission to select the OD.

The supplemental native census at source
`322abecf0de187a880dc2d8d4f67fa012230e7cd` found no exact ID among either the
visible silhouettes or the nine visible model edges. The three circular edges
were shank sections with Y normals, not an alternate native ID. The owning
`Wire` eye surface was a torus with centre
`(-4.4201138409138974e-11, -1.3548712585881306e-10, 0)`, Z axis, major radius
`0.006381749644849558 m` and minor radius `0.002413 m`. Its analytic inner
diameter is `7.937499289699116 mm`; the model-to-view transform had identity
rotation and scale 4. This is the expected model frame, not permission to
dimension a nominal replacement or change selection type.

The initial HLR setup precedes imported control annotations. The existing
`_drawing_view_display.set_hidden_lines_removed` contract documents that these
annotations can leave the edge set unregenerated and that
`IView.UpdateViewDisplayGeometry` alone does not rebuild it. A real HLV-to-HLR
transition with both native mode readbacks, followed by
`UpdateViewDisplayGeometry`, was therefore exercised before discovery.
**It did not recover the missing SM ID.** The complete `c34` native census still
contains no exact origin-ID circle. An ordering or refresh change alone is not
a demonstrated repair. Do not retry against a different type, diameter, view or
configuration when the strict query finds no ID.

Discovery therefore uses the existing primary coordinate-acquisition seam, not
a fallback chain of enumerators. From the current finished view's exact source
part and configuration, it finds exactly one `Wire` eye torus satisfying the
strict native owner, centre, axis and radii predicates. It projects that native
torus's top-inner point `(cx, cy + major_radius - minor_radius, cz)` into the
drawing view with `model_points_in_view`, then calls the established
`_select_view_entity(..., "SILHOUETTE", sheet_xy)` hit test.

The acquired native selection must immediately have count one and type 46.
Before creating the dimension, its returned `ISilhouetteEdge.GetCurve()` must
prove the exact finite origin-ID circle, and its face must map to the
authoritative source `Wire` eye torus. The point is only an acquisition input:
it is not a synthetic contour or a nominal dimension, and selecting the OD,
another circle, another feature or an ambiguous source torus is refused. There
is no visible-enumerator rescue, edge substitution or relaxed criterion.

`IModelDocExtension.SelectByID2` documents the `SILHOUETTE` selection string.
The existing pinion-bracket coordinate-silhouette caller records a real farm
positive control, whereas `SelectByRay` is not documented to select silhouettes.
Those contracts support this acquisition design, not a claim that the SM hit
test has succeeded. Only the repaired recipe's actual native leaf can prove
the required physical contour and subsequent attachment survival.

The final and still-open post-native-save checks retain type 46 and exactly one
live attachment, and reuse the same strict circle, source-view, native feature
and torus predicate as discovery. The label's physical ID remains mandatory:
the outer eye is not an alternative. As for CH, refreshes belong to the existing
pre-save layout check, not the post-save observer, and successful save/leaf
evidence is required before claiming post-save proof.

## Rejected native candidate 10ae

Source `10ae3ca0e95afd612b324f792ef142ffd281c136` produced two failed normal
drawing leaves in run `20261022T201714479Z-50388d94c538424fae4dc16fafd5c040`,
build `20261022T201743.641221Z-cd92a187b96d465eb7c0a837b1743981`. Both source
part leaves succeeded, but neither drawing reached a qualified native save:

- CH stopped during discovery with `EyeOD: unchanged spring eye has no circular
  silhouette`.
- SM stopped during discovery with `unchanged counter eye has no exact ID
  circular silhouette`.

These messages establish **zero accepted contours**, not zero raw native
circles. This source's new view, referenced-path, native-feature and torus
predicates can reject an otherwise circular contour. The two worker logs and
native events contain no geometry census; both explicitly report no forensic
captures. There is no successful feature-equality, annotation, after-SaveAs3 or
PDF proof from this attempt.

The exact 2942-to-10ae source comparison shows no new CH pre-discovery mode,
configuration or refresh call. `_drawing_view_display`, `_drawing_edges` and
`_drawing_common` have identical Git blobs between those sources. The later
layout-before-reference refresh order was not reached by the CH failure, so it
does not explain the new pre-creation rejection.

## Complete native readback at c34

The approved combined normal drawing run
`20261022T214811367Z-f2dd38415a1d4a20bc1333f7621235be`, build
`20261022T214835.817289Z-6919e84a3f174b3ebeccadff0b97e482`, preserved the original
predicate-time snapshot separately from later independent getter observations.
Both drawing leaves retained their original fatal errors. The two source-part
leaves were cache hits; there are no qualified drawing saves or PDFs from this
attempt.

- CH: 48 native silhouette entries, five analytic circles, two exact origin-ID
  entries and one exact origin-OD entry. All three physical entries first reject
  at the direct drawing/source feature equality. Native drawing feature
  self-equality is 1; source-mapped owner equality to source `Wire` is 1.
- SM: 49 native silhouette entries, five analytic circles, only the OD at the
  origin and no exact physical ID. The ten visible model edges contain only
  three circular shank sections, with Y normals; they are not an alternate ID.
  The source eye torus has the exact centre, axis and radii listed above.
- Both: referenced and active source configurations are `Default`, ID 0; HLR
  mode is 2; source paths and physical file identities match. Model-to-view
  rotation is identity, with scale 5 for CH and 4 for SM.

The supported visible-silhouette enumeration is
`IView.GetVisibleEntities2(component, 4)`, not an all/hidden-contour API.
Face-generated silhouette curves are transient and unselectable and cannot
replace the required native `ISilhouetteEdge` attachment. Correspondence,
matching names and torus geometry alone do not waive the exact circle, native
kind, source-owner or annotation-count predicates.

Full worker logs and structured census packets are retained out of tree in
`D:/farm-runs/rolling-main-post-v44-20261021`; provisional census collectors are
not part of the permanent repair.

## Evidence boundary

The focused offline tests replay observed native circle parameters, invalidate
pre-rebuild handles and exercise wrong circle, owner, view, configuration,
attachment count/type and missing/extra attachment refusals. Their COM-shaped
objects are test doubles, not native evidence. Native farm outputs, complete v44
sheet comparisons and automated machinist reports remain separate qualification
evidence tied to the producing source and PDF hashes.
