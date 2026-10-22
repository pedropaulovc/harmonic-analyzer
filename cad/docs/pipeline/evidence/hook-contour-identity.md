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
- the native face's owning feature being the source part's authoritative `Wire`
  feature, compared with `ISldWorks.IsSame`, not a matching feature-name string;
- a finite native torus at the same origin and Z axis, with the catalogue eye
  mean radius and wire radius, using the unchanged 1e-5 mm diameter tolerance.

Do not compare a post-rebuild annotation with a silhouette handle retained from
before the settling rebuild. The 2026-10-22 native diagnostic at source
`2942dd0651b13be2ad64af9568f8323f2f3bd551` read one EyeOD attachment of type 46;
its captured and attached CircleParams were identical:

```text
(-2.102257677834285e-10, -7.358970724458125e-11, 0,
 0, 0, 1, 0.006350000187332174)
```

The failing clause was the old physical-owner comparison, not attachment count,
type or measured circle. That diagnostic did not separately record a missing
face versus a not-same native face; identical circle parameters alone are not
owner-identity proof. The repair retains only dimension keys and contracts, not
pre-rebuild COM handles. It reads the annotation's current attached silhouette,
then obtains its face's native feature and torus. The expected feature comes
from `IPartDoc.FeatureByName("Wire")` on the current view's referenced source
part. Both native source builders explicitly name their circular-profile sweep
`Wire` (`diag_build_9489T111._sweep_wire` and
`diag_build_9490T1._sweep_wire`); the finished-stock trim keeps that feature.
`Wire` also owns the bend, so the centre, axis and catalogue torus radii are
required independently. No fresh visible-entity scan or self-membership test is
used during verification.

The same native enumeration returned two ID entries with identical circle
parameters. Enumerator entries are not annotation attachments: multiple visible
entries must not disable the exactly-one-attachment guard. Wrong diameter,
foreign owner, missing contour and additional annotation attachments are refused.

The SM diagnostic records `Wire` as the eye's actual native owner. The retained
CH diagnostic does not contain a feature/torus readback; its source builder is
the authoritative feature-name evidence. Final native qualification must prove
the strict source-feature identity check on both drawings.

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

The initial HLR setup precedes the imported control annotations. The existing
`_drawing_view_display.set_hidden_lines_removed` contract documents that these
annotations can leave the edge set unregenerated, and that
`IView.UpdateViewDisplayGeometry` alone does not rebuild it. Immediately before
discovery, the recipe therefore uses the existing real HLV-to-HLR transition
with both native display-mode readbacks, then materializes that regenerated
geometry with `UpdateViewDisplayGeometry`. Existing imported machining controls
must still pass the settled checks. The native output must confirm recovery of
the missing physical ID; the source-order correction is not itself that proof.
Do not retry against a different type, diameter, view or configuration if the
strict query still finds no ID.

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

The one approved combined failure census retains the original kind4 snapshot
and buffers each actual predicate-time field, getter stage and first rejection.
Only on failure does it attach a strict-JSON exception note with independent
later readbacks, every candidate's predicate fields/errors, source/view/config
and physical-path controls, native equality self-controls, relevant torus
correspondence/roundtrip observations and a diagnostic kind1 inventory. A later
true readback must not overwrite an earlier false predicate. These observations
do not change acceptance, selection, view modes or the original exception.

Generic `IsSame` dispatch signatures do not establish feature-class or
drawing/source-context support. The documented results are 1 (same), 0 (not
same), and -1 (unable to determine). Correspondence observations and matching
names/geometry are not permission to waive the mandatory owner predicate.

## Evidence boundary

The focused offline tests replay observed native circle parameters, invalidate
pre-rebuild handles and exercise wrong circle, owner, view, configuration,
attachment count/type and missing/extra attachment refusals. Their COM-shaped
objects are test doubles, not native evidence. Native farm outputs, complete v44
sheet comparisons and automated machinist reports remain separate qualification
evidence tied to the producing source and PDF hashes.
